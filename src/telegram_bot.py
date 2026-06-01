#!/usr/bin/env python3
"""Read-only Telegram dashboard for the TON fee prediction project."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_TELEGRAM_MESSAGE_LENGTH = 3900
NANOTON_PER_TON = 1_000_000_000
FORECAST_STALE_HOURS = 26


HELP_TEXT = """TON Fee Forecast Bot

I estimate the next 24 hours of TON transaction fees using recent on-chain activity.

Commands:
/forecast - Next 24-hour predicted average transaction fees
/besttime - Estimated cheapest hour to send a transaction
/accuracy - Operational live accuracy from previously published forecasts
/timezone - Show timezone detection and override examples

Times are shown in the detected Telegram language timezone when possible.
You can override it by adding an IANA timezone, for example: /forecast Asia/Seoul

Forecasts are directional estimates, not guarantees.
"""


CHART_DESCRIPTIONS = {
    "hourly_fee_trend.svg": "Hourly average fee trend across the collected feature window.",
    "fee_distribution.svg": "Distribution of observed transaction fees.",
    "network_activity_trend.svg": "Sampled transaction and account activity by hour.",
    "model_r2_comparison.svg": "Chronological holdout R2 comparison by model.",
    "rolling_backtest_r2_comparison.svg": "Rolling backtest mean R2 comparison by model.",
    "model_mae_comparison.svg": "Chronological holdout MAE comparison by model.",
    "actual_vs_predicted.svg": "Holdout actual next-hour fees versus model predictions.",
    "forecast_next_24h.svg": "Recent actual fees with the generated 24-hour forecast.",
    "forecast_next_24h.png": "Telegram-ready next 24-hour forecast chart.",
}


logger = logging.getLogger("ton_fee_telegram_bot")

LANGUAGE_TIMEZONE_MAP = {
    "ko": "Asia/Seoul",
    "ja": "Asia/Tokyo",
    "zh": "Asia/Shanghai",
    "zh-cn": "Asia/Shanghai",
    "zh-hans": "Asia/Shanghai",
    "zh-tw": "Asia/Taipei",
    "zh-hant": "Asia/Taipei",
    "ru": "Europe/Moscow",
    "uk": "Europe/Kyiv",
    "tr": "Europe/Istanbul",
    "pt-br": "America/Sao_Paulo",
    "es-mx": "America/Mexico_City",
    "en-gb": "Europe/London",
}


class DashboardError(Exception):
    """Expected dashboard data loading error."""


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def predictions(self) -> Path:
        return self.root / "predictions.csv"

    @property
    def hourly_features(self) -> Path:
        return self.root / "hourly_features.csv"

    @property
    def model_metrics(self) -> Path:
        return self.root / "models" / "model_metrics.json"

    @property
    def model_comparison(self) -> Path:
        return self.root / "models" / "model_comparison.csv"

    @property
    def rolling_backtest(self) -> Path:
        return self.root / "models" / "rolling_backtest.csv"

    @property
    def operational_metrics(self) -> Path:
        return self.root / "models" / "operational_metrics.json"

    @property
    def last_updated(self) -> Path:
        return self.root / "last_updated.json"

    @property
    def collection_metadata(self) -> Path:
        return self.root / "collection_metadata.json"

    @property
    def figures_dir(self) -> Path:
        return self.root / "docs" / "figures"


@dataclass(frozen=True)
class TimeContext:
    timezone: ZoneInfo
    name: str
    source: str


@dataclass(frozen=True)
class ForecastStats:
    rows: list[dict[str, str]]
    cheapest: dict[str, str]
    highest: dict[str, str]
    cheapest_fee: float
    highest_fee: float
    difference: float
    percent: float


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DashboardError(f"Missing file: {relative(path)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DashboardError(f"Could not parse JSON file: {relative(path)} ({exc})") from exc


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise DashboardError(f"Missing file: {relative(path)}")
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except csv.Error as exc:
        raise DashboardError(f"Could not parse CSV file: {relative(path)} ({exc})") from exc


def read_csv_overview(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DashboardError(f"Missing file: {relative(path)}")

    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            first: dict[str, str] | None = None
            last: dict[str, str] | None = None
            rows = 0
            for row in reader:
                if first is None:
                    first = row
                last = row
                rows += 1
    except csv.Error as exc:
        raise DashboardError(f"Could not parse CSV file: {relative(path)} ({exc})") from exc

    return {"rows": rows, "first": first or {}, "last": last or {}}


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def to_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int | None = None) -> int | None:
    numeric = to_float(value)
    if numeric is None:
        return default
    return int(numeric)


def format_nanoton(value: Any) -> str:
    numeric = to_float(value)
    if numeric is None:
        return "n/a"
    return f"{numeric:,.0f} nanoton"


def format_ton(value: Any) -> str:
    numeric = to_float(value)
    if numeric is None:
        return "n/a"
    return f"{numeric:.9f} TON"


def nanoton_to_ton(value: Any) -> float | None:
    numeric = to_float(value)
    if numeric is None:
        return None
    return numeric / NANOTON_PER_TON


def format_metric(value: Any, digits: int = 4) -> str:
    numeric = to_float(value)
    if numeric is None:
        return "n/a"
    return f"{numeric:.{digits}f}"


def format_timestamp(value: Any) -> str:
    return format_timestamp_for_timezone(value, default_time_context())


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text or text.lower() == "n/a":
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def default_time_context() -> TimeContext:
    return TimeContext(timezone=ZoneInfo("UTC"), name="UTC", source="fallback")


def timezone_from_name(name: str) -> TimeContext | None:
    candidate = name.strip()
    if not candidate:
        return None
    aliases = {
        "UTC": "UTC",
        "GMT": "UTC",
        "KST": "Asia/Seoul",
        "JST": "Asia/Tokyo",
        "EST": "America/New_York",
        "EDT": "America/New_York",
        "CST": "America/Chicago",
        "CDT": "America/Chicago",
        "MST": "America/Denver",
        "MDT": "America/Denver",
        "PST": "America/Los_Angeles",
        "PDT": "America/Los_Angeles",
    }
    zone_name = aliases.get(candidate.upper(), candidate)
    try:
        return TimeContext(timezone=ZoneInfo(zone_name), name=zone_name, source="command override")
    except ZoneInfoNotFoundError:
        return None


def timezone_from_language(language_code: Any) -> TimeContext | None:
    if not isinstance(language_code, str) or not language_code.strip():
        return None
    normalized = language_code.strip().lower().replace("_", "-")
    zone_name = LANGUAGE_TIMEZONE_MAP.get(normalized) or LANGUAGE_TIMEZONE_MAP.get(normalized.split("-", 1)[0])
    if not zone_name:
        return None
    try:
        return TimeContext(timezone=ZoneInfo(zone_name), name=zone_name, source=f"Telegram language {language_code}")
    except ZoneInfoNotFoundError:
        return None


def resolve_time_context(message: dict[str, Any] | None = None) -> TimeContext:
    text = message.get("text") if isinstance(message, dict) else None
    if isinstance(text, str):
        parts = text.strip().split(maxsplit=1)
        if len(parts) > 1:
            override = timezone_from_name(parts[1])
            if override is not None:
                return override

    user = message.get("from") if isinstance(message, dict) else None
    if isinstance(user, dict):
        inferred = timezone_from_language(user.get("language_code"))
        if inferred is not None:
            return inferred
    return default_time_context()


def time_context_note(context: TimeContext) -> str:
    if context.source == "fallback":
        return "Time zone: UTC fallback. Telegram does not expose a user's exact timezone; add an IANA timezone to override, e.g. /forecast Asia/Seoul."
    return f"Time zone: {context.name} ({context.source})."


def format_timestamp_for_timezone(value: Any, context: TimeContext) -> str:
    timestamp = parse_timestamp(value)
    if timestamp is None:
        if not value:
            return "n/a"
        text = str(value)
        if text.endswith("+00:00"):
            return f"{text[:-6]}Z"
        return text
    local = timestamp.astimezone(context.timezone)
    return local.strftime("%Y-%m-%d %H:%M %Z")


def format_age_hours(value: Any) -> str:
    timestamp = parse_timestamp(value)
    if timestamp is None:
        return "n/a"
    hours = max(0.0, (datetime.now(UTC) - timestamp).total_seconds() / 3600)
    return f"{hours:.1f} hours"


def freshness_status(generated_at: Any, forecast_end: Any) -> tuple[str, list[str]]:
    warnings: list[str] = []
    generated = parse_timestamp(generated_at)
    end = parse_timestamp(forecast_end)
    now = datetime.now(UTC)

    if generated is None:
        warnings.append("Forecast generated timestamp is missing.")
    else:
        age_hours = (now - generated).total_seconds() / 3600
        if age_hours > FORECAST_STALE_HOURS:
            warnings.append(
                f"Forecast is older than {FORECAST_STALE_HOURS} hours. Treat it as stale until automation refreshes it."
            )

    if end is not None and end < now:
        warnings.append("Forecast window has already ended. Treat this output as stale.")

    if warnings:
        return "STALE / check automation", warnings
    return "Fresh enough for directional use", []


def percent_from_r2(value: Any) -> str:
    numeric = to_float(value)
    if numeric is None:
        return "n/a"
    return f"{numeric * 100:.1f}%"


def sorted_by_float(rows: list[dict[str, str]], column: str, reverse: bool = True) -> list[dict[str, str]]:
    def key(row: dict[str, str]) -> float:
        value = to_float(row.get(column))
        if value is None:
            return float("-inf") if reverse else float("inf")
        return value

    return sorted(rows, key=key, reverse=reverse)


def load_forecast_stats(predictions_path: Path) -> ForecastStats:
    rows = sorted_by_float(read_csv_rows(predictions_path), "horizon_hours", reverse=False)
    now = datetime.now(UTC)
    rows = [
        row
        for row in rows
        if (forecast_hour := parse_timestamp(row.get("forecast_hour"))) is None or forecast_hour >= now
    ]
    if not rows:
        raise DashboardError("다음 갱신 대기 중 (forecast가 만료됨)")

    numeric_rows: list[tuple[dict[str, str], float]] = []
    for row in rows:
        predicted_fee = to_float(row.get("predicted_avg_total_fee"))
        if predicted_fee is not None:
            numeric_rows.append((row, predicted_fee))
    if not numeric_rows:
        raise DashboardError("predictions.csv does not contain numeric predicted_avg_total_fee values.")

    cheapest, cheapest_fee = min(numeric_rows, key=lambda item: item[1])
    highest, highest_fee = max(numeric_rows, key=lambda item: item[1])
    difference = highest_fee - cheapest_fee
    percent = difference / highest_fee * 100 if highest_fee else 0.0
    return ForecastStats(
        rows=rows,
        cheapest=cheapest,
        highest=highest,
        cheapest_fee=cheapest_fee,
        highest_fee=highest_fee,
        difference=difference,
        percent=percent,
    )


def compact_ton(value: Any) -> str:
    numeric = nanoton_to_ton(value)
    if numeric is None:
        return "n/a"
    return f"{numeric:.6f} TON"


def compact_ton_with_interval(row: dict[str, str], fee: Any) -> str:
    point = compact_ton(fee)
    lo80 = to_float(row.get("predicted_avg_total_fee_lo80"))
    hi80 = to_float(row.get("predicted_avg_total_fee_hi80"))
    if lo80 is None or hi80 is None:
        return point
    return f"{point} (80%: {compact_ton(lo80)} - {compact_ton(hi80)})"


def ascii_bar(value: float, max_value: float, width: int = 12) -> str:
    if max_value <= 0:
        return "." * width
    filled = max(1, min(width, round(value / max_value * width)))
    return "#" * filled + "." * (width - filled)


class Dashboard:
    def __init__(self, paths: ProjectPaths) -> None:
        self.paths = paths

    def start(self) -> str:
        return HELP_TEXT

    def help(self) -> str:
        return HELP_TEXT

    def summary(self, time_context: TimeContext | None = None) -> str:
        time_context = time_context or default_time_context()
        metadata = self._metadata()
        hourly = read_csv_overview(self.paths.hourly_features)
        predictions = read_csv_overview(self.paths.predictions)
        metrics = self._safe_json(self.paths.model_metrics)

        raw_rows = metadata.get("final_rows")
        first_hour = hourly["first"].get("hour")
        latest_feature_hour = hourly["last"].get("hour")
        latest_raw = metadata.get("latest_iso_utc")
        forecast_first = predictions["first"].get("forecast_hour")
        forecast_last = predictions["last"].get("forecast_hour")
        forecast_generated = predictions["first"].get("forecast_generated_at")

        lines = [
            "Project Summary",
            "",
            "What it does: predicts the next-hour average TON transaction fee from hourly on-chain features.",
            time_context_note(time_context),
            f"Raw rows: {format_count(raw_rows)}",
            f"Hourly feature rows: {format_count(hourly['rows'])}",
            f"Feature date range: {format_timestamp_for_timezone(first_hour, time_context)} to {format_timestamp_for_timezone(latest_feature_hour, time_context)}",
            f"Latest raw transaction timestamp: {format_timestamp_for_timezone(latest_raw, time_context)}",
            f"Latest feature timestamp: {format_timestamp_for_timezone(latest_feature_hour, time_context)}",
            f"Best model: {metrics.get('best_model_name', 'n/a')}",
            f"Holdout R2: {format_metric(metrics.get('best_r2'))}",
            f"Holdout MAE: {format_nanoton(metrics.get('best_mae'))}",
            f"Forecast rows: {format_count(predictions['rows'])}",
            f"Forecast range: {format_timestamp_for_timezone(forecast_first, time_context)} to {format_timestamp_for_timezone(forecast_last, time_context)}",
            f"Forecast generated at: {format_timestamp_for_timezone(forecast_generated, time_context)}",
            "",
            "Important limitation: some collection windows hit TON Center API page limits, so activity counts "
            "are sampled indicators rather than guaranteed full-chain volume.",
        ]
        return "\n".join(lines)

    def forecast(self, time_context: TimeContext | None = None) -> str:
        time_context = time_context or default_time_context()
        stats = load_forecast_stats(self.paths.predictions)
        rows = stats.rows
        generated = rows[0].get("forecast_generated_at")
        freshness, warnings = freshness_status(generated, rows[-1].get("forecast_hour"))
        top_cheapest = sorted(
            [
                (row, to_float(row.get("predicted_avg_total_fee")))
                for row in rows
                if to_float(row.get("predicted_avg_total_fee")) is not None
            ],
            key=lambda item: item[1] or 0,
        )[:3]

        lines = [
            "TON Fee Forecast",
            "",
            time_context_note(time_context),
            f"Window: {format_timestamp_for_timezone(rows[0].get('forecast_hour'), time_context)} -> {format_timestamp_for_timezone(rows[-1].get('forecast_hour'), time_context)}",
            f"Generated: {format_timestamp_for_timezone(generated, time_context)} ({format_age_hours(generated)} old)",
            f"Freshness: {freshness}",
            "",
            "Cheapest hour",
            f"{format_timestamp_for_timezone(stats.cheapest.get('forecast_hour'), time_context)}",
            f"{compact_ton(stats.cheapest_fee)} ({format_nanoton(stats.cheapest_fee)})",
            "",
            f"Forecast range: {compact_ton(stats.cheapest_fee)} - {compact_ton(stats.highest_fee)}",
            f"Peak spread: {compact_ton(stats.difference)} ({stats.percent:.1f}% below highest hour)",
            "",
            "Top cheap windows:",
        ]

        for index, (row, fee) in enumerate(top_cheapest, start=1):
            lines.append(
                f"{index}. {format_timestamp_for_timezone(row.get('forecast_hour'), time_context)} - "
                f"{compact_ton_with_interval(row, fee)}"
            )

        lines.extend(["", "Forecast by horizon:"])
        for row in rows:
            fee = to_float(row.get("predicted_avg_total_fee"))
            if fee is None:
                continue
            lines.append(
                f"h+{format_count(row.get('horizon_hours'))}: "
                f"{format_timestamp_for_timezone(row.get('forecast_hour'), time_context)} - "
                f"{compact_ton_with_interval(row, fee)}"
            )

        if warnings:
            lines.extend(["", *[f"Warning: {warning}" for warning in warnings]])
        lines.extend(["", "Chart: see the 24-hour forecast image below.", "Directional estimate, not a guarantee."])
        return "\n".join(lines)

    def status(self, time_context: TimeContext | None = None) -> str:
        time_context = time_context or default_time_context()
        metadata = self._metadata()
        hourly = read_csv_overview(self.paths.hourly_features)
        predictions = read_csv_overview(self.paths.predictions)
        forecast_generated = predictions["first"].get("forecast_generated_at") or metadata.get("forecast_generated_at")
        forecast_end = predictions["last"].get("forecast_hour") or metadata.get("forecast_end")
        status, warnings = freshness_status(forecast_generated, forecast_end)

        lines = [
            "Forecast Refresh Status",
            "",
            time_context_note(time_context),
            f"Automation mode: {metadata.get('automation_mode', 'manual/local output')}",
            f"Last data update finished: {format_timestamp_for_timezone(metadata.get('update_finished_at_utc'), time_context)}",
            f"Forecast generated at: {format_timestamp_for_timezone(forecast_generated, time_context)}",
            f"Forecast age: {format_age_hours(forecast_generated)}",
            f"Forecast range: {format_timestamp_for_timezone(predictions['first'].get('forecast_hour'), time_context)} to {format_timestamp_for_timezone(forecast_end, time_context)}",
            f"Latest feature hour: {format_timestamp_for_timezone(hourly['last'].get('hour'), time_context)}",
            f"Latest raw transaction timestamp: {format_timestamp_for_timezone(metadata.get('latest_iso_utc'), time_context)}",
            f"Recent raw rows collected by automation: {format_count(metadata.get('recent_raw_rows_collected'))}",
            f"Known full raw rows: {format_count(metadata.get('final_rows'))}",
            f"Freshness: {status}",
            "",
            "Telegram handlers are read-only. Data collection, feature refresh, forecasting, charts, and deploys run in the scheduled GitHub Actions pipeline.",
        ]
        if warnings:
            lines.extend(["", *[f"Warning: {warning}" for warning in warnings]])
        return "\n".join(lines)

    def besttime(self, time_context: TimeContext | None = None) -> str:
        time_context = time_context or default_time_context()
        stats = load_forecast_stats(self.paths.predictions)

        lines = [
            "Best Time To Send TON",
            "",
            time_context_note(time_context),
            "Best hour",
            format_timestamp_for_timezone(stats.cheapest.get("forecast_hour"), time_context),
            "",
            "Predicted fee",
            f"{compact_ton(stats.cheapest_fee)}",
            f"{format_nanoton(stats.cheapest_fee)}",
            "",
            "Savings vs peak hour",
            f"{compact_ton(stats.difference)} lower",
            f"about {stats.percent:.1f}% cheaper",
            "",
            f"Lowest  [{ascii_bar(stats.cheapest_fee, stats.highest_fee)}] {compact_ton(stats.cheapest_fee)}",
            f"Highest [{ascii_bar(stats.highest_fee, stats.highest_fee)}] {compact_ton(stats.highest_fee)}",
            "",
            "This is the model's estimated cheapest hour in the next 24 hours. Actual network behavior can change quickly.",
        ]
        return "\n".join(lines)

    def model(self) -> str:
        metrics = read_json(self.paths.model_metrics)
        r2 = to_float(metrics.get("best_r2"))
        mae = to_float(metrics.get("best_mae"))
        rmse = to_float(metrics.get("best_rmse"))

        lines = [
            "Best Model",
            "",
            f"Model: {metrics.get('best_model_name', 'n/a')}",
            f"R2: {format_metric(r2)}",
            f"MAE: {format_nanoton(mae)}",
            f"RMSE: {format_nanoton(rmse)}",
            "",
            f"R2: the model explains about {percent_from_r2(r2)} of the variation in next-hour average fees. "
            "Fee movement remains noisy and difficult to predict when this value is low or negative.",
            f"MAE: on average, the prediction is off by about {format_nanoton(mae)}. This is usually the most "
            "practical error number for reading the dashboard.",
            f"RMSE: {format_nanoton(rmse)}. RMSE penalizes large misses more than MAE, so it rises when the model "
            "has occasional large errors.",
        ]
        return "\n".join(lines)

    def compare(self) -> str:
        rows = sorted_by_float(read_csv_rows(self.paths.model_comparison), "r2", reverse=True)
        if not rows:
            raise DashboardError("models/model_comparison.csv has no rows.")

        selected = rows[0]
        lines = [
            "Model Comparison",
            "",
            "Top chronological holdout models by R2:",
            "",
        ]
        for index, row in enumerate(rows[:6], start=1):
            lines.append(
                f"{index}. {row.get('model_name', 'n/a')} | "
                f"R2 {format_metric(row.get('r2'))} | "
                f"MAE {format_nanoton(row.get('mae'))} | "
                f"RMSE {format_nanoton(row.get('rmse'))}"
            )

        lines.extend(
            [
                "",
                f"Selected model: {selected.get('model_name', 'n/a')}. It is selected because it has the best "
                "chronological holdout R2 in the saved comparison while keeping MAE/RMSE competitive.",
                "Interpretation: the nonlinear boosted model performs better than linear alternatives, but the "
                "R2 is still modest, so it should be used as a directional forecasting tool.",
            ]
        )
        return "\n".join(lines)

    def backtest(self) -> str:
        rows = sorted_by_float(read_csv_rows(self.paths.rolling_backtest), "mean_r2", reverse=True)
        if not rows:
            raise DashboardError("models/rolling_backtest.csv has no rows.")

        best = rows[0]
        metrics = self._safe_json(self.paths.model_metrics)
        holdout_r2 = to_float(metrics.get("best_r2"))
        rolling_r2 = to_float(best.get("mean_r2"))

        lines = [
            "Rolling Backtest (in-sample)",
            "",
            "Label: in-sample backtest, not live operational accuracy.",
            f"Best model by mean R2: {best.get('model_name', 'n/a')}",
            f"Mean R2: {format_metric(rolling_r2)}",
            f"Mean MAE: {format_nanoton(best.get('mean_mae'))}",
            f"Mean RMSE: {format_nanoton(best.get('mean_rmse'))}",
            f"Folds: {format_count(best.get('folds'))}",
            "",
            "Top rolling models:",
            "",
        ]
        for index, row in enumerate(rows[:5], start=1):
            lines.append(
                f"{index}. {row.get('model_name', 'n/a')} | "
                f"mean R2 {format_metric(row.get('mean_r2'))} | "
                f"mean MAE {format_nanoton(row.get('mean_mae'))}"
            )

        lines.extend(
            [
                "",
                "Why this matters: rolling backtest checks whether the model works across multiple time windows "
                "instead of only one train/test split.",
            ]
        )
        if holdout_r2 is not None and rolling_r2 is not None and rolling_r2 < holdout_r2 / 2:
            lines.append(
                "Interpretation: rolling R2 is much lower than holdout R2, so performance is not stable "
                "across all time periods."
            )
        else:
            lines.append(
                "Interpretation: compare rolling metrics with holdout metrics before relying on the forecast; "
                "higher consistency across folds means a more reliable signal."
            )
        return "\n".join(lines)

    def accuracy(self) -> str:
        metrics = read_json(self.paths.operational_metrics)
        status = str(metrics.get("status", "n/a"))
        reconciled = metrics.get("reconciled_rows")
        distinct_origins = metrics.get("distinct_origins")
        min_stable_origins = metrics.get("min_stable_origins")
        pending = metrics.get("pending_rows")
        overall = metrics.get("overall") if isinstance(metrics.get("overall"), dict) else {}
        one_step = metrics.get("one_step") if isinstance(metrics.get("one_step"), dict) else {}
        by_horizon = metrics.get("by_horizon") if isinstance(metrics.get("by_horizon"), dict) else {}

        lines = [
            "Operational (live) Accuracy",
            "",
            "Measures forecasts after they were published. This is separate from in-sample backtests.",
            f"Status: {status}",
            f"Reconciled rows: {format_count(reconciled)}",
            f"Distinct origins: {format_count(distinct_origins)} / {format_count(min_stable_origins)}",
            f"Pending rows: {format_count(pending)}",
            f"Generated at: {format_timestamp(metrics.get('generated_at_utc'))}",
            "",
        ]
        if status == "accumulating":
            lines.extend([f"아직 누적 중(origins={format_count(distinct_origins)}).", ""])

        lines.extend(
            [
                "Overall:",
                format_operational_metric("overall", overall),
                "",
                "1-step apples-to-apples:",
                format_operational_metric("horizon=1h", one_step),
                "",
                "By horizon:",
            ]
        )
        if by_horizon:
            for horizon, values in sorted(by_horizon.items(), key=lambda item: to_int(item[0], 0) or 0):
                label = f"{horizon}h"
                if isinstance(values, dict):
                    lines.append(format_operational_metric(label, values))
        else:
            lines.append("n/a")
        return "\n".join(lines)

    def quality(self, time_context: TimeContext | None = None) -> str:
        time_context = time_context or default_time_context()
        metadata = self._metadata()
        hourly = read_csv_overview(self.paths.hourly_features)

        limit_hits = metadata.get("windows_with_limit_hits")
        limit = metadata.get("limit")
        max_pages = metadata.get("max_pages_per_window")

        lines = [
            "Data Quality And Limitations",
            "",
            time_context_note(time_context),
            f"Raw rows from metadata: {format_count(metadata.get('final_rows'))}",
            f"Hourly feature rows: {format_count(hourly['rows'])}",
            f"Feature range: {format_timestamp_for_timezone(hourly['first'].get('hour'), time_context)} to {format_timestamp_for_timezone(hourly['last'].get('hour'), time_context)}",
            f"Latest raw transaction timestamp: {format_timestamp_for_timezone(metadata.get('latest_iso_utc'), time_context)}",
            "Duplicate policy: raw transactions are de-duplicated by hash + lt.",
            f"API page-limit hits: {format_count(limit_hits)} windows hit the configured page limit.",
            f"Collection page settings: limit={format_count(limit)}, max_pages_per_window={format_count(max_pages)}",
            "",
            "Interpretation: tx_count and unique_accounts are useful sampled activity features, but they may not "
            "represent full-chain transaction volume when page limits are hit.",
            "Forecast reliability: the best model has positive R2, but the value is low. Use the forecast as "
            "a directional signal, not a production-grade guarantee.",
        ]
        return "\n".join(lines)

    def timezone(self, time_context: TimeContext | None = None) -> str:
        time_context = time_context or default_time_context()
        return "\n".join(
            [
                "Timezone Display",
                "",
                time_context_note(time_context),
                "",
                "Telegram messages do not include the user's exact device timezone. The bot estimates from Telegram language when possible and falls back to UTC when it cannot infer a reliable timezone.",
                "",
                "Override examples:",
                "/forecast Asia/Seoul",
                "/besttime America/New_York",
                "/status Europe/London",
                "",
                "Use IANA timezone names such as Asia/Seoul, America/Los_Angeles, Europe/Paris, or UTC.",
            ]
        )

    def charts(self) -> str:
        load_forecast_stats(self.paths.predictions)
        if not self.paths.figures_dir.exists():
            raise DashboardError(f"Missing directory: {relative(self.paths.figures_dir)}")

        files = sorted(
            path
            for path in self.paths.figures_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".svg", ".png", ".jpg", ".jpeg"}
        )
        if not files:
            return "No generated chart files were found in docs/figures/."

        image_files = [path for path in files if path.suffix.lower() in {".png", ".jpg", ".jpeg"}]
        lines = [
            "Generated Charts",
            "",
            "Available chart files:",
            "",
        ]
        for path in files:
            description = CHART_DESCRIPTIONS.get(path.name, "Generated project chart.")
            lines.append(f"- {path.name}: {description}")

        if image_files:
            lines.extend(
                [
                    "",
                    "`/forecast` sends the Telegram-ready PNG chart directly. SVG files are listed here for project diagnostics.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "All current charts are SVG files. This bot lists them instead of sending files because "
                    "Telegram does not reliably render SVG as chart previews without a conversion dependency.",
                ]
            )
        return "\n".join(lines)

    def _metadata(self) -> dict[str, Any]:
        if self.paths.last_updated.exists():
            return read_json(self.paths.last_updated)
        if self.paths.collection_metadata.exists():
            return read_json(self.paths.collection_metadata)
        raise DashboardError(
            f"Missing metadata files: {relative(self.paths.last_updated)} and "
            f"{relative(self.paths.collection_metadata)}"
        )

    def _safe_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return read_json(path)

    def _latest_feature_hour(self) -> str:
        hourly = read_csv_overview(self.paths.hourly_features)
        return hourly["last"].get("hour", "")


def format_count(value: Any) -> str:
    numeric = to_int(value)
    if numeric is None:
        return "n/a"
    return f"{numeric:,}"


def format_hour(value: Any, context: TimeContext | None = None) -> str:
    context = context or default_time_context()
    return format_timestamp_for_timezone(value, context)


def format_operational_metric(label: str, values: dict[str, Any]) -> str:
    return (
        f"{label}: n={format_count(values.get('n'))}, "
        f"origins={format_count(values.get('distinct_origins'))}, "
        f"MAE={format_nanoton(values.get('mae'))}, "
        f"MAPE={format_metric(values.get('mape'), 2)}%, "
        f"directional={format_metric(values.get('directional_accuracy'), 4)}, "
        f"persistence_skill={format_metric(values.get('skill_score'), 4)}, "
        f"seasonal_skill={format_metric(values.get('seasonal_naive_24h_skill_score'), 4)}, "
        f"rolling_skill={format_metric(values.get('rolling_mean_6h_skill_score'), 4)}"
    )


class TelegramClient:
    def __init__(self, token: str, request_timeout: int = 30) -> None:
        self.token = token
        self.request_timeout = request_timeout
        self.session = requests.Session()

    def request(self, method: str, **payload: Any) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            response = self.session.post(url, data=payload, timeout=self.request_timeout)
        except requests.RequestException as exc:
            raise RuntimeError(f"Telegram request failed for {method}: {redact_token(str(exc), self.token)}") from exc

        if response.status_code >= 400:
            raise RuntimeError(f"Telegram API returned HTTP {response.status_code} for {method}: {response.text[:300]}")

        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API returned ok=false for {method}: {str(data)[:300]}")
        return data

    def get_updates(self, offset: int | None, timeout: int = 50) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            payload["offset"] = offset
        data = self.request("getUpdates", **payload)
        return data.get("result", [])

    def send_message(self, chat_id: int, text: str) -> None:
        for chunk in split_message(text):
            self.request("sendMessage", chat_id=chat_id, text=chunk, disable_web_page_preview=True)

    def send_photo(self, chat_id: int, photo_path: Path, caption: str | None = None) -> None:
        if not photo_path.exists():
            logger.warning("Forecast chart image is missing: %s", photo_path)
            return

        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        payload: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            payload["caption"] = caption
        try:
            with photo_path.open("rb") as handle:
                response = self.session.post(
                    url,
                    data=payload,
                    files={"photo": (photo_path.name, handle, "image/png")},
                    timeout=self.request_timeout,
                )
        except requests.RequestException as exc:
            raise RuntimeError(f"Telegram photo upload failed: {redact_token(str(exc), self.token)}") from exc

        if response.status_code >= 400:
            raise RuntimeError(f"Telegram API returned HTTP {response.status_code} for sendPhoto: {response.text[:300]}")

        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API returned ok=false for sendPhoto: {str(data)[:300]}")


def split_message(text: str) -> list[str]:
    if len(text) <= MAX_TELEGRAM_MESSAGE_LENGTH:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for line in text.splitlines():
        additional_length = len(line) + 1
        if current and current_length + additional_length > MAX_TELEGRAM_MESSAGE_LENGTH:
            chunks.append("\n".join(current))
            current = []
            current_length = 0
        current.append(line)
        current_length += additional_length
    if current:
        chunks.append("\n".join(current))
    return chunks


def redact_token(text: str, token: str | None) -> str:
    if not token:
        return text
    return text.replace(token, "[redacted-token]")


def command_name(text: str) -> str:
    first_token = text.strip().split(maxsplit=1)[0].lower()
    return first_token.split("@", 1)[0]


def build_handlers(dashboard: Dashboard) -> dict[str, Callable[[TimeContext], str]]:
    return {
        "/start": lambda _time_context: dashboard.start(),
        "/help": lambda _time_context: dashboard.help(),
        "/summary": dashboard.summary,
        "/forecast": dashboard.forecast,
        "/status": dashboard.status,
        "/besttime": dashboard.besttime,
        "/timezone": dashboard.timezone,
        "/model": lambda _time_context: dashboard.model(),
        "/compare": lambda _time_context: dashboard.compare(),
        "/backtest": lambda _time_context: dashboard.backtest(),
        "/accuracy": lambda _time_context: dashboard.accuracy(),
        "/quality": dashboard.quality,
        "/charts": lambda _time_context: dashboard.charts(),
    }


def handle_message(message: dict[str, Any], handlers: dict[str, Callable[[TimeContext], str]]) -> str | None:
    text = message.get("text")
    if not isinstance(text, str) or not text.strip().startswith("/"):
        return None

    handler = handlers.get(command_name(text))
    if handler is None:
        return "Unknown command. Use /help to see available dashboard commands."

    try:
        return handler(resolve_time_context(message))
    except DashboardError as exc:
        return f"Dashboard data is not available yet: {exc}"
    except Exception:
        logger.exception("Unexpected command handler error")
        return "Unexpected dashboard error. Check the bot logs on the host machine."


def run_polling(client: TelegramClient, dashboard: Dashboard, poll_timeout: int) -> None:
    handlers = build_handlers(dashboard)
    offset: int | None = None
    logger.info("TON fee Telegram dashboard is running.")

    while True:
        try:
            updates = client.get_updates(offset=offset, timeout=poll_timeout)
        except Exception as exc:
            logger.error("Polling failed: %s", redact_token(str(exc), client.token))
            time.sleep(5)
            continue

        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1

            message = update.get("message")
            if not isinstance(message, dict):
                continue
            chat = message.get("chat")
            if not isinstance(chat, dict) or "id" not in chat:
                continue

            response = handle_message(message, handlers)
            if response is None:
                continue

            try:
                client.send_message(chat_id=chat["id"], text=response)
                if command_name(message.get("text", "")) == "/forecast":
                    client.send_photo(
                        chat_id=chat["id"],
                        photo_path=dashboard.paths.figures_dir / "forecast_next_24h.png",
                        caption="24-hour forecast chart",
                    )
            except Exception as exc:
                logger.error("sendMessage failed: %s", redact_token(str(exc), client.token))


def validate_dashboard(dashboard: Dashboard) -> int:
    checks = [
        ("/start", dashboard.start),
        ("/help", dashboard.help),
        ("/summary", dashboard.summary),
        ("/forecast", dashboard.forecast),
        ("/status", dashboard.status),
        ("/besttime", dashboard.besttime),
        ("/timezone", dashboard.timezone),
        ("/model", dashboard.model),
        ("/compare", dashboard.compare),
        ("/backtest", dashboard.backtest),
        ("/accuracy", dashboard.accuracy),
        ("/quality", dashboard.quality),
        ("/charts", dashboard.charts),
    ]

    failures = 0
    for name, handler in checks:
        try:
            text = handler()
        except Exception as exc:
            failures += 1
            print(f"{name}: FAIL - {exc}")
            continue
        print(f"{name}: OK ({len(split_message(text))} Telegram message chunk(s), {len(text)} characters)")

    if failures:
        print(f"Validation failed: {failures} command(s) could not be rendered.")
        return 1
    print("Validation OK: dashboard commands rendered from existing output files.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT), help="TON fee prediction project root.")
    parser.add_argument("--validate", action="store_true", help="Render dashboard commands locally without Telegram.")
    parser.add_argument("--poll-timeout", type=int, default=50, help="Telegram long-poll timeout in seconds.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    paths = ProjectPaths(root=Path(args.project_root).resolve())
    dashboard = Dashboard(paths)

    if args.validate:
        return validate_dashboard(dashboard)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN is not set. Refusing to start the Telegram bot.", file=sys.stderr)
        return 2

    poll_timeout = max(1, int(args.poll_timeout))
    client = TelegramClient(token=token)
    run_polling(client, dashboard, poll_timeout=poll_timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

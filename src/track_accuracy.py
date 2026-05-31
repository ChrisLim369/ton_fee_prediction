#!/usr/bin/env python3
"""Track operational accuracy for forecasts that were published before outcomes were known."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from schema import resolve_path
except ModuleNotFoundError:  # pragma: no cover - supports importing as src.track_accuracy in tests.
    from src.schema import resolve_path

PREDICTION_COLUMNS = [
    "forecast_generated_at",
    "forecast_hour",
    "horizon_hours",
    "predicted_avg_total_fee",
    "predicted_avg_total_fee_ton",
    "model_name",
    "model_trained_at_utc",
]
LOG_COLUMNS = [*PREDICTION_COLUMNS, "last_observed_hour", "last_observed_fee"]
ACCURACY_COLUMNS = [
    "forecast_generated_at",
    "forecast_hour",
    "horizon_hours",
    "model_name",
    "predicted_avg_total_fee",
    "actual_avg_total_fee",
    "error",
    "absolute_error",
    "pct_error",
    "last_observed_fee",
    "persistence_pred",
    "persistence_absolute_error",
    "direction_correct",
    "actual_is_capped",
]
DEDUP_COLUMNS = ["forecast_generated_at", "forecast_hour", "horizon_hours"]
MIN_STABLE_N = 8
EPSILON = 1e-12


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_utc(value: Any) -> str:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def read_csv_or_empty(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path)


def load_predictions(path: Path) -> pd.DataFrame:
    predictions = pd.read_csv(path)
    missing = [column for column in PREDICTION_COLUMNS if column not in predictions.columns]
    if missing:
        raise ValueError(f"predictions.csv is missing required columns: {missing}")
    return predictions[PREDICTION_COLUMNS].copy()


def load_hourly(path: Path) -> pd.DataFrame:
    hourly = pd.read_csv(path)
    missing = [column for column in ["hour", "avg_total_fee"] if column not in hourly.columns]
    if missing:
        raise ValueError(f"hourly_features.csv is missing required columns: {missing}")
    if "is_capped_hour" not in hourly.columns:
        hourly["is_capped_hour"] = 0
    hourly = hourly.copy()
    hourly["hour_dt"] = pd.to_datetime(hourly["hour"], utc=True, errors="coerce")
    hourly["avg_total_fee"] = pd.to_numeric(hourly["avg_total_fee"], errors="coerce")
    hourly["is_capped_hour"] = pd.to_numeric(hourly["is_capped_hour"], errors="coerce").fillna(0).astype(int)
    hourly = hourly.dropna(subset=["hour_dt", "avg_total_fee"]).sort_values("hour_dt").reset_index(drop=True)
    if hourly.empty:
        raise ValueError("hourly_features.csv has no usable actual avg_total_fee rows")
    return hourly


def latest_observed_at(hourly: pd.DataFrame, generated_at: Any) -> tuple[str, float]:
    generated_dt = pd.to_datetime(generated_at, utc=True, errors="coerce")
    eligible = hourly
    if not pd.isna(generated_dt):
        bounded = hourly[hourly["hour_dt"] <= generated_dt]
        if not bounded.empty:
            eligible = bounded
    row = eligible.iloc[-1]
    return iso_utc(row["hour_dt"]), float(row["avg_total_fee"])


def append_forecast_log(predictions_path: Path, hourly_path: Path, log_path: Path) -> dict[str, int]:
    predictions = load_predictions(predictions_path)
    hourly = load_hourly(hourly_path)
    log = read_csv_or_empty(log_path, LOG_COLUMNS)

    anchors: dict[str, tuple[str, float]] = {}
    new_rows = predictions.copy()
    for generated_at in new_rows["forecast_generated_at"].drop_duplicates():
        anchors[str(generated_at)] = latest_observed_at(hourly, generated_at)

    new_rows["last_observed_hour"] = new_rows["forecast_generated_at"].map(lambda value: anchors[str(value)][0])
    new_rows["last_observed_fee"] = new_rows["forecast_generated_at"].map(lambda value: anchors[str(value)][1])

    combined = pd.concat([log.reindex(columns=LOG_COLUMNS), new_rows.reindex(columns=LOG_COLUMNS)], ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=DEDUP_COLUMNS, keep="first").sort_values(
        ["forecast_generated_at", "horizon_hours", "forecast_hour"]
    )
    combined.to_csv(log_path, index=False)
    return {
        "input_rows": int(len(predictions)),
        "log_rows": int(len(combined)),
        "new_rows": int(before - len(log)),
        "deduped_rows": int(before - len(combined)),
    }


def sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def reconciled_rows(log: pd.DataFrame, hourly: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if log.empty:
        return pd.DataFrame(columns=ACCURACY_COLUMNS), 0

    prepared = log.reindex(columns=LOG_COLUMNS).copy()
    prepared["forecast_hour_dt"] = pd.to_datetime(prepared["forecast_hour"], utc=True, errors="coerce")
    prepared["predicted_avg_total_fee"] = pd.to_numeric(prepared["predicted_avg_total_fee"], errors="coerce")
    prepared["last_observed_fee"] = pd.to_numeric(prepared["last_observed_fee"], errors="coerce")
    actuals = hourly[["hour_dt", "avg_total_fee", "is_capped_hour"]].rename(
        columns={"hour_dt": "forecast_hour_dt", "avg_total_fee": "actual_avg_total_fee"}
    )
    merged = prepared.merge(actuals, how="left", on="forecast_hour_dt")
    pending_rows = int(merged["actual_avg_total_fee"].isna().sum())
    merged = merged.dropna(subset=["actual_avg_total_fee", "predicted_avg_total_fee", "last_observed_fee"]).copy()
    if merged.empty:
        return pd.DataFrame(columns=ACCURACY_COLUMNS), pending_rows

    merged["actual_avg_total_fee"] = pd.to_numeric(merged["actual_avg_total_fee"], errors="coerce")
    merged["error"] = merged["predicted_avg_total_fee"] - merged["actual_avg_total_fee"]
    merged["absolute_error"] = merged["error"].abs()
    merged["pct_error"] = merged.apply(
        lambda row: row["absolute_error"] / abs(row["actual_avg_total_fee"]) * 100
        if abs(row["actual_avg_total_fee"]) > EPSILON
        else math.nan,
        axis=1,
    )
    merged["persistence_pred"] = merged["last_observed_fee"]
    merged["persistence_absolute_error"] = (merged["persistence_pred"] - merged["actual_avg_total_fee"]).abs()
    merged["direction_correct"] = merged.apply(
        lambda row: sign(row["predicted_avg_total_fee"] - row["last_observed_fee"])
        == sign(row["actual_avg_total_fee"] - row["last_observed_fee"]),
        axis=1,
    )
    merged["actual_is_capped"] = pd.to_numeric(merged["is_capped_hour"], errors="coerce").fillna(0).astype(int)

    result = merged.reindex(columns=ACCURACY_COLUMNS)
    return result, pending_rows


def maybe_number(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(value)


def metric_summary(rows: pd.DataFrame) -> dict[str, Any]:
    n = int(len(rows))
    if n == 0:
        return {
            "n": 0,
            "mae": None,
            "rmse": None,
            "mape": None,
            "r2": None,
            "directional_accuracy": None,
            "persistence_mae": None,
            "skill_score": None,
        }

    mae = float(rows["absolute_error"].mean())
    rmse = float(math.sqrt((rows["error"] ** 2).mean()))
    directional_accuracy = float(rows["direction_correct"].astype(bool).mean())
    persistence_mae = float(rows["persistence_absolute_error"].mean())

    mape: float | None = None
    r2: float | None = None
    skill_score: float | None = None
    if n >= MIN_STABLE_N:
        valid_pct = rows["pct_error"].dropna()
        if not valid_pct.empty:
            mape = float(valid_pct.mean())
        ss_res = float((rows["error"] ** 2).sum())
        actual = rows["actual_avg_total_fee"]
        ss_tot = float(((actual - actual.mean()) ** 2).sum())
        if ss_tot > EPSILON:
            r2 = 1 - ss_res / ss_tot
        if persistence_mae > EPSILON:
            skill_score = 1 - mae / persistence_mae

    return {
        "n": n,
        "mae": maybe_number(mae),
        "rmse": maybe_number(rmse),
        "mape": maybe_number(mape),
        "r2": maybe_number(r2),
        "directional_accuracy": maybe_number(directional_accuracy),
        "persistence_mae": maybe_number(persistence_mae),
        "skill_score": maybe_number(skill_score),
    }


def build_metrics(accuracy: pd.DataFrame, pending_rows: int) -> dict[str, Any]:
    reconciled_count = int(len(accuracy))
    by_horizon = {
        str(int(horizon)): metric_summary(group)
        for horizon, group in accuracy.groupby(pd.to_numeric(accuracy["horizon_hours"], errors="coerce"))
        if not pd.isna(horizon)
    }
    clean = accuracy[accuracy["actual_is_capped"] == 0] if not accuracy.empty else accuracy
    capped = accuracy[accuracy["actual_is_capped"] == 1] if not accuracy.empty else accuracy
    return {
        "generated_at_utc": utc_now_iso(),
        "status": "active" if reconciled_count >= MIN_STABLE_N else "accumulating",
        "reconciled_rows": reconciled_count,
        "pending_rows": int(pending_rows),
        "overall": metric_summary(accuracy),
        "by_horizon": by_horizon,
        "by_capped": {
            "clean": metric_summary(clean),
            "capped": metric_summary(capped),
        },
    }


def format_report_value(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return str(value)


def metric_table(title: str, rows: list[tuple[str, dict[str, Any]]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not rows:
        lines.append("| none | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")
    for label, metrics in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    format_report_value(metrics.get("n"), 0),
                    format_report_value(metrics.get("mae"), 2),
                    format_report_value(metrics.get("rmse"), 2),
                    format_report_value(metrics.get("mape"), 2),
                    format_report_value(metrics.get("r2"), 4),
                    format_report_value(metrics.get("directional_accuracy"), 4),
                    format_report_value(metrics.get("persistence_mae"), 2),
                    format_report_value(metrics.get("skill_score"), 4),
                ]
            )
            + " |"
        )
    return lines


def write_report(path: Path, metrics: dict[str, Any]) -> None:
    status = str(metrics["status"])
    lines = [
        "# Operational Forecast Accuracy",
        "",
        "This report measures operational live accuracy from forecasts that were published before outcomes were known. "
        "It is separate from in-sample backtests such as `actual_vs_predicted.csv` and `models/rolling_backtest.csv`.",
        "",
        f"Generated at: {metrics['generated_at_utc']}",
        f"Status: {status}",
        f"Reconciled rows: {metrics['reconciled_rows']}",
        f"Pending rows: {metrics['pending_rows']}",
        "",
    ]
    if status == "accumulating":
        lines.extend(
            [
                f"The live ledger is still accumulating enough realized forecasts for stable metrics "
                f"(reconciled n={metrics['reconciled_rows']}).",
                "",
            ]
        )
    lines.extend(metric_table("Overall", [("overall", metrics["overall"])]))
    lines.extend([""])
    horizon_rows = sorted(metrics["by_horizon"].items(), key=lambda item: int(item[0]))
    lines.extend(metric_table("By Horizon", [(f"{label}h", value) for label, value in horizon_rows]))
    lines.extend([""])
    capped = metrics["by_capped"]
    lines.extend(metric_table("By Actual Cap Status", [("clean", capped["clean"]), ("capped", capped["capped"])]))
    lines.extend(
        [
            "",
            "Positive skill score means the model beat the persistence baseline anchored at the last observed fee when "
            "the forecast was issued. `N/A` is used for small samples or zero denominators.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def reconcile_and_report(
    log_path: Path,
    hourly_path: Path,
    accuracy_path: Path,
    metrics_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    log = read_csv_or_empty(log_path, LOG_COLUMNS)
    hourly = load_hourly(hourly_path)
    accuracy, pending_rows = reconciled_rows(log, hourly)
    accuracy.to_csv(accuracy_path, index=False)
    metrics = build_metrics(accuracy, pending_rows)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    write_report(report_path, metrics)
    return metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--append", action="store_true", help="Append the current predictions.csv to forecast_log.csv.")
    parser.add_argument("--reconcile", action="store_true", help="Reconcile forecast_log.csv with hourly_features.csv.")
    parser.add_argument("--predictions", default="predictions.csv")
    parser.add_argument("--hourly", default="hourly_features.csv")
    parser.add_argument("--log", default="forecast_log.csv")
    parser.add_argument("--accuracy", default="forecast_accuracy.csv")
    parser.add_argument("--metrics", default="models/operational_metrics.json")
    parser.add_argument("--report", default="docs/operational_accuracy.md")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_append = args.append or not args.reconcile
    run_reconcile = args.reconcile or not args.append

    result: dict[str, Any] = {}
    predictions_path = resolve_path(args.predictions)
    hourly_path = resolve_path(args.hourly)
    log_path = resolve_path(args.log)
    accuracy_path = resolve_path(args.accuracy)
    metrics_path = resolve_path(args.metrics)
    report_path = resolve_path(args.report)

    if run_append:
        result["append"] = append_forecast_log(predictions_path, hourly_path, log_path)
    if run_reconcile:
        metrics = reconcile_and_report(log_path, hourly_path, accuracy_path, metrics_path, report_path)
        result["reconcile"] = {
            "status": metrics["status"],
            "reconciled_rows": metrics["reconciled_rows"],
            "pending_rows": metrics["pending_rows"],
            "metrics": str(metrics_path),
            "report": str(report_path),
        }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

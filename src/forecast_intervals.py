#!/usr/bin/env python3
"""Attach empirical replay-based prediction intervals to saved forecasts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__ == "src":
    from .generate_forecast import load_model, numeric_hourly, recursive_forecast
    from .schema import MODEL_FEATURE_COLUMNS, resolve_path
else:
    from generate_forecast import load_model, numeric_hourly, recursive_forecast
    from schema import MODEL_FEATURE_COLUMNS, resolve_path


MIN_RESIDUALS_PER_HORIZON = 20


def parse_levels(value: str) -> list[int]:
    levels = [int(part.strip()) for part in value.split(",") if part.strip()]
    for level in levels:
        if level <= 0 or level >= 100:
            raise ValueError("--levels entries must be between 1 and 99")
    return levels


def central_quantiles(level: int) -> tuple[float, float]:
    tail = (100 - level) / 200
    return tail, 1 - tail


def replay_residuals(
    hourly: pd.DataFrame,
    model: dict[str, Any],
    horizon_hours: int,
    step_hours: int,
    min_history_hours: int,
) -> dict[int, list[float]]:
    actual_by_hour = hourly.set_index("hour_dt")["avg_total_fee"].astype(float).to_dict()
    last_anchor = hourly["hour_dt"].max() - pd.Timedelta(hours=horizon_hours)
    residuals: dict[int, list[float]] = {horizon: [] for horizon in range(1, horizon_hours + 1)}

    generated_at = datetime.now(UTC).replace(microsecond=0)
    for anchor_index in range(min_history_hours - 1, len(hourly), step_hours):
        anchor_hour = hourly.iloc[anchor_index]["hour_dt"]
        if anchor_hour > last_anchor:
            break
        history = hourly.iloc[: anchor_index + 1].copy()
        forecasts = recursive_forecast(history, model, horizon_hours, generated_at)
        for forecast in forecasts:
            forecast_hour = pd.Timestamp(forecast["forecast_hour"])
            actual = actual_by_hour.get(forecast_hour)
            if actual is None:
                continue
            horizon = int(forecast["horizon_hours"])
            residuals[horizon].append(float(actual) - float(forecast["predicted_avg_total_fee"]))
    return residuals


def summarize_intervals(
    residuals: dict[int, list[float]],
    levels: list[int],
    min_residuals: int = MIN_RESIDUALS_PER_HORIZON,
) -> dict[str, dict[str, Any]]:
    by_horizon: dict[str, dict[str, Any]] = {}
    for horizon, values in sorted(residuals.items()):
        arr = np.asarray(values, dtype=float)
        entry: dict[str, Any] = {"n": int(len(arr))}
        for level in levels:
            level_key = str(level)
            if len(arr) < min_residuals:
                entry[level_key] = {"width_lo": None, "width_hi": None}
                continue
            lower_q, upper_q = central_quantiles(level)
            raw_lo = float(np.quantile(arr, lower_q))
            raw_hi = float(np.quantile(arr, upper_q))
            width_lo = min(raw_lo, 0.0)
            width_hi = max(raw_hi, 0.0)
            entry[level_key] = {"width_lo": width_lo, "width_hi": width_hi}
        by_horizon[str(horizon)] = entry
    return by_horizon


def calibration_out_of_sample(
    residuals: dict[int, list[float]],
    levels: list[int],
    fit_fraction: float = 0.7,
    min_residuals: int = MIN_RESIDUALS_PER_HORIZON,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_horizon: dict[str, dict[str, Any]] = {}
    overall_values: dict[int, list[tuple[np.ndarray, float, float]]] = {level: [] for level in levels}

    for horizon, values in sorted(residuals.items()):
        arr = np.asarray(values, dtype=float)
        split_index = int(len(arr) * fit_fraction)
        fit = arr[:split_index]
        check = arr[split_index:]
        entry: dict[str, Any] = {
            "calibration": {
                "method": "out_of_sample_chronological",
                "fit_fraction": fit_fraction,
                "fit_n": int(len(fit)),
                "check_n": int(len(check)),
            }
        }
        for level in levels:
            level_key = str(level)
            if len(fit) < min_residuals or len(check) < min_residuals:
                entry[level_key] = {"coverage_oos": None}
                continue
            lower_q, upper_q = central_quantiles(level)
            raw_lo = float(np.quantile(fit, lower_q))
            raw_hi = float(np.quantile(fit, upper_q))
            width_lo = min(raw_lo, 0.0)
            width_hi = max(raw_hi, 0.0)
            coverage = float(np.mean((check >= width_lo) & (check <= width_hi)))
            entry[level_key] = {"coverage_oos": coverage}
            overall_values[level].append((check, width_lo, width_hi))
        by_horizon[str(horizon)] = entry

    overall: dict[str, dict[str, Any]] = {}
    for level, groups in overall_values.items():
        if not groups:
            overall[str(level)] = {"check_n": 0, "coverage_oos": None}
            continue
        covered = 0
        total = 0
        for check, width_lo, width_hi in groups:
            covered += int(np.sum((check >= width_lo) & (check <= width_hi)))
            total += int(len(check))
        overall[str(level)] = {"check_n": total, "coverage_oos": float(covered / total) if total else None}
    return by_horizon, overall


def attach_calibration(
    by_horizon: dict[str, dict[str, Any]],
    calibration: dict[str, dict[str, Any]],
    levels: list[int],
) -> dict[str, dict[str, Any]]:
    output = json.loads(json.dumps(by_horizon))
    for horizon, horizon_calibration in calibration.items():
        entry = output.setdefault(horizon, {"n": 0})
        entry["calibration"] = horizon_calibration.get("calibration", {})
        for level in levels:
            level_key = str(level)
            level_entry = entry.setdefault(level_key, {})
            level_entry["coverage_oos"] = horizon_calibration.get(level_key, {}).get("coverage_oos")
    return output


def interval_columns(level: int) -> tuple[str, str, str, str]:
    return (
        f"predicted_avg_total_fee_lo{level}",
        f"predicted_avg_total_fee_hi{level}",
        f"predicted_avg_total_fee_lo{level}_ton",
        f"predicted_avg_total_fee_hi{level}_ton",
    )


def apply_intervals_to_predictions(
    predictions: pd.DataFrame,
    by_horizon: dict[str, dict[str, Any]],
    levels: list[int],
) -> pd.DataFrame:
    output = predictions.copy()
    for level in levels:
        lo_col, hi_col, lo_ton_col, hi_ton_col = interval_columns(level)
        output[lo_col] = np.nan
        output[hi_col] = np.nan
        output[lo_ton_col] = np.nan
        output[hi_ton_col] = np.nan

    point = pd.to_numeric(output["predicted_avg_total_fee"], errors="coerce")
    for index, row in output.iterrows():
        horizon = str(int(row["horizon_hours"]))
        horizon_entry = by_horizon.get(horizon, {})
        previous_lo = None
        previous_hi = None
        for level in sorted(levels):
            level_entry = horizon_entry.get(str(level)) if isinstance(horizon_entry, dict) else None
            if not isinstance(level_entry, dict):
                continue
            width_lo = level_entry.get("width_lo")
            width_hi = level_entry.get("width_hi")
            if width_lo is None or width_hi is None or pd.isna(point.iloc[index]):
                continue
            prediction = float(point.iloc[index])
            lower = min(prediction, max(0.0, prediction + float(width_lo)))
            upper = max(prediction, prediction + float(width_hi))
            if previous_lo is not None:
                lower = min(lower, previous_lo)
            if previous_hi is not None:
                upper = max(upper, previous_hi)
            lo_col, hi_col, lo_ton_col, hi_ton_col = interval_columns(level)
            output.at[index, lo_col] = lower
            output.at[index, hi_col] = upper
            output.at[index, lo_ton_col] = lower / 1_000_000_000
            output.at[index, hi_ton_col] = upper / 1_000_000_000
            previous_lo = lower
            previous_hi = upper
    return output


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Forecast Prediction Intervals",
        "",
        "These intervals are empirical in-sample estimates from historical recursive forecast replay residuals.",
        "They are not calibrated from live operational residuals yet.",
        "",
        "## Method",
        "",
        "- For each historical anchor, the saved best model is replayed recursively for 24 hours.",
        "- Residuals are grouped by forecast horizon.",
        "- 80% intervals use the horizon residual q10/q90; 50% intervals use q25/q75.",
        "- Fees are clamped at zero and interval rows are clipped so 80% contains 50% and the point forecast.",
        "",
        "## Limitations",
        "",
        "If the selected model is a naive baseline, these replay residuals are close to an unbiased empirical "
        "error sample.",
        "For trained models, the same checked-in history also informed training, so intervals may be "
        "optimistically narrow.",
        "Once S1 forecast_accuracy.csv has enough live residuals per horizon, recalibrate these bands from "
        "operational errors.",
        "",
        "## Calibration",
        "",
        "Out-of-sample calibration: quantiles are fit on earlier anchors, then coverage is measured on "
        "held-out later anchors.",
        f"Configuration: method={payload['calibration']['method']}, "
        f"fit_fraction={payload['calibration']['fit_fraction']}.",
        "Unlike in-sample quantile coverage, these observed values are not guaranteed to equal the nominal "
        "80% or 50%.",
        "",
        "| Horizon | total_n | check_n | 80% observed OOS | 50% observed OOS |",
        "|---:|---:|---:|---:|---:|",
    ]
    for horizon, values in payload["by_horizon"].items():
        calibration = values.get("calibration", {})
        lines.append(
            f"| h+{horizon} | {values['n']} | {calibration.get('check_n', 0)} | "
            f"{format_coverage(values.get('80', {}).get('coverage_oos'))} | "
            f"{format_coverage(values.get('50', {}).get('coverage_oos'))} |"
        )

    lines.extend(["", "## Overall Coverage", "", "| Nominal | Observed OOS | check_n |", "|---:|---:|---:|"])
    for level, values in payload["overall_coverage"].items():
        lines.append(
            f"| {level}% | {format_coverage(values.get('coverage_oos'))} | {values.get('check_n', 0)} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_coverage(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.1f}%"


def run(args: argparse.Namespace) -> dict[str, Any]:
    model_path = resolve_path(args.model)
    predictions_path = resolve_path(args.predictions)
    report_path = resolve_path(args.report)
    json_path = resolve_path(args.json)
    levels = parse_levels(args.levels)

    model = load_model(model_path)
    feature_columns = model.get("feature_columns", MODEL_FEATURE_COLUMNS)
    hourly = numeric_hourly(resolve_path(args.features), feature_columns)
    if hourly.empty:
        raise ValueError("hourly feature dataset is empty")

    residuals = replay_residuals(
        hourly=hourly,
        model=model,
        horizon_hours=args.horizon_hours,
        step_hours=args.step_hours,
        min_history_hours=args.min_history_hours,
    )
    interval_widths = summarize_intervals(residuals, levels)
    calibration_by_horizon, overall_coverage = calibration_out_of_sample(
        residuals=residuals,
        levels=levels,
        fit_fraction=args.calibration_fit_fraction,
    )
    by_horizon = attach_calibration(interval_widths, calibration_by_horizon, levels)

    predictions = pd.read_csv(predictions_path)
    predictions_with_intervals = apply_intervals_to_predictions(predictions, by_horizon, levels)
    predictions_with_intervals.to_csv(predictions_path, index=False)

    payload = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "method": "in_sample_replay",
        "levels": levels,
        "min_residuals_per_horizon": MIN_RESIDUALS_PER_HORIZON,
        "calibration": {
            "method": "out_of_sample_chronological",
            "fit_fraction": args.calibration_fit_fraction,
        },
        "by_horizon": by_horizon,
        "overall_coverage": overall_coverage,
        "limitations": [
            "Replay residuals are in-sample empirical intervals.",
            "Trained-model intervals may be optimistically narrow.",
            "Recalibrate with S1 operational residuals once forecast_accuracy.csv has enough rows.",
        ],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(report_path, payload)

    return {
        "status": "success",
        "method": payload["method"],
        "horizons": len(by_horizon),
        "predictions": str(predictions_path),
        "json": str(json_path),
        "report": str(report_path),
        "overall_coverage": overall_coverage,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", default="hourly_features.csv")
    parser.add_argument("--model", default="models/best_model.json")
    parser.add_argument("--predictions", default="predictions.csv")
    parser.add_argument("--report", default="docs/forecast_intervals.md")
    parser.add_argument("--json", default="models/forecast_intervals.json")
    parser.add_argument("--step-hours", type=int, default=1)
    parser.add_argument("--min-history-hours", type=int, default=168)
    parser.add_argument("--horizon-hours", type=int, default=24)
    parser.add_argument("--levels", default="80,50")
    parser.add_argument("--calibration-fit-fraction", type=float, default=0.7)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.step_hours < 1:
        raise ValueError("--step-hours must be at least 1")
    if args.min_history_hours < 1:
        raise ValueError("--min-history-hours must be at least 1")
    if args.horizon_hours < 1:
        raise ValueError("--horizon-hours must be at least 1")
    if not 0 < args.calibration_fit_fraction < 1:
        raise ValueError("--calibration-fit-fraction must be between 0 and 1")
    print(json.dumps(run(args), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

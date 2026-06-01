#!/usr/bin/env python3
"""Promote the horizon-validated rolling_mean_6h forecast model for serving."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from schema import MODEL_FEATURE_COLUMNS, resolve_path
except ModuleNotFoundError:
    from .schema import MODEL_FEATURE_COLUMNS, resolve_path

MODEL_NAME = "rolling_mean_6h"
SELECTED_BY = (
    "horizon-aware: rolling_mean_6h has the lowest 24h-average recursive MAE in both clean and "
    "recent regimes (see docs/horizon_forecast_experiment.md); shown R2/MAE are its 1-step holdout"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def comparison_row(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("model_name") == MODEL_NAME:
                return row
    raise ValueError(f"{MODEL_NAME} row not found in {path}")


def as_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def as_int(row: dict[str, str], key: str) -> int:
    return int(float(row[key]))


def last_24_fees(path: Path) -> list[float]:
    df = pd.read_csv(path)
    fees = pd.to_numeric(df["avg_total_fee"], errors="coerce").dropna().tail(24)
    if len(fees) < 24:
        raise ValueError(f"{path} has fewer than 24 non-null avg_total_fee values")
    return [float(value) for value in fees]


def model_metrics(row: dict[str, str]) -> dict[str, Any]:
    return {
        "mae": as_float(row, "mae"),
        "rmse": as_float(row, "rmse"),
        "r2": as_float(row, "r2"),
        "mape": as_float(row, "mape"),
        "directional_accuracy": as_float(row, "directional_accuracy"),
        "model_name": MODEL_NAME,
        "model_type": "naive",
        "target_transform": "none",
        "alpha": as_float(row, "alpha"),
        "train_rows": as_int(row, "train_rows"),
        "test_rows": as_int(row, "test_rows"),
    }


def promoted_model(
    existing_model: dict[str, Any],
    row: dict[str, str],
    history: list[float],
    trained_at_utc: str,
) -> dict[str, Any]:
    return {
        "model_name": MODEL_NAME,
        "model_type": "naive",
        "baseline_kind": MODEL_NAME,
        "target_column": existing_model.get("target_column", "target_next_hour_avg_fee"),
        "target_transform": "none",
        "feature_columns": existing_model.get("feature_columns", MODEL_FEATURE_COLUMNS),
        "trained_at_utc": trained_at_utc,
        "metrics": model_metrics(row),
        "naive_state": {"last_24_avg_total_fee": history},
    }


def trained_at(existing_model: dict[str, Any]) -> str:
    if existing_model.get("model_name") == MODEL_NAME and existing_model.get("baseline_kind") == MODEL_NAME:
        current = existing_model.get("trained_at_utc")
        if current:
            return str(current)
    return datetime.now(UTC).isoformat()


def promoted_metrics(existing_metrics: dict[str, Any], row: dict[str, str]) -> dict[str, Any]:
    output = dict(existing_metrics)
    output.update(
        {
            "best_model_name": MODEL_NAME,
            "best_r2": as_float(row, "r2"),
            "best_mae": as_float(row, "mae"),
            "best_rmse": as_float(row, "rmse"),
            "best_directional_accuracy": as_float(row, "directional_accuracy"),
            "selected_by": SELECTED_BY,
        }
    )
    return output


def promote(
    best_model_path: Path,
    model_metrics_path: Path,
    model_comparison_path: Path,
    hourly_features_path: Path,
) -> dict[str, Any]:
    existing_model = read_json(best_model_path)
    existing_metrics = read_json(model_metrics_path)
    row = comparison_row(model_comparison_path)
    history = last_24_fees(hourly_features_path)
    model = promoted_model(existing_model, row, history, trained_at(existing_model))
    metrics = promoted_metrics(existing_metrics, row)

    write_json(best_model_path, model)
    write_json(model_metrics_path, metrics)
    return {
        "best_model": str(best_model_path),
        "model_metrics": str(model_metrics_path),
        "model_name": MODEL_NAME,
        "history_rows": len(history),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--best-model", default="models/best_model.json")
    parser.add_argument("--model-metrics", default="models/model_metrics.json")
    parser.add_argument("--model-comparison", default="models/model_comparison.csv")
    parser.add_argument("--hourly-features", default="hourly_features.csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = promote(
        best_model_path=resolve_path(args.best_model),
        model_metrics_path=resolve_path(args.model_metrics),
        model_comparison_path=resolve_path(args.model_comparison),
        hourly_features_path=resolve_path(args.hourly_features),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

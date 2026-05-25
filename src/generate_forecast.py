#!/usr/bin/env python3
"""Generate a recursive next-24-hour TON fee forecast."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ton_pipeline import MODEL_FEATURE_COLUMNS, predict_with_model, resolve_path


FEE_DISTRIBUTION_COLUMNS = [
    "avg_total_fee",
    "median_total_fee",
    "p90_total_fee",
    "min_total_fee",
    "max_total_fee",
]


def load_model(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}. Run python src/train_model.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def numeric_hourly(path: Path, feature_columns: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["hour_dt"] = pd.to_datetime(df["hour"], utc=True)
    for column in feature_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.sort_values("hour_dt").reset_index(drop=True)


def typical_values(df: pd.DataFrame, feature_hour: pd.Timestamp, feature_columns: list[str]) -> dict[str, float]:
    same_hour = df[df["hour_of_day"] == feature_hour.hour]
    source = same_hour if len(same_hour) >= 3 else df
    medians = source[feature_columns].median(numeric_only=True).fillna(df[feature_columns].median(numeric_only=True))
    return {column: float(medians.get(column, 0.0)) for column in feature_columns}


def history_value(history: list[float], lag: int) -> float:
    if len(history) >= lag:
        return float(history[-lag])
    return float(history[0])


def rolling_mean(history: list[float], window: int) -> float:
    values = history[-window:] if len(history) >= window else history
    return float(np.mean(values))


def rolling_std(history: list[float], window: int) -> float:
    values = history[-window:] if len(history) >= window else history
    if len(values) < 2:
        return 0.0
    return float(np.std(values, ddof=1))


def synthetic_feature_row(
    df: pd.DataFrame,
    feature_hour: pd.Timestamp,
    history: list[float],
    feature_columns: list[str],
) -> dict[str, float]:
    row = typical_values(df, feature_hour, feature_columns)
    last_fee = float(history[-1])

    for column in FEE_DISTRIBUTION_COLUMNS:
        row[column] = last_fee
    row["std_total_fee"] = float(df["std_total_fee"].median()) if "std_total_fee" in df else 0.0

    row["hour_of_day"] = float(feature_hour.hour)
    row["day_of_week"] = float(feature_hour.dayofweek)
    row["is_weekend"] = 1.0 if feature_hour.dayofweek in {5, 6} else 0.0

    for lag in [1, 3, 6, 12, 24]:
        row[f"fee_lag_{lag}h"] = history_value(history, lag)

    for window in [3, 6, 12, 24]:
        row[f"rolling_avg_fee_{window}h"] = rolling_mean(history, window)
    for window in [6, 24]:
        row[f"rolling_std_fee_{window}h"] = rolling_std(history, window)

    for lag in [1, 3, 6, 12, 24]:
        row[f"fee_change_{lag}h"] = last_fee - history_value(history, lag)
    for lag in [1, 3, 6, 24]:
        row[f"p90_fee_change_{lag}h"] = last_fee - history_value(history, lag)
    row["same_hour_prev_day_fee"] = history_value(history, 24)
    row["hour_sin"] = float(np.sin(2 * np.pi * feature_hour.hour / 24))
    row["hour_cos"] = float(np.cos(2 * np.pi * feature_hour.hour / 24))
    row["day_sin"] = float(np.sin(2 * np.pi * feature_hour.dayofweek / 7))
    row["day_cos"] = float(np.cos(2 * np.pi * feature_hour.dayofweek / 7))

    return row


def generate(args: argparse.Namespace) -> dict[str, object]:
    features_path = resolve_path(args.features)
    model_path = resolve_path(args.model)
    output_path = resolve_path(args.output)

    model = load_model(model_path)
    feature_columns = model.get("feature_columns", MODEL_FEATURE_COLUMNS)
    df = numeric_hourly(features_path, feature_columns)
    if df.empty:
        raise ValueError("hourly feature dataset is empty")

    generated_at = datetime.now(UTC).replace(microsecond=0)
    last_hour = df["hour_dt"].max()
    history = df["avg_total_fee"].dropna().astype(float).tolist()
    if not history:
        raise ValueError("hourly feature dataset has no avg_total_fee values")

    forecasts: list[dict[str, object]] = []
    for horizon in range(1, args.horizon_hours + 1):
        forecast_hour = last_hour + pd.Timedelta(hours=horizon)
        feature_hour = forecast_hour - pd.Timedelta(hours=1)

        if horizon == 1:
            feature_row = df.iloc[-1][model["feature_columns"]].to_dict()
        else:
            feature_row = synthetic_feature_row(df, feature_hour, history, model["feature_columns"])

        prediction = predict_with_model(model, feature_row)
        history.append(prediction)

        forecasts.append(
            {
                "forecast_generated_at": generated_at.isoformat().replace("+00:00", "Z"),
                "forecast_hour": forecast_hour.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "horizon_hours": horizon,
                "predicted_avg_total_fee": prediction,
                "predicted_avg_total_fee_ton": prediction / 1_000_000_000,
                "model_name": model.get("model_name", model.get("model_type", "unknown")),
                "model_trained_at_utc": model.get("trained_at_utc"),
            }
        )

    forecast_df = pd.DataFrame(forecasts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    forecast_df.to_csv(output_path, index=False)

    return {
        "output": str(output_path),
        "rows": int(len(forecast_df)),
        "forecast_start": forecasts[0]["forecast_hour"],
        "forecast_end": forecasts[-1]["forecast_hour"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", default="hourly_features.csv")
    parser.add_argument("--model", default="models/best_model.json")
    parser.add_argument("--output", default="predictions.csv")
    parser.add_argument("--horizon-hours", type=int, default=24)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    if args.horizon_hours < 1:
        raise ValueError("--horizon-hours must be at least 1")
    print(json.dumps(generate(args), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

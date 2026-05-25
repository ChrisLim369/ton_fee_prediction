"""Naive baseline model helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .base import compute_metrics as compute_metrics


def naive_predictions(split: dict[str, Any], baseline_kind: str) -> np.ndarray:
    fee_history = split["fee_history"].reset_index(drop=True)
    predictions: list[float] = []
    for row_index in split["test_row_indices"]:
        if baseline_kind == "persistence":
            prediction = fee_history.iloc[row_index]
        elif baseline_kind == "seasonal_naive_24h":
            prediction = fee_history.iloc[row_index - 23] if row_index >= 23 else fee_history.iloc[0]
        elif baseline_kind == "rolling_mean_6h":
            start = max(0, row_index - 5)
            prediction = fee_history.iloc[start : row_index + 1].mean()
        else:
            raise ValueError(f"Unsupported naive baseline: {baseline_kind}")
        predictions.append(float(prediction))
    return np.maximum(0.0, np.array(predictions, dtype=float))


def fit_naive_model(
    split: dict[str, Any],
    feature_columns: list[str],
    target_column: str,
    model_name: str,
    baseline_kind: str,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float], pd.DataFrame]:
    predictions = naive_predictions(split, baseline_kind)
    metrics = compute_metrics(split["y_test"], predictions, split["test_current_fee"])
    metrics.update(
        {
            "model_name": model_name,
            "model_type": "naive",
            "target_transform": "none",
            "alpha": 0.0,
            "train_rows": split["train_rows"],
            "test_rows": split["test_rows"],
        }
    )

    residuals = split["y_test"] - predictions
    actual_vs_predicted = pd.DataFrame(
        {
            "hour": split["test_hours"],
            "actual_next_hour_avg_fee": split["y_test"],
            "predicted_next_hour_avg_fee": predictions,
            "error": residuals,
            "absolute_error": np.abs(residuals),
            "model_name": model_name,
        }
    )
    model = {
        "model_name": model_name,
        "model_type": "naive",
        "baseline_kind": baseline_kind,
        "target_column": target_column,
        "target_transform": "none",
        "feature_columns": feature_columns,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "metrics": metrics,
        "naive_state": {
            "last_24_avg_total_fee": split["fee_history"].dropna().astype(float).tail(24).tolist(),
        },
    }
    importance_table = pd.DataFrame(
        columns=[
            "model_name",
            "feature",
            "coefficient_scaled",
            "abs_coefficient_scaled",
            "tree_importance",
        ]
    )
    return model, importance_table, metrics, actual_vs_predicted



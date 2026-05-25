"""Linear regression model helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .base import compute_metrics as compute_metrics
from .base import split_model_data as split_model_data

if __package__ == "models":
    from schema import MODEL_FEATURE_COLUMNS as MODEL_FEATURE_COLUMNS
else:
    from ..schema import MODEL_FEATURE_COLUMNS as MODEL_FEATURE_COLUMNS


def regression_coefficients(
    x_scaled: pd.DataFrame,
    y: np.ndarray,
    alpha: float = 0.0,
) -> np.ndarray:
    train_design = np.column_stack([np.ones(len(x_scaled)), x_scaled.to_numpy(dtype=float)])
    if alpha <= 0:
        beta, *_ = np.linalg.lstsq(train_design, y, rcond=None)
        return beta.astype(float)

    penalty = np.eye(train_design.shape[1])
    penalty[0, 0] = 0.0
    lhs = train_design.T @ train_design + alpha * penalty
    rhs = train_design.T @ y
    beta, *_ = np.linalg.lstsq(lhs, rhs, rcond=None)
    return beta.astype(float)


def predict_design(
    beta: np.ndarray,
    x_scaled: pd.DataFrame,
    target_transform: str,
) -> np.ndarray:
    design = np.column_stack([np.ones(len(x_scaled)), x_scaled.to_numpy(dtype=float)])
    raw_predictions = design @ beta
    if target_transform == "log1p":
        raw_predictions = np.expm1(raw_predictions)
    return np.maximum(0.0, raw_predictions.astype(float))


def fit_regression_model(
    split: dict[str, Any],
    feature_columns: list[str],
    model_name: str,
    model_type: str,
    alpha: float = 0.0,
    target_transform: str = "none",
    target_column: str = "target_next_hour_avg_fee",
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float], pd.DataFrame]:
    y_train = split["y_train"]
    if target_transform == "log1p":
        train_target = np.log1p(y_train)
    elif target_transform == "none":
        train_target = y_train
    else:
        raise ValueError(f"Unsupported target transform: {target_transform}")

    beta = regression_coefficients(split["x_train_scaled"], train_target, alpha=alpha)
    intercept = float(beta[0])
    coefficients = beta[1:].astype(float)

    predictions = predict_design(beta, split["x_test_scaled"], target_transform)
    metrics = compute_metrics(split["y_test"], predictions, split["test_current_fee"])
    metrics.update(
        {
            "model_name": model_name,
            "model_type": model_type,
            "target_transform": target_transform,
            "alpha": float(alpha),
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
        "model_type": model_type,
        "target_column": target_column,
        "target_transform": target_transform,
        "alpha": float(alpha),
        "feature_columns": feature_columns,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "intercept": intercept,
        "coefficients_scaled": dict(zip(feature_columns, coefficients.tolist(), strict=True)),
        "impute_values": {column: float(split["impute_values"][column]) for column in feature_columns},
        "feature_means": {column: float(split["means"][column]) for column in feature_columns},
        "feature_stds": {column: float(split["stds"][column]) for column in feature_columns},
        "metrics": metrics,
    }

    coefficient_table = pd.DataFrame(
        {
            "model_name": model_name,
            "feature": feature_columns,
            "coefficient_scaled": coefficients,
            "abs_coefficient_scaled": np.abs(coefficients),
        }
    ).sort_values("abs_coefficient_scaled", ascending=False)

    return model, coefficient_table, metrics, actual_vs_predicted


def fit_linear_regression(
    hourly_df: pd.DataFrame,
    feature_columns: list[str] = MODEL_FEATURE_COLUMNS,
    target_column: str = "target_next_hour_avg_fee",
    test_fraction: float = 0.2,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float]]:
    """Compatibility wrapper for the original baseline training path."""
    split = split_model_data(hourly_df, feature_columns, target_column, test_fraction)
    model, coefficients, metrics, _ = fit_regression_model(
        split=split,
        feature_columns=feature_columns,
        model_name="linear_regression",
        model_type="ordinary_least_squares_linear_regression",
        alpha=0.0,
        target_transform="none",
        target_column=target_column,
    )
    return model, coefficients, metrics



"""Shared model split, metric, and prediction helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

if __package__ == "models":
    from features import prepare_model_matrix as prepare_model_matrix
else:
    from ..features import prepare_model_matrix as prepare_model_matrix


def split_model_data(
    hourly_df: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    test_fraction: float,
) -> dict[str, Any]:
    data = hourly_df.copy()
    if "hour" not in data.columns:
        raise ValueError("hourly feature dataset must include an hour column")
    data[target_column] = pd.to_numeric(data[target_column], errors="coerce")
    x = prepare_model_matrix(data, feature_columns)
    usable = x.notna().any(axis=1) & data[target_column].notna()
    x = x.loc[usable].reset_index(drop=True)
    y = data.loc[usable, target_column].astype(float).reset_index(drop=True)
    hours = data.loc[usable, "hour"].reset_index(drop=True)
    current_fee = pd.to_numeric(data.loc[usable, "avg_total_fee"], errors="coerce").astype(float).reset_index(drop=True)

    if len(x) < 10:
        raise ValueError("Need at least 10 hourly rows with targets to train the model.")

    split_index = max(1, int(len(x) * (1 - test_fraction)))
    if split_index >= len(x):
        split_index = len(x) - 1

    x_train = x.iloc[:split_index].copy()
    y_train = y.iloc[:split_index].to_numpy(dtype=float)
    x_test = x.iloc[split_index:].copy()
    y_test = y.iloc[split_index:].to_numpy(dtype=float)
    test_hours = hours.iloc[split_index:].reset_index(drop=True)
    test_row_indices = np.arange(split_index, len(x))

    impute_values = x_train.median(numeric_only=True).fillna(0)
    x_train = x_train.fillna(impute_values)
    x_test = x_test.fillna(impute_values)

    means = x_train.mean()
    stds = x_train.std(ddof=0).replace(0, 1).fillna(1)
    x_train_scaled = (x_train - means) / stds
    x_test_scaled = (x_test - means) / stds

    return {
        "x_train_scaled": x_train_scaled,
        "x_test_scaled": x_test_scaled,
        "y_train": y_train,
        "y_test": y_test,
        "test_hours": test_hours,
        "test_current_fee": current_fee.iloc[split_index:].reset_index(drop=True),
        "test_row_indices": test_row_indices,
        "fee_history": current_fee,
        "impute_values": impute_values,
        "means": means,
        "stds": stds,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
    }


def compute_metrics(
    y_true: np.ndarray,
    predictions: np.ndarray,
    current_fee: pd.Series | np.ndarray | None = None,
) -> dict[str, float]:
    residuals = y_true - predictions
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals**2)))
    total_var = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1 - np.sum(residuals**2) / total_var) if total_var else 0.0
    nonzero = y_true != 0
    mape = (
        float(np.mean(np.abs(residuals[nonzero] / y_true[nonzero])) * 100)
        if np.any(nonzero)
        else float("nan")
    )
    directional_accuracy = float("nan")
    if current_fee is not None:
        current = np.asarray(current_fee, dtype=float)
        directional_accuracy = float(np.mean(np.sign(predictions - current) == np.sign(y_true - current)))
    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "mape": mape,
        "directional_accuracy": directional_accuracy,
    }


def _split_from_row_ranges(
    x: pd.DataFrame,
    y: pd.Series,
    hours: pd.Series,
    current_fee: pd.Series,
    train_start: int,
    train_end: int,
    test_end: int,
) -> dict[str, Any]:
    x_train = x.iloc[train_start:train_end].copy()
    y_train = y.iloc[train_start:train_end].to_numpy(dtype=float)
    x_test = x.iloc[train_end:test_end].copy()
    y_test = y.iloc[train_end:test_end].to_numpy(dtype=float)
    test_hours = hours.iloc[train_end:test_end].reset_index(drop=True)
    test_row_indices = np.arange(train_end, test_end)

    impute_values = x_train.median(numeric_only=True).fillna(0)
    x_train = x_train.fillna(impute_values)
    x_test = x_test.fillna(impute_values)

    means = x_train.mean()
    stds = x_train.std(ddof=0).replace(0, 1).fillna(1)
    x_train_scaled = (x_train - means) / stds
    x_test_scaled = (x_test - means) / stds

    return {
        "x_train_scaled": x_train_scaled,
        "x_test_scaled": x_test_scaled,
        "y_train": y_train,
        "y_test": y_test,
        "test_hours": test_hours,
        "test_current_fee": current_fee.iloc[train_end:test_end].reset_index(drop=True),
        "test_row_indices": test_row_indices,
        "fee_history": current_fee.reset_index(drop=True),
        "impute_values": impute_values,
        "means": means,
        "stds": stds,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
    }


def predict_with_model(model: dict[str, Any], feature_row: dict[str, Any]) -> float:
    if model.get("model_type") == "naive":
        history = feature_row.get("_fee_history")
        if history:
            history_values = [float(value) for value in history if not pd.isna(value)]
        else:
            history_values = [
                float(value)
                for value in model.get("naive_state", {}).get("last_24_avg_total_fee", [])
                if not pd.isna(value)
            ]
        baseline_kind = model.get("baseline_kind")
        if baseline_kind == "persistence":
            value = float(feature_row.get("avg_total_fee", history_values[-1] if history_values else 0.0))
        elif baseline_kind == "seasonal_naive_24h":
            value = history_values[-24] if len(history_values) >= 24 else (history_values[0] if history_values else 0.0)
        elif baseline_kind == "rolling_mean_6h":
            window = history_values[-6:] if history_values else [float(feature_row.get("avg_total_fee", 0.0))]
            value = float(np.mean(window))
        else:
            raise ValueError(f"Unsupported naive baseline: {baseline_kind}")
        return max(0.0, float(value))

    if model.get("model_type") == "gradient_boosted_regression_trees":
        values: dict[str, float] = {}
        for feature in model["feature_columns"]:
            raw = feature_row.get(feature)
            if raw is None or pd.isna(raw):
                raw = model["impute_values"][feature]
            values[feature] = (
                float(raw) - float(model["feature_means"][feature])
            ) / float(model["feature_stds"][feature])
        x_scaled = pd.DataFrame([values], columns=model["feature_columns"])
        from .gbdt import predict_tree_ensemble

        return float(predict_tree_ensemble(model, x_scaled)[0])

    value = float(model["intercept"])
    for feature in model["feature_columns"]:
        raw = feature_row.get(feature)
        if raw is None or pd.isna(raw):
            raw = model["impute_values"][feature]
        scaled = (float(raw) - model["feature_means"][feature]) / model["feature_stds"][feature]
        value += float(model["coefficients_scaled"][feature]) * scaled
    if model.get("target_transform") == "log1p":
        value = float(np.expm1(value))
    return max(0.0, value)

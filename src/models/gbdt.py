"""Gradient boosted regression tree helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .base import compute_metrics as compute_metrics


def _tree_predict_one(tree: dict[str, Any], row: np.ndarray) -> float:
    node = tree
    while node.get("feature_index") is not None:
        feature_index = int(node["feature_index"])
        threshold = float(node["threshold"])
        node = node["left"] if row[feature_index] <= threshold else node["right"]
    return float(node["value"])


def predict_tree_ensemble(model: dict[str, Any], x_scaled: pd.DataFrame) -> np.ndarray:
    x_values = x_scaled.to_numpy(dtype=float)
    predictions = np.full(
        len(x_values),
        float(model["initial_prediction"]),
        dtype=float,
    )
    learning_rate = float(model["learning_rate"])
    for tree in model["trees"]:
        predictions += learning_rate * np.array([_tree_predict_one(tree, row) for row in x_values])
    if model.get("target_transform") == "log1p":
        predictions = np.expm1(predictions)
    return np.maximum(0.0, predictions.astype(float))


def _build_regression_tree(
    x_values: np.ndarray,
    y_values: np.ndarray,
    row_indices: np.ndarray,
    depth: int,
    max_depth: int,
    min_samples_leaf: int,
    feature_importance: np.ndarray,
) -> dict[str, Any]:
    node_values = y_values[row_indices]
    node_prediction = float(np.mean(node_values))
    node_sse = float(np.sum((node_values - node_prediction) ** 2))

    if (
        depth >= max_depth
        or len(row_indices) < 2 * min_samples_leaf
        or node_sse <= 1e-12
    ):
        return {"value": node_prediction, "feature_index": None}

    best_split: tuple[float, int, float, np.ndarray, np.ndarray] | None = None
    feature_count = x_values.shape[1]
    quantiles = np.linspace(0.1, 0.9, 9)

    for feature_index in range(feature_count):
        feature_values = x_values[row_indices, feature_index]
        thresholds = np.unique(np.quantile(feature_values, quantiles))
        for threshold in thresholds:
            left_mask = feature_values <= threshold
            left_count = int(left_mask.sum())
            right_count = len(row_indices) - left_count
            if left_count < min_samples_leaf or right_count < min_samples_leaf:
                continue

            left_indices = row_indices[left_mask]
            right_indices = row_indices[~left_mask]
            left_values = y_values[left_indices]
            right_values = y_values[right_indices]
            left_sse = float(np.sum((left_values - np.mean(left_values)) ** 2))
            right_sse = float(np.sum((right_values - np.mean(right_values)) ** 2))
            split_sse = left_sse + right_sse
            if best_split is None or split_sse < best_split[0]:
                best_split = (
                    split_sse,
                    feature_index,
                    float(threshold),
                    left_indices,
                    right_indices,
                )

    if best_split is None or best_split[0] >= node_sse:
        return {"value": node_prediction, "feature_index": None}

    split_sse, feature_index, threshold, left_indices, right_indices = best_split
    feature_importance[feature_index] += max(0.0, node_sse - split_sse)
    return {
        "value": node_prediction,
        "feature_index": int(feature_index),
        "threshold": float(threshold),
        "left": _build_regression_tree(
            x_values,
            y_values,
            left_indices,
            depth + 1,
            max_depth,
            min_samples_leaf,
            feature_importance,
        ),
        "right": _build_regression_tree(
            x_values,
            y_values,
            right_indices,
            depth + 1,
            max_depth,
            min_samples_leaf,
            feature_importance,
        ),
    }


def fit_gradient_boosted_tree_model(
    split: dict[str, Any],
    feature_columns: list[str],
    model_name: str,
    max_depth: int,
    n_estimators: int,
    learning_rate: float,
    min_samples_leaf: int = 20,
    target_transform: str = "none",
    target_column: str = "target_next_hour_avg_fee",
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float], pd.DataFrame]:
    if target_transform == "log1p":
        train_target = np.log1p(split["y_train"])
    elif target_transform == "none":
        train_target = split["y_train"]
    else:
        raise ValueError(f"Unsupported target transform: {target_transform}")

    x_train_values = split["x_train_scaled"].to_numpy(dtype=float)
    initial_prediction = float(np.mean(train_target))
    train_predictions = np.full(len(train_target), initial_prediction, dtype=float)
    trees: list[dict[str, Any]] = []
    feature_importance_values = np.zeros(len(feature_columns), dtype=float)

    for _ in range(n_estimators):
        residuals = train_target - train_predictions
        tree = _build_regression_tree(
            x_values=x_train_values,
            y_values=residuals,
            row_indices=np.arange(len(residuals)),
            depth=0,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            feature_importance=feature_importance_values,
        )
        tree_train_predictions = np.array([_tree_predict_one(tree, row) for row in x_train_values])
        train_predictions += learning_rate * tree_train_predictions
        trees.append(tree)

    model = {
        "model_name": model_name,
        "model_type": "gradient_boosted_regression_trees",
        "target_column": target_column,
        "target_transform": target_transform,
        "feature_columns": feature_columns,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "initial_prediction": initial_prediction,
        "learning_rate": float(learning_rate),
        "n_estimators": int(n_estimators),
        "max_depth": int(max_depth),
        "min_samples_leaf": int(min_samples_leaf),
        "trees": trees,
        "impute_values": {column: float(split["impute_values"][column]) for column in feature_columns},
        "feature_means": {column: float(split["means"][column]) for column in feature_columns},
        "feature_stds": {column: float(split["stds"][column]) for column in feature_columns},
    }

    predictions = predict_tree_ensemble(model, split["x_test_scaled"])
    metrics = compute_metrics(split["y_test"], predictions, split["test_current_fee"])
    metrics.update(
        {
            "model_name": model_name,
            "model_type": "gradient_boosted_regression_trees",
            "target_transform": target_transform,
            "alpha": 0.0,
            "max_depth": int(max_depth),
            "n_estimators": int(n_estimators),
            "learning_rate": float(learning_rate),
            "min_samples_leaf": int(min_samples_leaf),
            "train_rows": split["train_rows"],
            "test_rows": split["test_rows"],
        }
    )
    model["metrics"] = metrics

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

    total_importance = float(feature_importance_values.sum())
    normalized_importance = (
        feature_importance_values / total_importance
        if total_importance > 0
        else feature_importance_values
    )
    importance_table = pd.DataFrame(
        {
            "model_name": model_name,
            "feature": feature_columns,
            "coefficient_scaled": np.nan,
            "abs_coefficient_scaled": normalized_importance,
            "tree_importance": normalized_importance,
        }
    ).sort_values("abs_coefficient_scaled", ascending=False)

    return model, importance_table, metrics, actual_vs_predicted



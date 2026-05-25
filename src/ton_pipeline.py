"""Shared helpers for TON fee data collection, feature engineering, and models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd


try:
    from schema import BOOL_COLUMNS as BOOL_COLUMNS
    from schema import HOURLY_COLUMNS as HOURLY_COLUMNS
    from schema import HOURLY_DICTIONARY as HOURLY_DICTIONARY
    from schema import MODEL_FEATURE_COLUMNS as MODEL_FEATURE_COLUMNS
    from schema import NUMERIC_COLUMNS as NUMERIC_COLUMNS
    from schema import PROJECT_ROOT as PROJECT_ROOT
    from schema import RAW_COLUMNS as RAW_COLUMNS
    from schema import RAW_DICTIONARY as RAW_DICTIONARY
    from schema import ZERO_FILL_COLUMNS as ZERO_FILL_COLUMNS
    from schema import resolve_path as resolve_path
except ModuleNotFoundError:
    from .schema import BOOL_COLUMNS as BOOL_COLUMNS
    from .schema import HOURLY_COLUMNS as HOURLY_COLUMNS
    from .schema import HOURLY_DICTIONARY as HOURLY_DICTIONARY
    from .schema import MODEL_FEATURE_COLUMNS as MODEL_FEATURE_COLUMNS
    from .schema import NUMERIC_COLUMNS as NUMERIC_COLUMNS
    from .schema import PROJECT_ROOT as PROJECT_ROOT
    from .schema import RAW_COLUMNS as RAW_COLUMNS
    from .schema import RAW_DICTIONARY as RAW_DICTIONARY
    from .schema import ZERO_FILL_COLUMNS as ZERO_FILL_COLUMNS
    from .schema import resolve_path as resolve_path


try:
    from ingestion import as_bool as as_bool
    from ingestion import as_int as as_int
    from ingestion import fetch_transactions as fetch_transactions
    from ingestion import flatten_transaction as flatten_transaction
    from ingestion import iter_windows as iter_windows
    from ingestion import nested as nested
    from ingestion import parse_utc as parse_utc
    from ingestion import sum_message_field as sum_message_field
    from ingestion import write_raw_csv as write_raw_csv
except ModuleNotFoundError:
    from .ingestion import as_bool as as_bool
    from .ingestion import as_int as as_int
    from .ingestion import fetch_transactions as fetch_transactions
    from .ingestion import flatten_transaction as flatten_transaction
    from .ingestion import iter_windows as iter_windows
    from .ingestion import nested as nested
    from .ingestion import parse_utc as parse_utc
    from .ingestion import sum_message_field as sum_message_field
    from .ingestion import write_raw_csv as write_raw_csv


try:
    from features import build_hourly_features as build_hourly_features
    from features import capped_hours_from_metadata as capped_hours_from_metadata
    from features import normalize_bool as normalize_bool
    from features import prepare_model_matrix as prepare_model_matrix
    from features import read_raw_transactions as read_raw_transactions
    from features import recompute_hourly_derived_features as recompute_hourly_derived_features
    from features import write_data_dictionary as write_data_dictionary
    from features import write_summary as write_summary
except ModuleNotFoundError:
    from .features import build_hourly_features as build_hourly_features
    from .features import capped_hours_from_metadata as capped_hours_from_metadata
    from .features import normalize_bool as normalize_bool
    from .features import prepare_model_matrix as prepare_model_matrix
    from .features import read_raw_transactions as read_raw_transactions
    from .features import recompute_hourly_derived_features as recompute_hourly_derived_features
    from .features import write_data_dictionary as write_data_dictionary
    from .features import write_summary as write_summary


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


def build_model_candidates() -> list[dict[str, Any]]:
    return [
        {
            "model_name": "persistence",
            "model_type": "naive",
            "baseline_kind": "persistence",
            "target_transform": "none",
        },
        {
            "model_name": "seasonal_naive_24h",
            "model_type": "naive",
            "baseline_kind": "seasonal_naive_24h",
            "target_transform": "none",
        },
        {
            "model_name": "rolling_mean_6h",
            "model_type": "naive",
            "baseline_kind": "rolling_mean_6h",
            "target_transform": "none",
        },
        {
            "model_name": "ridge_alpha_1",
            "model_type": "ridge_regression",
            "alpha": 1.0,
            "target_transform": "none",
        },
        {
            "model_name": "ridge_alpha_10",
            "model_type": "ridge_regression",
            "alpha": 10.0,
            "target_transform": "none",
        },
        {
            "model_name": "ridge_alpha_100",
            "model_type": "ridge_regression",
            "alpha": 100.0,
            "target_transform": "none",
        },
        {
            "model_name": "ridge_alpha_1_log1p_target",
            "model_type": "ridge_regression",
            "alpha": 1.0,
            "target_transform": "log1p",
        },
        {
            "model_name": "ridge_alpha_10_log1p_target",
            "model_type": "ridge_regression",
            "alpha": 10.0,
            "target_transform": "log1p",
        },
        {
            "model_name": "ridge_alpha_100_log1p_target",
            "model_type": "ridge_regression",
            "alpha": 100.0,
            "target_transform": "log1p",
        },
        {
            "model_name": "gradient_boosted_stumps_50_lr_0_05",
            "model_type": "gradient_boosted_regression_trees",
            "max_depth": 1,
            "n_estimators": 50,
            "learning_rate": 0.05,
            "min_samples_leaf": 20,
            "target_transform": "none",
        },
        {
            "model_name": "gradient_boosted_stumps_100_lr_0_05",
            "model_type": "gradient_boosted_regression_trees",
            "max_depth": 1,
            "n_estimators": 100,
            "learning_rate": 0.05,
            "min_samples_leaf": 20,
            "target_transform": "none",
        },
        {
            "model_name": "gradient_boosted_stumps_200_lr_0_03",
            "model_type": "gradient_boosted_regression_trees",
            "max_depth": 1,
            "n_estimators": 200,
            "learning_rate": 0.03,
            "min_samples_leaf": 20,
            "target_transform": "none",
        },
        {
            "model_name": "gradient_boosted_trees_depth_3_50_lr_0_1",
            "model_type": "gradient_boosted_regression_trees",
            "max_depth": 3,
            "n_estimators": 50,
            "learning_rate": 0.1,
            "min_samples_leaf": 20,
            "target_transform": "none",
        },
    ]


def fit_model_candidate(
    candidate: dict[str, Any],
    split: dict[str, Any],
    feature_columns: list[str],
    target_column: str,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float], pd.DataFrame]:
    if candidate["model_type"] == "naive":
        return fit_naive_model(
            split=split,
            feature_columns=feature_columns,
            target_column=target_column,
            model_name=str(candidate["model_name"]),
            baseline_kind=str(candidate["baseline_kind"]),
        )

    if candidate["model_type"] == "gradient_boosted_regression_trees":
        return fit_gradient_boosted_tree_model(
            split=split,
            feature_columns=feature_columns,
            target_column=target_column,
            model_name=str(candidate["model_name"]),
            max_depth=int(candidate["max_depth"]),
            n_estimators=int(candidate["n_estimators"]),
            learning_rate=float(candidate["learning_rate"]),
            min_samples_leaf=int(candidate["min_samples_leaf"]),
            target_transform=str(candidate["target_transform"]),
        )

    return fit_regression_model(
        split=split,
        feature_columns=feature_columns,
        target_column=target_column,
        **candidate,
    )


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


def train_model_suite(
    hourly_df: pd.DataFrame,
    feature_columns: list[str] = MODEL_FEATURE_COLUMNS,
    target_column: str = "target_next_hour_avg_fee",
    test_fraction: float = 0.2,
    rolling_summary: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    split = split_model_data(hourly_df, feature_columns, target_column, test_fraction)
    candidates = build_model_candidates()

    trained: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    coefficient_tables: list[pd.DataFrame] = []
    prediction_tables: list[pd.DataFrame] = []

    for candidate in candidates:
        model, coefficients, metrics, actual_vs_predicted = fit_model_candidate(
            candidate,
            split,
            feature_columns,
            target_column,
        )
        trained.append(model)
        comparison_rows.append(metrics)
        coefficient_tables.append(coefficients)
        prediction_tables.append(actual_vs_predicted)

    comparison = pd.DataFrame(comparison_rows).sort_values(
        ["r2", "rmse", "mae"],
        ascending=[False, True, True],
    )
    selected_by = "chronological holdout R2"
    if rolling_summary is not None and not rolling_summary.empty:
        rolling_selection = rolling_summary.sort_values(
            ["mean_r2", "median_rmse"],
            ascending=[False, True],
        )
        best_model_name = str(rolling_selection.iloc[0]["model_name"])
        selected_by = "rolling backtest mean R2 (tie-break median RMSE)"
    else:
        best_model_name = str(comparison.iloc[0]["model_name"])
    best_comparison_row = comparison[comparison["model_name"] == best_model_name].iloc[0]
    best_model = next(model for model in trained if model["model_name"] == best_model_name)
    feature_importance = pd.concat(coefficient_tables, ignore_index=True)
    best_actual_vs_predicted = next(
        table for table in prediction_tables if str(table["model_name"].iloc[0]) == best_model_name
    )

    summary = {
        "best_model_name": best_model_name,
        "best_r2": float(best_comparison_row["r2"]),
        "best_mae": float(best_comparison_row["mae"]),
        "best_rmse": float(best_comparison_row["rmse"]),
        "best_directional_accuracy": float(best_comparison_row["directional_accuracy"]),
        "selected_by": selected_by,
        "train_rows": int(split["train_rows"]),
        "test_rows": int(split["test_rows"]),
    }

    return best_model, comparison, feature_importance, best_actual_vs_predicted, summary


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


def rolling_backtest_model_suite(
    hourly_df: pd.DataFrame,
    feature_columns: list[str] = MODEL_FEATURE_COLUMNS,
    target_column: str = "target_next_hour_avg_fee",
    min_train_rows: int = 336,
    test_rows: int = 24,
    step_rows: int = 24,
    max_folds: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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

    if len(x) < min_train_rows + test_rows:
        raise ValueError(
            f"Need at least {min_train_rows + test_rows} usable rows for rolling backtest."
        )

    fold_starts = list(range(min_train_rows, len(x) - test_rows + 1, step_rows))
    if max_folds > 0:
        fold_starts = fold_starts[-max_folds:]

    candidates = build_model_candidates()
    rows: list[dict[str, Any]] = []
    for fold_index, test_start in enumerate(fold_starts, start=1):
        test_end = test_start + test_rows
        split = _split_from_row_ranges(
            x=x,
            y=y,
            hours=hours,
            current_fee=current_fee,
            train_start=0,
            train_end=test_start,
            test_end=test_end,
        )
        for candidate in candidates:
            _, _, metrics, _ = fit_model_candidate(
                candidate,
                split,
                feature_columns,
                target_column,
            )
            row = {
                **metrics,
                "fold": fold_index,
                "train_start_hour": str(hours.iloc[0]),
                "train_end_hour": str(hours.iloc[test_start - 1]),
                "test_start_hour": str(hours.iloc[test_start]),
                "test_end_hour": str(hours.iloc[test_end - 1]),
            }
            rows.append(row)

    fold_results = pd.DataFrame(rows)
    winners = (
        fold_results.sort_values(["fold", "r2", "rmse", "mae"], ascending=[True, False, True, True])
        .groupby("fold", as_index=False)
        .first()[["fold", "model_name"]]
        .rename(columns={"model_name": "winning_model_name"})
    )
    win_counts = winners["winning_model_name"].value_counts().rename("r2_win_count")

    aggregation = {
        "r2": ["mean", "median", "std", "min", "max"],
        "mae": ["mean", "median", "std"],
        "rmse": ["mean", "median", "std"],
        "mape": ["mean", "median"],
        "directional_accuracy": ["mean", "median"],
        "fold": "count",
    }
    summary = fold_results.groupby(
        ["model_name", "model_type", "target_transform"],
        as_index=False,
    ).agg(aggregation)
    summary.columns = [
        "_".join(column).strip("_") if isinstance(column, tuple) else column
        for column in summary.columns
    ]
    summary = summary.rename(
        columns={
            "r2_mean": "mean_r2",
            "r2_median": "median_r2",
            "r2_std": "std_r2",
            "r2_min": "min_r2",
            "r2_max": "max_r2",
            "mae_mean": "mean_mae",
            "mae_median": "median_mae",
            "mae_std": "std_mae",
            "rmse_mean": "mean_rmse",
            "rmse_median": "median_rmse",
            "rmse_std": "std_rmse",
            "mape_mean": "mean_mape",
            "mape_median": "median_mape",
            "directional_accuracy_mean": "mean_directional_accuracy",
            "directional_accuracy_median": "median_directional_accuracy",
            "fold_count": "folds",
        }
    )
    summary["r2_win_count"] = summary["model_name"].map(win_counts).fillna(0).astype(int)
    summary = summary.sort_values(
        ["mean_r2", "median_rmse"],
        ascending=[False, True],
    ).reset_index(drop=True)
    fold_results = fold_results.merge(winners, on="fold", how="left")
    return summary, fold_results


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

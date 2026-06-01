"""Model candidate suite training helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .base import split_model_data as split_model_data
from .gbdt import fit_gradient_boosted_tree_model as fit_gradient_boosted_tree_model
from .linear import fit_regression_model as fit_regression_model
from .naive import fit_naive_model as fit_naive_model

if __package__ == "models":
    from schema import MODEL_FEATURE_COLUMNS as MODEL_FEATURE_COLUMNS
else:
    from ..schema import MODEL_FEATURE_COLUMNS as MODEL_FEATURE_COLUMNS


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
        rolling_selection = rolling_summary.copy()
        persistence_mean_mae = float(
            rolling_selection.loc[rolling_selection["model_name"] == "persistence", "mean_mae"].iloc[0]
        )
        rolling_selection["skill_vs_persistence"] = 1 - (
            rolling_selection["mean_mae"].astype(float) / persistence_mean_mae
        )
        skilled = rolling_selection[rolling_selection["skill_vs_persistence"] > 0].sort_values(
            ["skill_vs_persistence", "median_rmse"],
            ascending=[False, True],
        )
        if skilled.empty:
            rolling_selection = rolling_selection[
                rolling_selection["model_name"].isin(["persistence", "rolling_mean_6h"])
            ].sort_values(["mean_mae", "median_rmse"], ascending=[True, True])
            selected_by = "rolling backtest naive fallback by mean MAE"
        else:
            rolling_selection = skilled
            selected_by = "rolling backtest MAE skill vs persistence"
        best_model_name = str(rolling_selection.iloc[0]["model_name"])
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


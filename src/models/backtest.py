"""Rolling backtest helpers for model candidates."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .base import _split_from_row_ranges as _split_from_row_ranges
from .suite import build_model_candidates as build_model_candidates
from .suite import fit_model_candidate as fit_model_candidate

if __package__ == "models":
    from features import prepare_model_matrix as prepare_model_matrix
    from schema import MODEL_FEATURE_COLUMNS as MODEL_FEATURE_COLUMNS
else:
    from ..features import prepare_model_matrix as prepare_model_matrix
    from ..schema import MODEL_FEATURE_COLUMNS as MODEL_FEATURE_COLUMNS


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



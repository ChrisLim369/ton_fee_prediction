#!/usr/bin/env python3
"""Measure recursive 24-hour horizon forecast candidates without writing deployment artifacts."""

from __future__ import annotations

import sys
from datetime import UTC
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import generate_forecast  # noqa: E402
from features import prepare_model_matrix  # noqa: E402
from models.base import _split_from_row_ranges  # noqa: E402
from models.linear import fit_regression_model  # noqa: E402
from schema import MODEL_FEATURE_COLUMNS  # noqa: E402

FEATURES_PATH = ROOT / "hourly_features.csv"
REPORT_PATH = ROOT / "docs" / "horizon_forecast_experiment.md"
TARGET_COLUMN = "target_next_hour_avg_fee"
HORIZON_HOURS = 24
TEST_FRACTION = 0.2
RECENT_REGIME_START = pd.Timestamp("2026-05-26T00:00:00Z")
CANDIDATE_ORDER = ["persistence", "rolling_mean_6h", "ridge_alpha_100_log1p_target"]


def load_hourly_features() -> pd.DataFrame:
    df = generate_forecast.numeric_hourly(FEATURES_PATH, MODEL_FEATURE_COLUMNS)
    for column in ["avg_total_fee", TARGET_COLUMN, "is_capped_hour"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def usable_mask(df: pd.DataFrame) -> pd.Series:
    x = prepare_model_matrix(df, MODEL_FEATURE_COLUMNS)
    target = pd.to_numeric(df[TARGET_COLUMN], errors="coerce")
    return x.notna().any(axis=1) & target.notna()


def holdout_start_index(df: pd.DataFrame) -> int:
    usable_indices = np.flatnonzero(usable_mask(df).to_numpy())
    if len(usable_indices) < 10:
        raise ValueError("Need at least 10 usable rows for the horizon experiment")
    split_index = max(1, int(len(usable_indices) * (1 - TEST_FRACTION)))
    if split_index >= len(usable_indices):
        split_index = len(usable_indices) - 1
    return int(usable_indices[split_index])


def capped_target_mask(df: pd.DataFrame) -> pd.Series:
    capped = pd.to_numeric(df["is_capped_hour"], errors="coerce")
    return capped.shift(-1).eq(1)


def fit_clean_ridge_model(df: pd.DataFrame, holdout_start: int) -> tuple[dict[str, Any], int]:
    train_mask = (df.index < holdout_start) & usable_mask(df) & ~capped_target_mask(df)
    train_df = df.loc[train_mask].copy().reset_index(drop=True)
    if len(train_df) < 10:
        raise ValueError("Need at least 10 clean train rows before holdout")

    augmented = pd.concat([train_df, train_df.tail(1)], ignore_index=True)
    x = prepare_model_matrix(augmented, MODEL_FEATURE_COLUMNS)
    y = pd.to_numeric(augmented[TARGET_COLUMN], errors="coerce")
    split = _split_from_row_ranges(
        x=x,
        y=y,
        hours=augmented["hour"],
        current_fee=pd.to_numeric(augmented["avg_total_fee"], errors="coerce"),
        train_start=0,
        train_end=len(train_df),
        test_end=len(augmented),
    )
    model, _, _, _ = fit_regression_model(
        split=split,
        feature_columns=MODEL_FEATURE_COLUMNS,
        model_name="ridge_alpha_100_log1p_target",
        model_type="ridge_regression",
        alpha=100.0,
        target_transform="log1p",
        target_column=TARGET_COLUMN,
    )
    return model, len(train_df)


def naive_model(model_name: str, baseline_kind: str) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "model_type": "naive",
        "baseline_kind": baseline_kind,
        "target_column": TARGET_COLUMN,
        "target_transform": "none",
        "feature_columns": MODEL_FEATURE_COLUMNS,
        "trained_at_utc": "measurement-only",
        "metrics": {},
        "naive_state": {"last_24_avg_total_fee": []},
    }


def candidate_models(df: pd.DataFrame, holdout_start: int) -> tuple[dict[str, dict[str, Any]], int]:
    ridge_model, clean_train_rows = fit_clean_ridge_model(df, holdout_start)
    return (
        {
            "persistence": naive_model("persistence", "persistence"),
            "rolling_mean_6h": naive_model("rolling_mean_6h", "rolling_mean_6h"),
            "ridge_alpha_100_log1p_target": ridge_model,
        },
        clean_train_rows,
    )


def regime_for(origin_hour: pd.Timestamp) -> str:
    return "recent_capped" if origin_hour >= RECENT_REGIME_START else "clean"


def evaluate_model(df: pd.DataFrame, model: dict[str, Any], holdout_start: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for origin_index in range(holdout_start, len(df) - HORIZON_HOURS):
        origin_hour = df.iloc[origin_index]["hour_dt"]
        future = df.iloc[origin_index + 1 : origin_index + HORIZON_HOURS + 1]
        if future["avg_total_fee"].isna().any():
            continue

        history = df.iloc[: origin_index + 1].copy()
        generated_at = origin_hour.to_pydatetime().astimezone(UTC)
        forecasts = generate_forecast.recursive_forecast(history, model, HORIZON_HOURS, generated_at)
        for forecast in forecasts:
            horizon = int(forecast["horizon_hours"])
            actual_row = future.iloc[horizon - 1]
            forecast_hour = pd.to_datetime(forecast["forecast_hour"], utc=True)
            if forecast_hour != actual_row["hour_dt"]:
                raise ValueError(f"forecast hour mismatch at origin {origin_hour}, horizon {horizon}")
            prediction = float(forecast["predicted_avg_total_fee"])
            actual = float(actual_row["avg_total_fee"])
            rows.append(
                {
                    "model_name": model["model_name"],
                    "origin_hour": origin_hour,
                    "regime": regime_for(origin_hour),
                    "horizon": horizon,
                    "actual": actual,
                    "prediction": prediction,
                    "absolute_error": abs(actual - prediction),
                }
            )
    return rows


def evaluate_candidates(df: pd.DataFrame, models: dict[str, dict[str, Any]], holdout_start: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model_name in CANDIDATE_ORDER:
        rows.extend(evaluate_model(df, models[model_name], holdout_start))
    if not rows:
        raise ValueError("No eligible rolling-origin forecast rows were evaluated")
    return pd.DataFrame(rows)


def ordered_columns(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.reindex(columns=CANDIDATE_ORDER)


def per_horizon_summary(results: pd.DataFrame) -> pd.DataFrame:
    mae = results.pivot_table(
        index="horizon",
        columns="model_name",
        values="absolute_error",
        aggfunc="mean",
    )
    mae = ordered_columns(mae)
    summary = mae.reset_index()
    summary["winner"] = mae.idxmin(axis=1).to_numpy()
    persistence = mae["persistence"]
    for model_name in CANDIDATE_ORDER:
        summary[f"{model_name}_skill"] = 1 - (mae[model_name].to_numpy() / persistence.to_numpy())
    return summary


def overall_summary(results: pd.DataFrame) -> pd.DataFrame:
    mae = results.groupby("model_name")["absolute_error"].mean().reindex(CANDIDATE_ORDER)
    persistence_mae = float(mae["persistence"])
    return pd.DataFrame(
        {
            "model_name": mae.index,
            "mean_mae_24h": mae.to_numpy(),
            "skill_vs_persistence": 1 - (mae.to_numpy() / persistence_mae),
        }
    )


def regime_summary(results: pd.DataFrame) -> pd.DataFrame:
    summary = results.pivot_table(
        index="regime",
        columns="model_name",
        values="absolute_error",
        aggfunc="mean",
    )
    return ordered_columns(summary)


def winner_segments(per_horizon: pd.DataFrame) -> str:
    segments: list[str] = []
    start = int(per_horizon.iloc[0]["horizon"])
    current = str(per_horizon.iloc[0]["winner"])
    previous = start
    for row in per_horizon.iloc[1:].itertuples(index=False):
        horizon = int(row.horizon)
        winner = str(row.winner)
        if winner != current:
            segments.append(format_segment(start, previous, current))
            start = horizon
            current = winner
        previous = horizon
    segments.append(format_segment(start, previous, current))
    return ", ".join(segments)


def format_segment(start: int, end: int, model_name: str) -> str:
    horizon = f"h{start}" if start == end else f"h{start}-h{end}"
    return f"{horizon}={model_name}"


def robust_replacement(overall: pd.DataFrame, regime: pd.DataFrame, per_horizon: pd.DataFrame) -> str | None:
    winner_counts = per_horizon["winner"].value_counts()
    for model_name in CANDIDATE_ORDER[1:]:
        if int(winner_counts.get(model_name, 0)) < 12:
            continue
        if float(overall.loc[overall["model_name"] == model_name, "skill_vs_persistence"].iloc[0]) <= 0:
            continue
        if (regime[model_name] < regime["persistence"]).all():
            return model_name
    return None


def fmt_number(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def per_horizon_table(per_horizon: pd.DataFrame) -> str:
    rows: list[list[str]] = []
    for row in per_horizon.itertuples(index=False):
        rows.append(
            [
                str(int(row.horizon)),
                fmt_number(float(row.persistence)),
                fmt_number(float(row.rolling_mean_6h)),
                fmt_number(float(row.ridge_alpha_100_log1p_target)),
                fmt_number(float(row.rolling_mean_6h_skill), 6),
                fmt_number(float(row.ridge_alpha_100_log1p_target_skill), 6),
                str(row.winner),
            ]
        )
    return markdown_table(
        [
            "Horizon",
            "Persistence MAE",
            "Rolling mean 6h MAE",
            "Ridge clean MAE",
            "Rolling skill",
            "Ridge skill",
            "Winner",
        ],
        rows,
    )


def overall_table(overall: pd.DataFrame) -> str:
    rows = [
        [
            str(row.model_name),
            fmt_number(float(row.mean_mae_24h)),
            fmt_number(float(row.skill_vs_persistence), 6),
        ]
        for row in overall.itertuples(index=False)
    ]
    return markdown_table(["Model", "24h average MAE", "Skill vs persistence"], rows)


def regime_table(regime: pd.DataFrame) -> str:
    rows: list[list[str]] = []
    for row in regime.reset_index().itertuples(index=False):
        rows.append(
            [
                str(row.regime),
                fmt_number(float(row.persistence)),
                fmt_number(float(row.rolling_mean_6h)),
                fmt_number(float(row.ridge_alpha_100_log1p_target)),
            ]
        )
    return markdown_table(["Regime", "Persistence MAE", "Rolling mean 6h MAE", "Ridge clean MAE"], rows)


def build_report(
    results: pd.DataFrame,
    per_horizon: pd.DataFrame,
    overall: pd.DataFrame,
    regime: pd.DataFrame,
    holdout_start: int,
    clean_train_rows: int,
) -> str:
    synthesis = winner_segments(per_horizon)
    replacement = robust_replacement(overall, regime, per_horizon)
    origin_counts = (
        results[results["model_name"] == CANDIDATE_ORDER[0]]
        .drop_duplicates(["origin_hour"])
        .groupby("regime")
        .size()
    )
    if replacement:
        conclusion = (
            f"{replacement} meets the measurement threshold for a persistence replacement candidate; "
            f"the horizon-aware synthesis is {synthesis}."
        )
    else:
        conclusion = (
            "No feature candidate clears the persistence replacement threshold across both clean and recent regimes; "
            f"the measured horizon-aware synthesis is {synthesis}, but deployment should wait for 3-2b review."
        )

    return "\n".join(
        [
            "# Horizon-Aware Forecast Experiment",
            "",
            (
                "This measurement compares three read-only forecast candidates with recursive 24-hour "
                "rolling-origin evaluation. It does not write deployment forecasts, models, predictions, "
                "or mirrored data."
            ),
            "",
            "## Method",
            "",
            "- Input: `hourly_features.csv`, sorted by `hour`.",
            f"- Fixed chronological split: holdout starts at row {holdout_start}.",
            f"- Ridge training rows after capped-target exclusion: {clean_train_rows}.",
            "- Ridge is fit once before holdout on clean-target rows only.",
            (
                "- Each origin passes only `df.iloc[:t+1]` into `recursive_forecast()`; origin-future rows "
                "are used only as actuals."
            ),
            (
                f"- Regime split: clean origins before {RECENT_REGIME_START.strftime('%Y-%m-%d')}; "
                "recent/capped origins from that date onward."
            ),
            "",
            "## Per-Horizon MAE",
            "",
            per_horizon_table(per_horizon),
            "",
            "## 24h Average MAE",
            "",
            overall_table(overall),
            "",
            "## Regime Transfer",
            "",
            regime_table(regime),
            "",
            f"- Evaluated clean origins per candidate: {int(origin_counts.get('clean', 0))}",
            f"- Evaluated recent/capped origins per candidate: {int(origin_counts.get('recent_capped', 0))}",
            "",
            "## Recommendation",
            "",
            f"- Per-horizon winner synthesis: {synthesis}",
            (
            "- Persistence replacement threshold: a non-persistence candidate should win across many horizons "
                "and beat persistence in both clean and recent/capped regimes."
            ),
            f"- Replacement candidate: {replacement or 'none'}",
            "",
            "## Conclusion",
            "",
            conclusion,
            "",
        ]
    )


def main() -> int:
    df = load_hourly_features()
    holdout_start = holdout_start_index(df)
    models, clean_train_rows = candidate_models(df, holdout_start)
    results = evaluate_candidates(df, models, holdout_start)
    horizon = per_horizon_summary(results)
    overall = overall_summary(results)
    regime = regime_summary(results)
    REPORT_PATH.write_text(
        build_report(results, horizon, overall, regime, holdout_start, clean_train_rows),
        encoding="utf-8",
    )

    print("Horizon-aware forecast experiment")
    print(f"origins per candidate: {results['origin_hour'].nunique()}")
    print(f"winner synthesis: {winner_segments(horizon)}")
    print(f"replacement candidate: {robust_replacement(overall, regime, horizon) or 'none'}")
    print(f"report: {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

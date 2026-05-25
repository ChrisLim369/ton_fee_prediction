#!/usr/bin/env python3
"""Train and compare next-hour TON transaction fee models."""

from __future__ import annotations

import argparse
import json
import logging
import sys

import pandas as pd

from ton_pipeline import (
    MODEL_FEATURE_COLUMNS,
    PROJECT_ROOT,
    resolve_path,
    rolling_backtest_model_suite,
    train_model_suite,
)


def write_evaluation_report(
    path,
    summary: dict[str, object],
    comparison: pd.DataFrame,
    rolling_summary: pd.DataFrame | None = None,
) -> None:
    best_r2 = float(summary["best_r2"])
    lines = [
        "# Model Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Best model: `{summary['best_model_name']}`",
        f"- Selected by: {summary.get('selected_by', 'chronological holdout R2')}",
        f"- Best model R2: {best_r2:.6f}",
        f"- Best model MAE: {float(summary['best_mae']):.3f} nanoton",
        f"- Best model RMSE: {float(summary['best_rmse']):.3f} nanoton",
        f"- Best model directional accuracy: {float(summary['best_directional_accuracy']):.3f}",
        "",
        "## Interpretation",
        "",
        "Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.",
        "If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.",
        "The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.",
        "",
        "## Model Comparison",
        "",
        "```text",
        comparison.to_string(index=False),
        "```",
        "",
    ]
    if rolling_summary is not None and not rolling_summary.empty:
        lines.extend(
            [
                "## Rolling Backtest",
                "",
                "Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.",
                "",
                "```text",
                rolling_summary.head(12).to_string(index=False),
                "```",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def train(args: argparse.Namespace) -> dict[str, object]:
    hourly_path = resolve_path(args.features)
    best_model_path = resolve_path(args.best_model)
    metrics_path = resolve_path(args.metrics)
    coefficients_path = resolve_path(args.coefficients)
    comparison_path = resolve_path(args.comparison)
    feature_importance_path = resolve_path(args.feature_importance)
    actual_vs_predicted_path = resolve_path(args.actual_vs_predicted)
    rolling_backtest_path = resolve_path(args.rolling_backtest)
    rolling_backtest_folds_path = resolve_path(args.rolling_backtest_folds)
    report_path = resolve_path(args.report)

    hourly_df = pd.read_csv(hourly_path)
    feature_columns = args.feature_columns or MODEL_FEATURE_COLUMNS
    rolling_summary, rolling_folds = rolling_backtest_model_suite(
        hourly_df=hourly_df,
        feature_columns=feature_columns,
        target_column=args.target,
        min_train_rows=args.rolling_min_train_rows,
        test_rows=args.rolling_test_rows,
        step_rows=args.rolling_step_rows,
        max_folds=args.rolling_max_folds,
    )
    best_model, comparison, feature_importance, actual_vs_predicted, summary = train_model_suite(
        hourly_df=hourly_df,
        feature_columns=feature_columns,
        target_column=args.target,
        test_fraction=args.test_fraction,
        rolling_summary=rolling_summary,
    )

    best_model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    coefficients_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    feature_importance_path.parent.mkdir(parents=True, exist_ok=True)
    actual_vs_predicted_path.parent.mkdir(parents=True, exist_ok=True)
    rolling_backtest_path.parent.mkdir(parents=True, exist_ok=True)
    rolling_backtest_folds_path.parent.mkdir(parents=True, exist_ok=True)

    best_model_path.write_text(json.dumps(best_model, indent=2), encoding="utf-8")
    metrics_payload = {"model": str(best_model_path.relative_to(PROJECT_ROOT)), **summary}
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    comparison.to_csv(comparison_path, index=False)
    rolling_summary.to_csv(rolling_backtest_path, index=False)
    rolling_folds.to_csv(rolling_backtest_folds_path, index=False)
    feature_importance.to_csv(feature_importance_path, index=False)
    feature_importance[feature_importance["model_name"] == best_model["model_name"]].to_csv(
        coefficients_path,
        index=False,
    )
    actual_vs_predicted.to_csv(actual_vs_predicted_path, index=False)
    write_evaluation_report(report_path, summary, comparison, rolling_summary)

    result = {
        "model": str(best_model_path),
        "metrics": str(metrics_path),
        "coefficients": str(coefficients_path),
        "comparison": str(comparison_path),
        "rolling_backtest": str(rolling_backtest_path),
        "rolling_backtest_folds": str(rolling_backtest_folds_path),
        "feature_importance": str(feature_importance_path),
        "actual_vs_predicted": str(actual_vs_predicted_path),
        "report": str(report_path),
        "rolling_best_model_name": str(rolling_summary.iloc[0]["model_name"]),
        "rolling_best_mean_r2": float(rolling_summary.iloc[0]["mean_r2"]),
        "rolling_best_mean_mae": float(rolling_summary.iloc[0]["mean_mae"]),
        "rolling_best_mean_rmse": float(rolling_summary.iloc[0]["mean_rmse"]),
        "rolling_folds": int(rolling_summary.iloc[0]["folds"]),
        **summary,
    }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", default="hourly_features.csv")
    parser.add_argument("--best-model", default="models/best_model.json")
    parser.add_argument("--metrics", default="models/model_metrics.json")
    parser.add_argument("--coefficients", default="models/model_coefficients.csv")
    parser.add_argument("--comparison", default="models/model_comparison.csv")
    parser.add_argument("--rolling-backtest", default="models/rolling_backtest.csv")
    parser.add_argument("--rolling-backtest-folds", default="models/rolling_backtest_folds.csv")
    parser.add_argument("--feature-importance", default="models/feature_importance.csv")
    parser.add_argument("--actual-vs-predicted", default="actual_vs_predicted.csv")
    parser.add_argument("--report", default="docs/model_evaluation_report.md")
    parser.add_argument("--target", default="target_next_hour_avg_fee")
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--rolling-min-train-rows", type=int, default=336)
    parser.add_argument("--rolling-test-rows", type=int, default=24)
    parser.add_argument("--rolling-step-rows", type=int, default=24)
    parser.add_argument("--rolling-max-folds", type=int, default=8)
    parser.add_argument("--feature-columns", nargs="*", default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    if not 0 < args.test_fraction < 1:
        raise ValueError("--test-fraction must be between 0 and 1")
    print(json.dumps(train(args), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

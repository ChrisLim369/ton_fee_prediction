#!/usr/bin/env python3
"""Measure whether excluding capped targets improves model selection."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
REPORT_PATH = ROOT / "docs" / "capped_target_experiment.md"
NAIVE_MODEL_TYPES = {"naive"}


def load_train_model() -> Any:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    import train_model

    return train_model


def train_args(output_dir: Path, exclude_capped_targets: bool) -> argparse.Namespace:
    return argparse.Namespace(
        features="hourly_features.csv",
        best_model=str(output_dir / "models" / "best_model.json"),
        metrics=str(output_dir / "models" / "model_metrics.json"),
        coefficients=str(output_dir / "models" / "model_coefficients.csv"),
        comparison=str(output_dir / "models" / "model_comparison.csv"),
        rolling_backtest=str(output_dir / "models" / "rolling_backtest.csv"),
        rolling_backtest_folds=str(output_dir / "models" / "rolling_backtest_folds.csv"),
        feature_importance=str(output_dir / "models" / "feature_importance.csv"),
        actual_vs_predicted=str(output_dir / "actual_vs_predicted.csv"),
        report=str(output_dir / "docs" / "model_evaluation_report.md"),
        target="target_next_hour_avg_fee",
        test_fraction=0.2,
        rolling_min_train_rows=336,
        rolling_test_rows=24,
        rolling_step_rows=24,
        rolling_max_folds=8,
        feature_columns=None,
        exclude_capped_targets=exclude_capped_targets,
    )


def run_training(label: str, exclude_capped_targets: bool, total_rows: int) -> dict[str, Any]:
    output_dir = Path(tempfile.mkdtemp(prefix=f".capped-target-{label}-", dir=ROOT))
    try:
        train_model = load_train_model()
        result = train_model.train(train_args(output_dir, exclude_capped_targets))
        return summarize_run(label, result, total_rows)
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def summarize_run(label: str, result: dict[str, Any], total_rows: int) -> dict[str, Any]:
    metrics_path = Path(str(result["metrics"]))
    rolling_path = Path(str(result["rolling_backtest"]))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    rolling = pd.read_csv(rolling_path)

    model_name = str(metrics["best_model_name"])
    selected = rolling.loc[rolling["model_name"] == model_name]
    persistence = rolling.loc[rolling["model_name"] == "persistence"]
    if selected.empty:
        raise ValueError(f"{label}: selected model {model_name!r} is missing from rolling backtest")
    if persistence.empty:
        raise ValueError(f"{label}: persistence is missing from rolling backtest")

    selected_row = selected.iloc[0]
    persistence_row = persistence.iloc[0]
    model_mean_mae = float(selected_row["mean_mae"])
    persistence_mean_mae = float(persistence_row["mean_mae"])
    exclusion = result.get(
        "capped_target_exclusion",
        {"before_rows": total_rows, "after_rows": total_rows, "excluded_rows": 0},
    )

    return {
        "label": label,
        "best_model_name": model_name,
        "selected_by": str(metrics["selected_by"]),
        "model_type": str(selected_row["model_type"]),
        "rolling_model_mean_mae": model_mean_mae,
        "rolling_persistence_mean_mae": persistence_mean_mae,
        "skill_vs_persistence": 1 - (model_mean_mae / persistence_mean_mae),
        "rolling_mean_r2": float(selected_row["mean_r2"]),
        "holdout_mae": float(metrics["best_mae"]),
        "holdout_r2": float(metrics["best_r2"]),
        "before_rows": int(exclusion["before_rows"]),
        "after_rows": int(exclusion["after_rows"]),
        "excluded_rows": int(exclusion["excluded_rows"]),
        "train_rows": int(metrics["train_rows"]),
        "test_rows": int(metrics["test_rows"]),
    }


def fmt_float(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def comparison_rows(baseline: dict[str, Any], excluded: dict[str, Any]) -> list[list[str]]:
    return [
        row_for_report(baseline),
        row_for_report(excluded),
    ]


def row_for_report(run: dict[str, Any]) -> list[str]:
    return [
        str(run["label"]),
        str(run["best_model_name"]),
        str(run["selected_by"]),
        fmt_float(float(run["rolling_model_mean_mae"]), 3),
        fmt_float(float(run["rolling_persistence_mean_mae"]), 3),
        fmt_float(float(run["skill_vs_persistence"])),
        fmt_float(float(run["rolling_mean_r2"])),
        fmt_float(float(run["holdout_mae"]), 3),
        fmt_float(float(run["holdout_r2"])),
        str(run["before_rows"]),
        str(run["after_rows"]),
        str(run["excluded_rows"]),
    ]


def verdict(baseline: dict[str, Any], excluded: dict[str, Any]) -> dict[str, Any]:
    naive_to_feature = baseline["model_type"] in NAIVE_MODEL_TYPES and excluded["model_type"] not in NAIVE_MODEL_TYPES
    mae_improvement = 1 - (
        float(excluded["rolling_model_mean_mae"]) / float(baseline["rolling_model_mean_mae"])
    )
    positive_skill = float(excluded["skill_vs_persistence"]) > 0
    helped = naive_to_feature or positive_skill or mae_improvement > 0.05
    if helped:
        branch = "helpful"
        recommendation = (
            "Capped-target exclusion appears helpful. Consider adopting `--exclude-capped-targets` "
            "for Wave 3-2 retraining, and only consider API backfill if a remaining data gap needs it."
        )
    else:
        branch = "minimal"
        recommendation = (
            "Capped-target exclusion effect is minimal. Keep all rows, skip API recollection, and move "
            "Wave 3-2 directly to horizon-aware forecasting as the larger lever."
        )
    return {
        "branch": branch,
        "recommendation": recommendation,
        "naive_to_feature": naive_to_feature,
        "positive_skill": positive_skill,
        "rolling_mae_improvement": mae_improvement,
    }


def build_report(baseline: dict[str, Any], excluded: dict[str, Any]) -> str:
    decision = verdict(baseline, excluded)
    mae_change_pct = fmt_float(float(decision["rolling_mae_improvement"]) * 100, 2)
    baseline_skill = fmt_float(float(baseline["skill_vs_persistence"]))
    excluded_skill = fmt_float(float(excluded["skill_vs_persistence"]))
    conclusion = (
        f"{decision['branch'].upper()}: baseline selected `{baseline['best_model_name']}` with "
        f"skill_vs_persistence {baseline_skill}; excluded selected `{excluded['best_model_name']}` with "
        f"skill_vs_persistence {excluded_skill} after excluding {excluded['excluded_rows']} capped-target rows."
    )
    table = markdown_table(
        [
            "Run",
            "Selected model",
            "Selected by",
            "Rolling MAE selected",
            "Rolling MAE persistence",
            "Skill vs persistence",
            "Rolling mean R2",
            "Holdout MAE",
            "Holdout R2",
            "Rows before",
            "Rows after",
            "Rows excluded",
        ],
        comparison_rows(baseline, excluded),
    )
    return "\n".join(
        [
            "# Capped Target Exclusion Experiment",
            "",
            (
                "This measurement runs `src/train_model.py` twice against committed `hourly_features.csv`: "
                "once with all rows, and once with `--exclude-capped-targets`. All training outputs are "
                "redirected to temporary directories and deleted after extracting metrics."
            ),
            "",
            "## Results",
            "",
            table,
            "",
            "## Methodology Caveat",
            "",
            (
                "`--exclude-capped-targets` drops rows before the chronological split, so the two runs do "
                "not use identical test sets. Cross-run absolute MAE is therefore not a clean apples-to-apples "
                "measure. Interpret the result by checking whether the selected model changes, whether each "
                "run's selected model has positive `skill_vs_persistence`, and the direction and rough size "
                "of rolling mean MAE."
            ),
            "",
            "## Data-Driven Recommendation",
            "",
            (
                "Rule: if exclusion changes selection from a naive model to a feature model, gives the excluded "
                "selected model positive skill versus persistence, or improves selected rolling mean MAE by "
                "about 5% or more, treat exclusion as useful. Otherwise treat the effect as minimal and avoid "
                "API recollection."
            ),
            "",
            f"- Selection changed naive to feature model: {decision['naive_to_feature']}",
            f"- Excluded selected-model skill_vs_persistence > 0: {decision['positive_skill']}",
            f"- Selected rolling mean MAE change vs baseline: {mae_change_pct}%",
            f"- Recommendation branch: {decision['branch']}",
            f"- Recommendation: {decision['recommendation']}",
            "",
            "## Conclusion",
            "",
            conclusion,
            "",
        ]
    )


def main() -> int:
    total_rows = len(pd.read_csv(ROOT / "hourly_features.csv"))
    baseline = run_training("baseline", exclude_capped_targets=False, total_rows=total_rows)
    excluded = run_training("excluded", exclude_capped_targets=True, total_rows=total_rows)
    report = build_report(baseline, excluded)
    REPORT_PATH.write_text(report, encoding="utf-8")

    decision = verdict(baseline, excluded)
    print("Capped-target exclusion experiment")
    print(f"baseline: {baseline['best_model_name']} skill={fmt_float(float(baseline['skill_vs_persistence']))}")
    print(f"excluded: {excluded['best_model_name']} skill={fmt_float(float(excluded['skill_vs_persistence']))}")
    print(f"excluded rows: {excluded['excluded_rows']}")
    print(f"rolling MAE change: {fmt_float(float(decision['rolling_mae_improvement']) * 100, 2)}%")
    print(f"recommendation branch: {decision['branch']}")
    print(f"report: {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

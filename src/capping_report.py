#!/usr/bin/env python3
"""Diagnose capped target rows without changing model training data."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ == "src":
    from .models.base import compute_metrics
    from .schema import resolve_path
else:
    from models.base import compute_metrics
    from schema import resolve_path


MIN_STABLE_N = 8
KNOWN_COVERAGE_NOTE = (
    "Current checked-in hourly_features.csv has 1512 rows, 113 capped rows, capped share 7.5%."
)
CONFOUNDING_WARNING = (
    "Capped rows are concentrated in a recent continuous block, so capped vs clean differences cannot be "
    "attributed to truncation bias alone; time/regime effects are confounded."
)
UNDER_FLAG_WARNING = (
    "Per-run collection caps are now persisted as collection_cap, and new rows are flagged with "
    "tx_count>=collection_cap. Legacy rows with missing collection_cap can remain under-flagged until an R2 "
    "raw replay rebuilds those hours from archived raw data; this report does not auto-relabel them."
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_hourly(path: Path) -> pd.DataFrame:
    hourly = pd.read_csv(path)
    required = {"hour", "avg_total_fee", "tx_count", "is_capped_hour"}
    missing = sorted(required - set(hourly.columns))
    if missing:
        raise ValueError(f"hourly_features.csv is missing required columns: {missing}")
    hourly = hourly.copy()
    hourly["hour_dt"] = pd.to_datetime(hourly["hour"], utc=True, errors="coerce")
    hourly["avg_total_fee"] = pd.to_numeric(hourly["avg_total_fee"], errors="coerce")
    hourly["tx_count"] = pd.to_numeric(hourly["tx_count"], errors="coerce")
    hourly["is_capped_hour"] = pd.to_numeric(hourly["is_capped_hour"], errors="coerce").fillna(0).astype(int)
    hourly = hourly.dropna(subset=["hour_dt"]).sort_values("hour_dt").reset_index(drop=True)
    return hourly


def iso_hour(value: Any) -> str:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def coverage_diagnostic(hourly: pd.DataFrame) -> dict[str, Any]:
    total_rows = int(len(hourly))
    capped_rows = int(hourly["is_capped_hour"].sum())
    capped_fraction = capped_rows / total_rows if total_rows else 0.0
    capped = hourly[hourly["is_capped_hour"] == 1]
    onset = iso_hour(capped.iloc[0]["hour_dt"]) if not capped.empty else None
    daily = []
    for date, group in hourly.groupby(hourly["hour_dt"].dt.strftime("%Y-%m-%d")):
        daily.append(
            {
                "date": date,
                "rows": int(len(group)),
                "capped_rows": int(group["is_capped_hour"].sum()),
                "capped_frac": float(group["is_capped_hour"].mean()) if len(group) else 0.0,
            }
        )
    return {
        "total_rows": total_rows,
        "capped_rows": capped_rows,
        "capped_fraction": capped_fraction,
        "capped_percent": capped_fraction * 100,
        "onset_hour": onset,
        "daily": daily,
        "known_distribution": {
            "before_2026_05_26": "0%",
            "2026_05_26": "50%",
            "2026_05_27_to_2026_05_30": "100%",
            "2026_05_31": "83%",
        },
        "confounding_warning": CONFOUNDING_WARNING,
        "under_flag_warning": UNDER_FLAG_WARNING,
    }


def plateau_diagnostic(hourly: pd.DataFrame) -> dict[str, Any]:
    mask = (hourly["tx_count"] == 5000) & (hourly["is_capped_hour"] == 0)
    plateau = hourly[mask].copy()
    if plateau.empty:
        return {"tx_count_5000_underflagged_rows": 0, "first_hour": None, "last_hour": None}
    return {
        "tx_count_5000_underflagged_rows": int(len(plateau)),
        "first_hour": iso_hour(plateau.iloc[0]["hour_dt"]),
        "last_hour": iso_hour(plateau.iloc[-1]["hour_dt"]),
    }


def metric_or_null(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def segment_metrics(rows: pd.DataFrame) -> dict[str, Any]:
    n = int(len(rows))
    base = {
        "n": n,
        "mae": None,
        "rmse": None,
        "mape": None,
        "r2": None,
        "directional_accuracy": None,
        "persistence_mae": None,
        "skill_score": None,
    }
    if n == 0:
        return base
    metrics = compute_metrics(
        rows["actual_next_hour_avg_fee"].to_numpy(dtype=float),
        rows["predicted_next_hour_avg_fee"].to_numpy(dtype=float),
    )
    base["mae"] = metric_or_null(metrics.get("mae"))
    base["rmse"] = metric_or_null(metrics.get("rmse"))
    base["directional_accuracy"] = metric_or_null(metrics.get("directional_accuracy"))
    if n >= MIN_STABLE_N:
        base["mape"] = metric_or_null(metrics.get("mape"))
        base["r2"] = metric_or_null(metrics.get("r2"))
    return base


def label_holdout_targets(hourly: pd.DataFrame, holdout: pd.DataFrame) -> pd.DataFrame:
    cap_by_hour = {
        iso_hour(row["hour_dt"]): int(row["is_capped_hour"])
        for _, row in hourly.iterrows()
    }
    labeled = holdout.copy()
    labeled["feature_hour_dt"] = pd.to_datetime(labeled["hour"], utc=True, errors="coerce")
    labeled["target_hour"] = labeled["feature_hour_dt"] + pd.Timedelta(hours=1)
    labeled["target_hour_iso"] = labeled["target_hour"].map(iso_hour)
    labeled["target_is_capped"] = labeled["target_hour_iso"].map(cap_by_hour)
    labeled["actual_next_hour_avg_fee"] = pd.to_numeric(labeled["actual_next_hour_avg_fee"], errors="coerce")
    labeled["predicted_next_hour_avg_fee"] = pd.to_numeric(labeled["predicted_next_hour_avg_fee"], errors="coerce")
    return labeled.dropna(
        subset=["target_is_capped", "actual_next_hour_avg_fee", "predicted_next_hour_avg_fee"]
    ).copy()


def holdout_segments(hourly: pd.DataFrame, holdout_path: Path) -> dict[str, Any]:
    holdout = pd.read_csv(holdout_path)
    required = {"hour", "actual_next_hour_avg_fee", "predicted_next_hour_avg_fee"}
    missing = sorted(required - set(holdout.columns))
    if missing:
        raise ValueError(f"actual_vs_predicted.csv is missing required columns: {missing}")
    labeled = label_holdout_targets(hourly, holdout)
    clean = labeled[labeled["target_is_capped"].astype(int) == 0]
    capped = labeled[labeled["target_is_capped"].astype(int) == 1]
    return {
        "matched_rows": int(len(labeled)),
        "dropped_missing_target_cap_rows": int(len(holdout) - len(labeled)),
        "segments": {
            "clean": segment_metrics(clean),
            "capped": segment_metrics(capped),
        },
    }


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return str(value)


def segment_table(segments: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        "| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in ["clean", "capped"]:
        values = segments[label]
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    fmt(values.get("n"), 0),
                    fmt(values.get("mae"), 2),
                    fmt(values.get("rmse"), 2),
                    fmt(values.get("mape"), 2),
                    fmt(values.get("r2"), 4),
                    fmt(values.get("directional_accuracy"), 4),
                    fmt(values.get("persistence_mae"), 2),
                    fmt(values.get("skill_score"), 4),
                ]
            )
            + " |"
        )
    return lines


def write_report(path: Path, payload: dict[str, Any]) -> None:
    coverage = payload["coverage"]
    plateau = payload["plateau"]
    segments = payload["segments"]
    daily_rows = coverage["daily"][-10:]
    lines = [
        "# Capped Target Diagnostic",
        "",
        "This diagnostic does not de-bias or change `target_next_hour_avg_fee`. It separates in-sample holdout "
        "metrics by whether the target hour H+1 is currently flagged as capped.",
        "",
        "## Coverage",
        "",
        f"- {KNOWN_COVERAGE_NOTE}",
        f"- Computed capped rows in current file: {coverage['capped_rows']:,} / {coverage['total_rows']:,} "
        f"({coverage['capped_percent']:.1f}%).",
        f"- Capped onset hour: {coverage['onset_hour'] or 'N/A'}",
        "- Known distribution: before 2026-05-26 = 0%, 2026-05-26 = 50%, "
        "2026-05-27 through 2026-05-30 = 100%, 2026-05-31 = 83%.",
        "",
        "## Warnings",
        "",
        f"- Confounding: {coverage['confounding_warning']}",
        f"- Under-flag limit: {coverage['under_flag_warning']}",
        f"- Plateau summary: tx_count==5000 and is_capped_hour==0 rows = "
        f"{plateau['tx_count_5000_underflagged_rows']:,}, from {plateau['first_hour'] or 'N/A'} "
        f"to {plateau['last_hour'] or 'N/A'}.",
        "",
        "## Recent Daily Capped Fraction",
        "",
        "| Date | Rows | Capped rows | Capped fraction |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in daily_rows:
        lines.append(
            f"| {row['date']} | {row['rows']:,} | {row['capped_rows']:,} | {row['capped_frac'] * 100:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## In-Sample Holdout Segments",
            "",
            "Target capping is defined as `is_capped_hour` at H+1, where H is the feature hour in "
            "`actual_vs_predicted.csv`.",
            f"Matched holdout rows: {payload['matched_rows']:,}",
            f"Dropped rows with missing H+1 cap label: {payload['dropped_missing_target_cap_rows']:,}",
            "",
            *segment_table(segments),
            "",
            "Small groups with n < 8 report MAPE/R2/skill as N/A. Directional accuracy is N/A here because "
            "the holdout file does not carry current-fee anchors.",
            "",
            "## Future Work",
            "",
            "New rows persist per-run caps in `collection_cap` and use `tx_count>=collection_cap` for capping. "
            "Legacy rows where `collection_cap` is missing should be corrected by R2 raw replay rather than "
            "heuristic relabeling.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(hourly_path: Path, holdout_path: Path) -> dict[str, Any]:
    hourly = load_hourly(hourly_path)
    coverage = coverage_diagnostic(hourly)
    plateau = plateau_diagnostic(hourly)
    holdout = holdout_segments(hourly, holdout_path)
    return {
        "generated_at_utc": utc_now_iso(),
        "coverage": coverage,
        "plateau": plateau,
        "matched_rows": holdout["matched_rows"],
        "dropped_missing_target_cap_rows": holdout["dropped_missing_target_cap_rows"],
        "segments": holdout["segments"],
        "warnings": {
            "confounding": CONFOUNDING_WARNING,
            "under_flag": UNDER_FLAG_WARNING,
        },
        "future_work": "Use R2 raw replay to rebuild legacy rows with persisted collection_cap labels.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hourly", default="hourly_features.csv")
    parser.add_argument("--holdout", default="actual_vs_predicted.csv")
    parser.add_argument("--report", default="docs/capping_diagnostic.md")
    parser.add_argument("--json", default="models/capping_diagnostic.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = build_payload(resolve_path(args.hourly), resolve_path(args.holdout))
    json_path = resolve_path(args.json)
    report_path = resolve_path(args.report)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(report_path, payload)
    print(
        json.dumps(
            {
                "status": "success",
                "capped_rows": payload["coverage"]["capped_rows"],
                "capped_percent": payload["coverage"]["capped_percent"],
                "matched_rows": payload["matched_rows"],
                "report": str(report_path),
                "json": str(json_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

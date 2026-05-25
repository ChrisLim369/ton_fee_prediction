#!/usr/bin/env python3
"""Refresh forecast outputs without committing raw history.

This script is intended for GitHub Actions. It can either collect a recent
temporary raw window or update a restored persistent raw CSV from GitHub Actions
cache, convert the available raw rows into hourly aggregates, merge those
aggregates into the committed hourly history, and regenerate the next-24-hour
forecast.

It deliberately keeps raw_transactions.csv ignored by Git.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from features import build_hourly_features, read_raw_transactions, recompute_hourly_derived_features
from generate_forecast import generate as generate_forecast
from schema import PROJECT_ROOT, resolve_path
from update_data import update as update_raw_data


def read_json_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def completed_utc_hour() -> datetime:
    now = datetime.now(UTC)
    return now.replace(minute=0, second=0, microsecond=0)


def collect_recent_raw(args: argparse.Namespace, start_dt: datetime, end_dt: datetime) -> dict[str, Any]:
    recent_raw_path = resolve_path(args.recent_raw)
    recent_status_path = resolve_path(args.recent_status)

    if args.reset_recent_raw and not args.use_raw_latest_state:
        recent_raw_path.unlink(missing_ok=True)
        recent_status_path.unlink(missing_ok=True)

    update_args = Namespace(
        raw=str(recent_raw_path),
        last_updated=str(recent_status_path),
        metadata=str(recent_status_path),
        base_url=args.base_url,
        start_date=None if args.use_raw_latest_state else start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        bootstrap_days=args.bootstrap_days,
        overlap_seconds=0,
        include_partial_hour=False,
        window_hours=args.window_hours,
        limit=args.limit,
        max_pages_per_window=args.max_pages_per_window,
        max_pages_cap=args.max_pages_cap,
        sort=args.sort,
        workchain=args.workchain,
        sleep=args.sleep,
        max_retries=args.max_retries,
        stream=args.stream,
        in_memory=False,
        verbose=args.verbose,
    )
    return update_raw_data(update_args)


def merge_hourly_features(args: argparse.Namespace, collection_status: dict[str, Any]) -> dict[str, Any]:
    recent_raw_path = resolve_path(args.recent_raw)
    hourly_path = resolve_path(args.hourly_features)

    raw_df = read_raw_transactions(recent_raw_path)
    recent_hourly = build_hourly_features(raw_df, collection_status)
    if recent_hourly.empty:
        raise ValueError("Recent transaction collection produced no hourly feature rows.")

    existing_hourly = pd.DataFrame()
    if hourly_path.exists():
        existing_hourly = pd.read_csv(hourly_path)

    merged = pd.concat([existing_hourly, recent_hourly], ignore_index=True)
    merged = recompute_hourly_derived_features(merged)

    hourly_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(hourly_path, index=False)

    return {
        "recent_raw_rows": int(len(raw_df)),
        "recent_hourly_rows": int(len(recent_hourly)),
        "hourly_rows": int(len(merged)),
        "latest_feature_hour": str(merged.iloc[-1]["hour"]),
        "oldest_feature_hour": str(merged.iloc[0]["hour"]),
    }


def update_metadata(
    args: argparse.Namespace,
    collection_status: dict[str, Any],
    merge_status: dict[str, Any],
    forecast_status: dict[str, Any],
) -> dict[str, Any]:
    last_updated_path = resolve_path(args.last_updated)
    metadata_path = resolve_path(args.metadata)
    previous = read_json_optional(last_updated_path) or read_json_optional(metadata_path)

    previous_full_rows = previous.get("final_rows")
    current_final_rows = collection_status.get("final_rows")
    generated_at = None
    predictions_path = resolve_path(args.predictions)
    if predictions_path.exists():
        try:
            predictions = pd.read_csv(predictions_path)
            if not predictions.empty:
                generated_at = predictions.iloc[0].get("forecast_generated_at")
        except (OSError, pd.errors.ParserError, KeyError):
            generated_at = None

    payload = {
        **collection_status,
        "status": "success",
        "automation_mode": "persistent_raw_cache_merge" if args.use_raw_latest_state else "recent_raw_merge",
        "update_finished_at_utc": datetime.now(UTC).isoformat(),
        "recent_raw_path": str(resolve_path(args.recent_raw).relative_to(PROJECT_ROOT)),
        "recent_raw_rows_collected": merge_status["recent_raw_rows"],
        "recent_hourly_rows": merge_status["recent_hourly_rows"],
        "hourly_rows": merge_status["hourly_rows"],
        "oldest_feature_hour": merge_status["oldest_feature_hour"],
        "latest_feature_hour": merge_status["latest_feature_hour"],
        "forecast_generated_at": generated_at,
        "forecast_start": forecast_status.get("forecast_start"),
        "forecast_end": forecast_status.get("forecast_end"),
        "previous_known_full_raw_rows": previous_full_rows,
        "final_rows": current_final_rows or previous_full_rows,
        "raw_rows_note": (
            "raw_transactions.csv is not committed to Git. In GitHub Actions-only mode, "
            "the ignored raw CSV is restored from and saved back to the GitHub Actions cache "
            "when available. If no cache exists, the workflow bootstraps a recent raw window."
        ),
        "note": (
            "Automated refresh updated the available raw transaction state, merged refreshed hourly "
            "aggregates into hourly_features.csv history, and regenerated predictions.csv. "
            "Transaction count features remain sampled when TON Center page limits are reached."
        ),
    }
    if previous_full_rows is not None and current_final_rows is not None:
        previous_rows = int(previous_full_rows)
        current_rows = int(current_final_rows)
        if current_rows < previous_rows * 0.9:
            payload["status"] = "degraded"
            payload["degradation_reason"] = (
                f"raw row count regressed from {previous_rows} to {current_rows}; "
                "refusing to publish a potentially truncated dataset"
            )

    write_json(last_updated_path, payload)
    write_json(metadata_path, payload)
    return payload


def refresh(args: argparse.Namespace) -> dict[str, Any]:
    if not args.use_raw_latest_state and args.lookback_hours < 26:
        raise ValueError("--lookback-hours must be at least 26 so 24-hour lag features can be recomputed.")

    end_dt = completed_utc_hour()
    start_dt = end_dt - timedelta(hours=args.lookback_hours)
    if start_dt >= end_dt:
        raise ValueError("Recent refresh start time must be before end time.")

    collection_status = collect_recent_raw(args, start_dt, end_dt)
    merge_status = merge_hourly_features(args, collection_status)
    forecast_status = generate_forecast(
        Namespace(
            features=args.hourly_features,
            model=args.model,
            output=args.predictions,
            horizon_hours=args.horizon_hours,
        )
    )
    metadata = update_metadata(args, collection_status, merge_status, forecast_status)

    if not args.keep_temp and not args.preserve_raw:
        resolve_path(args.recent_raw).unlink(missing_ok=True)
        resolve_path(args.recent_status).unlink(missing_ok=True)

    return {
        "status": "success",
        "raw_mode": "persistent_cache" if args.use_raw_latest_state else "recent_window",
        "lookback_hours": args.lookback_hours,
        "latest_feature_hour": metadata.get("latest_feature_hour"),
        "forecast_start": forecast_status.get("forecast_start"),
        "forecast_end": forecast_status.get("forecast_end"),
        "recent_raw_rows_collected": metadata.get("recent_raw_rows_collected"),
        "hourly_rows": metadata.get("hourly_rows"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lookback-hours", type=int, default=72)
    parser.add_argument(
        "--bootstrap-days",
        type=int,
        default=3,
        help="Lookback used by update_data.py when the selected raw CSV does not exist.",
    )
    parser.add_argument("--recent-raw", default=".automation_recent_raw_transactions.csv")
    parser.add_argument("--recent-status", default=".automation_recent_last_updated.json")
    parser.add_argument("--hourly-features", default="hourly_features.csv")
    parser.add_argument("--model", default="models/best_model.json")
    parser.add_argument("--predictions", default="predictions.csv")
    parser.add_argument("--last-updated", default="last_updated.json")
    parser.add_argument("--metadata", default="collection_metadata.json")
    parser.add_argument("--horizon-hours", type=int, default=24)
    parser.add_argument("--base-url", default="https://toncenter.com/api/v3")
    parser.add_argument("--window-hours", type=int, default=1)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-pages-per-window", type=int, default=1)
    parser.add_argument("--max-pages-cap", type=int, default=10)
    parser.add_argument("--sort", choices=["asc", "desc", "both"], default="asc")
    parser.add_argument("--workchain", default="0")
    parser.add_argument("--sleep", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument(
        "--preserve-raw",
        action="store_true",
        help="Keep the selected raw/status files after refresh, for GitHub Actions cache persistence.",
    )
    parser.add_argument(
        "--use-raw-latest-state",
        action="store_true",
        help="Let update_data.py continue from the selected raw CSV latest timestamp instead of forcing a fixed recent window.",
    )
    parser.add_argument("--reset-recent-raw", action="store_true", default=True)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    if args.max_pages_cap < args.max_pages_per_window:
        raise ValueError("--max-pages-cap must be at least --max-pages-per-window")
    result = refresh(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

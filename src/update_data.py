#!/usr/bin/env python3
"""Incrementally update raw TON transaction data.

The update process:
1. Read the latest collected timestamp/logical time from raw_transactions.csv.
2. Fetch TON Center v3 transactions after that point, with a small overlap.
3. Merge, de-duplicate by transaction hash and logical time, and rewrite CSV.
4. Save last_updated.json with update status and latest collection state.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from ingestion import as_int, fetch_transactions, flatten_transaction, iter_windows, parse_utc, write_raw_csv
from schema import PROJECT_ROOT, RAW_COLUMNS, resolve_path

logger = logging.getLogger(__name__)


def load_existing_raw(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=RAW_COLUMNS)
    df = pd.read_csv(path)
    for column in RAW_COLUMNS:
        if column not in df.columns:
            df[column] = None
    return df[RAW_COLUMNS]


def latest_state(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"latest_now": None, "latest_lt": None, "latest_iso_utc": None}
    now_series = pd.to_numeric(df["now"], errors="coerce")
    lt_series = pd.to_numeric(df["lt"], errors="coerce")
    latest_now = int(now_series.max()) if now_series.notna().any() else None
    latest_lt = int(lt_series.max()) if lt_series.notna().any() else None
    latest_iso = datetime.fromtimestamp(latest_now, UTC).isoformat() if latest_now else None
    return {"latest_now": latest_now, "latest_lt": latest_lt, "latest_iso_utc": latest_iso}


def save_last_updated(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def default_end_datetime(include_partial_hour: bool) -> datetime:
    now = datetime.now(UTC).replace(microsecond=0)
    if include_partial_hour:
        return now
    return now.replace(minute=0, second=0)


def hour_labels(start_dt: datetime, end_dt: datetime) -> list[str]:
    labels = []
    current = start_dt.replace(minute=0, second=0, microsecond=0)
    while current < end_dt:
        labels.append(current.isoformat().replace("+00:00", "Z"))
        current += timedelta(hours=1)
    return labels


def update_state_from_row(state: dict[str, Any], row: dict[str, Any]) -> None:
    now_value = as_int(row.get("now"), None)
    lt_value = as_int(row.get("lt"), None)
    if now_value is not None and (
        state["latest_now"] is None or now_value > state["latest_now"]
    ):
        state["latest_now"] = now_value
        state["latest_iso_utc"] = datetime.fromtimestamp(now_value, UTC).isoformat()
    if lt_value is not None and (
        state["latest_lt"] is None or lt_value > state["latest_lt"]
    ):
        state["latest_lt"] = lt_value


def stream_update(args: argparse.Namespace) -> dict[str, Any]:
    """Large-range update that rewrites a de-duplicated raw CSV through a temp file."""
    raw_path = resolve_path(args.raw)
    last_updated_path = resolve_path(args.last_updated)
    metadata_path = resolve_path(args.metadata)
    temp_path = raw_path.with_name(f".{raw_path.name}.tmp")
    started_at = datetime.now(UTC)
    raw_path_status = str(raw_path.relative_to(PROJECT_ROOT))

    existing_keys: set[tuple[str, str]] = set()
    before_state = {"latest_now": None, "latest_lt": None, "latest_iso_utc": None}
    old_rows = 0

    try:
        with temp_path.open("w", newline="", encoding="utf-8") as output_handle:
            writer = csv.DictWriter(output_handle, fieldnames=RAW_COLUMNS)
            writer.writeheader()

            if raw_path.exists():
                with raw_path.open("r", newline="", encoding="utf-8") as input_handle:
                    reader = csv.DictReader(input_handle)
                    for source_row in reader:
                        row = {column: source_row.get(column) for column in RAW_COLUMNS}
                        key = (str(row.get("hash") or ""), str(row.get("lt") or ""))
                        if not key[0] or key in existing_keys:
                            continue
                        existing_keys.add(key)
                        writer.writerow(row)
                        old_rows += 1
                        update_state_from_row(before_state, row)

            end_dt = parse_utc(args.end_date) or default_end_datetime(args.include_partial_hour)
            use_start_lt = bool(before_state["latest_lt"] is not None and not args.start_date)
            if args.start_date:
                start_dt = parse_utc(args.start_date)
            elif before_state["latest_now"] is not None:
                start_dt = datetime.fromtimestamp(before_state["latest_now"], UTC) - timedelta(
                    seconds=args.overlap_seconds
                )
            else:
                start_dt = end_dt - timedelta(days=args.bootstrap_days)

            if start_dt is None:
                raise ValueError("Unable to determine start time")
            if start_dt >= end_dt:
                status = {
                    "status": "skipped",
                    "reason": "start time is not before end time",
                    "update_started_at_utc": started_at.isoformat(),
                    "update_finished_at_utc": datetime.now(UTC).isoformat(),
                    "raw_path": raw_path_status,
                    **before_state,
                }
                save_last_updated(last_updated_path, status)
                temp_path.unlink(missing_ok=True)
                return status

            api_key = os.getenv("TONCENTER_API_KEY") or os.getenv("TON_API_KEY")
            sleep_seconds = args.sleep if args.sleep is not None else (0.12 if api_key else 1.1)
            session = requests.Session()
            after_state = dict(before_state)
            fetched_rows = 0
            new_rows_added = 0
            request_count = 0
            windows_processed = 0
            windows_with_limit_hits = 0
            capped_hours: set[str] = set()
            sorts = ["asc", "desc"] if args.sort == "both" else [args.sort]

            for window_start, window_end in iter_windows(start_dt, end_dt, args.window_hours):
                windows_processed += 1
                for sort in sorts:
                    for page in range(args.max_pages_cap):
                        params = {
                            "start_utime": int(window_start.timestamp()),
                            "end_utime": int(window_end.timestamp()),
                            "limit": args.limit,
                            "offset": page * args.limit,
                            "sort": sort,
                        }
                        if args.workchain != "all":
                            params["workchain"] = int(args.workchain)
                        if use_start_lt:
                            params["start_lt"] = int(before_state["latest_lt"]) + 1

                        transactions = fetch_transactions(
                            session=session,
                            base_url=args.base_url,
                            api_key=api_key,
                            params=params,
                            max_retries=args.max_retries,
                        )
                        request_count += 1
                        fetched_rows += len(transactions)

                        for tx in transactions:
                            row = flatten_transaction(tx)
                            key = (str(row.get("hash") or ""), str(row.get("lt") or ""))
                            if not key[0] or key in existing_keys:
                                continue
                            existing_keys.add(key)
                            writer.writerow({column: row.get(column) for column in RAW_COLUMNS})
                            new_rows_added += 1
                            update_state_from_row(after_state, row)

                        output_handle.flush()

                        if len(transactions) == args.limit:
                            windows_with_limit_hits += 1
                            capped_hours.update(hour_labels(window_start, window_end))

                        if args.verbose:
                            logger.info(
                                f"{window_start.isoformat()} sort={sort} page={page + 1} "
                                f"fetched={len(transactions)} new_rows={new_rows_added}"
                            )

                        if len(transactions) < args.limit:
                            break
                        time.sleep(sleep_seconds * random.uniform(0.9, 1.1))
                time.sleep(sleep_seconds * random.uniform(0.9, 1.1))

        temp_path.replace(raw_path)
        finished_at = datetime.now(UTC)
        status = {
            "status": "success",
            "mode": "stream",
            "endpoint": f"{args.base_url.rstrip('/')}/transactions",
            "api_key_used": bool(api_key),
            "raw_path": raw_path_status,
            "update_started_at_utc": started_at.isoformat(),
            "update_finished_at_utc": finished_at.isoformat(),
            "query_start_utc": start_dt.isoformat(),
            "query_end_utc": end_dt.isoformat(),
            "incremental_mode": "start_lt" if use_start_lt else "utime",
            "query_start_lt": int(before_state["latest_lt"]) + 1 if use_start_lt else None,
            "previous_latest_now": before_state["latest_now"],
            "previous_latest_iso_utc": before_state["latest_iso_utc"],
            "latest_now": after_state["latest_now"],
            "latest_iso_utc": after_state["latest_iso_utc"],
            "latest_lt": after_state["latest_lt"],
            "old_rows": int(old_rows),
            "fetched_rows": int(fetched_rows),
            "new_rows_added": int(new_rows_added),
            "final_rows": int(old_rows + new_rows_added),
            "request_count": request_count,
            "windows_processed": windows_processed,
            "windows_with_limit_hits": windows_with_limit_hits,
            "limit": args.limit,
            "max_pages_per_window": args.max_pages_per_window,
            "max_pages_cap": args.max_pages_cap,
            "window_hours": args.window_hours,
            "sort": args.sort,
            "workchain": args.workchain,
            "capped_hours_utc": sorted(capped_hours),
            "note": (
                "Streaming mode rewrites a de-duplicated raw CSV through a temp file. "
                "If windows_with_limit_hits is greater than zero, increase "
                "--max-pages-per-window for fuller hourly coverage."
            ),
        }
        save_last_updated(last_updated_path, status)
        metadata_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
        return status

    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        failure = {
            "status": "failed",
            "mode": "stream",
            "error": str(exc),
            "raw_path": raw_path_status,
            "update_started_at_utc": started_at.isoformat(),
            "update_finished_at_utc": datetime.now(UTC).isoformat(),
            **before_state,
        }
        save_last_updated(last_updated_path, failure)
        raise


def update(args: argparse.Namespace) -> dict[str, Any]:
    if not getattr(args, "in_memory", False):
        return stream_update(args)

    raw_path = resolve_path(args.raw)
    last_updated_path = resolve_path(args.last_updated)
    metadata_path = resolve_path(args.metadata)
    started_at = datetime.now(UTC)
    raw_path_status = str(raw_path.relative_to(PROJECT_ROOT))

    existing = load_existing_raw(raw_path)
    before_state = latest_state(existing)

    end_dt = parse_utc(args.end_date) or default_end_datetime(args.include_partial_hour)
    use_start_lt = bool(before_state["latest_lt"] is not None and not args.start_date)
    if args.start_date:
        start_dt = parse_utc(args.start_date)
    elif before_state["latest_now"] is not None:
        # The overlap protects against transactions that share the latest second
        # or late API indexing; de-duplication keeps the raw CSV stable.
        start_dt = datetime.fromtimestamp(before_state["latest_now"], UTC) - timedelta(seconds=args.overlap_seconds)
    else:
        start_dt = end_dt - timedelta(days=args.bootstrap_days)

    if start_dt is None:
        raise ValueError("Unable to determine start time")
    if start_dt >= end_dt:
        status = {
            "status": "skipped",
            "reason": "start time is not before end time",
            "update_started_at_utc": started_at.isoformat(),
            "update_finished_at_utc": datetime.now(UTC).isoformat(),
            "raw_path": raw_path_status,
            **before_state,
        }
        save_last_updated(last_updated_path, status)
        return status

    api_key = os.getenv("TONCENTER_API_KEY") or os.getenv("TON_API_KEY")
    sleep_seconds = args.sleep if args.sleep is not None else (0.12 if api_key else 1.1)
    session = requests.Session()

    fetched_rows: list[dict[str, Any]] = []
    request_count = 0
    windows_processed = 0
    windows_with_limit_hits = 0
    capped_hours: set[str] = set()
    sorts = ["asc", "desc"] if args.sort == "both" else [args.sort]

    try:
        for window_start, window_end in iter_windows(start_dt, end_dt, args.window_hours):
            windows_processed += 1
            for sort in sorts:
                for page in range(args.max_pages_cap):
                    params = {
                        "start_utime": int(window_start.timestamp()),
                        "end_utime": int(window_end.timestamp()),
                        "limit": args.limit,
                        "offset": page * args.limit,
                        "sort": sort,
                    }
                    if args.workchain != "all":
                        params["workchain"] = int(args.workchain)
                    if use_start_lt:
                        params["start_lt"] = int(before_state["latest_lt"]) + 1

                    transactions = fetch_transactions(
                        session=session,
                        base_url=args.base_url,
                        api_key=api_key,
                        params=params,
                        max_retries=args.max_retries,
                    )
                    request_count += 1
                    fetched_rows.extend(flatten_transaction(tx) for tx in transactions)

                    if len(transactions) == args.limit:
                        windows_with_limit_hits += 1
                        capped_hours.update(hour_labels(window_start, window_end))

                    if args.verbose:
                        logger.info(
                            f"{window_start.isoformat()} sort={sort} page={page + 1} "
                            f"fetched={len(transactions)} total_fetched={len(fetched_rows)}"
                        )

                    if len(transactions) < args.limit:
                        break
                    time.sleep(sleep_seconds * random.uniform(0.9, 1.1))
            time.sleep(sleep_seconds * random.uniform(0.9, 1.1))

        fetched = pd.DataFrame(fetched_rows, columns=RAW_COLUMNS)
        old_keys = set(zip(existing["hash"].astype(str), existing["lt"].astype(str), strict=False))
        merged = pd.concat([existing, fetched], ignore_index=True)
        merged = merged.drop_duplicates(subset=["hash", "lt"], keep="last")
        merged["now_sort"] = pd.to_numeric(merged["now"], errors="coerce")
        merged["lt_sort"] = pd.to_numeric(merged["lt"], errors="coerce")
        merged = merged.sort_values(["now_sort", "account", "lt_sort"], na_position="last")
        merged = merged.drop(columns=["now_sort", "lt_sort"])

        new_keys = set(zip(merged["hash"].astype(str), merged["lt"].astype(str), strict=False))
        new_rows_added = len(new_keys - old_keys)
        write_raw_csv(raw_path, merged[RAW_COLUMNS].to_dict("records"))

        after_state = latest_state(merged)
        finished_at = datetime.now(UTC)
        status = {
            "status": "success",
            "endpoint": f"{args.base_url.rstrip('/')}/transactions",
            "api_key_used": bool(api_key),
            "raw_path": raw_path_status,
            "update_started_at_utc": started_at.isoformat(),
            "update_finished_at_utc": finished_at.isoformat(),
            "query_start_utc": start_dt.isoformat(),
            "query_end_utc": end_dt.isoformat(),
            "incremental_mode": "start_lt" if use_start_lt else "utime",
            "query_start_lt": int(before_state["latest_lt"]) + 1 if use_start_lt else None,
            "previous_latest_now": before_state["latest_now"],
            "previous_latest_iso_utc": before_state["latest_iso_utc"],
            "latest_now": after_state["latest_now"],
            "latest_iso_utc": after_state["latest_iso_utc"],
            "latest_lt": after_state["latest_lt"],
            "old_rows": int(len(existing)),
            "fetched_rows": int(len(fetched)),
            "new_rows_added": int(new_rows_added),
            "final_rows": int(len(merged)),
            "request_count": request_count,
            "windows_processed": windows_processed,
            "windows_with_limit_hits": windows_with_limit_hits,
            "limit": args.limit,
            "max_pages_per_window": args.max_pages_per_window,
            "max_pages_cap": args.max_pages_cap,
            "window_hours": args.window_hours,
            "sort": args.sort,
            "workchain": args.workchain,
            "capped_hours_utc": sorted(capped_hours),
            "note": (
                "If windows_with_limit_hits is greater than zero, the update may be a "
                "sample of a high-volume hour. Increase --max-pages-per-window and use "
                "TONCENTER_API_KEY for fuller coverage."
            ),
        }
        save_last_updated(last_updated_path, status)
        metadata_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
        return status

    except Exception as exc:
        failure = {
            "status": "failed",
            "error": str(exc),
            "raw_path": raw_path_status,
            "update_started_at_utc": started_at.isoformat(),
            "update_finished_at_utc": datetime.now(UTC).isoformat(),
            "query_start_utc": start_dt.isoformat(),
            "query_end_utc": end_dt.isoformat(),
            **before_state,
        }
        save_last_updated(last_updated_path, failure)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default="raw_transactions.csv")
    parser.add_argument("--last-updated", default="last_updated.json")
    parser.add_argument("--metadata", default="collection_metadata.json")
    parser.add_argument("--base-url", default="https://toncenter.com/api/v3")
    parser.add_argument("--start-date", default=None, help="Override UTC start date for this update.")
    parser.add_argument("--end-date", default=None, help="Override UTC end date for this update.")
    parser.add_argument("--bootstrap-days", type=int, default=1, help="Lookback used when raw CSV does not exist.")
    parser.add_argument("--overlap-seconds", type=int, default=300, help="Re-fetch overlap before latest timestamp.")
    parser.add_argument(
        "--include-partial-hour",
        action="store_true",
        help="Include the currently in-progress UTC hour instead of stopping at the last completed hour.",
    )
    parser.add_argument("--window-hours", type=int, default=1)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-pages-per-window", type=int, default=1)
    parser.add_argument("--max-pages-cap", type=int, default=10)
    parser.add_argument("--sort", choices=["asc", "desc", "both"], default="asc")
    parser.add_argument("--workchain", default="0", help="Integer workchain or 'all'.")
    parser.add_argument("--sleep", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument(
        "--stream",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--in-memory", action="store_true", help="Keep fetched rows in memory before writing raw CSV.")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    if args.limit < 1 or args.limit > 1000:
        parser.error("--limit must be between 1 and 1000")
    if args.window_hours < 1:
        parser.error("--window-hours must be at least 1")
    if args.max_pages_per_window < 1:
        parser.error("--max-pages-per-window must be at least 1")
    if args.max_pages_cap < args.max_pages_per_window:
        parser.error("--max-pages-cap must be at least --max-pages-per-window")
    if args.workchain != "all":
        try:
            int(args.workchain)
        except ValueError:
            parser.error("--workchain must be an integer or 'all'")

    status = update(args)
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

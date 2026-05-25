#!/usr/bin/env python3
"""Collect TON transaction-level data from TON Center API v3.

Endpoint used:
    GET https://toncenter.com/api/v3/transactions

The script intentionally stores a flat raw CSV first. Feature aggregation is
handled separately in build_hourly_features.py so the collection step remains
auditable and reproducible.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ingestion import fetch_transactions, flatten_transaction, iter_windows, parse_utc, write_raw_csv  # noqa: E402


logger = logging.getLogger(__name__)


def hour_labels(start_dt: datetime, end_dt: datetime) -> list[str]:
    labels = []
    current = start_dt.replace(minute=0, second=0, microsecond=0)
    while current < end_dt:
        labels.append(current.isoformat().replace("+00:00", "Z"))
        current += timedelta(hours=1)
    return labels


def collect(args: argparse.Namespace) -> dict[str, Any]:
    """Collect and de-duplicate transaction rows across time windows."""
    end_dt = parse_utc(args.end_date) or datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start_dt = parse_utc(args.start_date) or (end_dt - timedelta(days=args.days))

    if start_dt >= end_dt:
        raise ValueError("start date must be before end date")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("TONCENTER_API_KEY") or os.getenv("TON_API_KEY")
    sleep_seconds = args.sleep if args.sleep is not None else (0.12 if api_key else 1.1)
    sorts = ["asc", "desc"] if args.sort == "both" else [args.sort]

    rows_by_key: dict[tuple[str, int | None], dict[str, Any]] = {}
    request_count = 0
    windows_processed = 0
    windows_with_limit_hits = 0
    capped_hours: set[str] = set()
    session = requests.Session()

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
                transactions = fetch_transactions(
                    session=session,
                    base_url=args.base_url,
                    api_key=api_key,
                    params=params,
                    max_retries=args.max_retries,
                )
                request_count += 1

                for tx in transactions:
                    row = flatten_transaction(tx)
                    key = (row.get("hash") or "", row.get("lt"))
                    if key[0]:
                        rows_by_key[key] = row

                if len(transactions) == args.limit:
                    windows_with_limit_hits += 1
                    capped_hours.update(hour_labels(window_start, window_end))

                if args.verbose:
                    logger.info(
                        f"{window_start.isoformat()} sort={sort} page={page + 1} "
                        f"fetched={len(transactions)} unique_rows={len(rows_by_key)}"
                    )

                if len(transactions) < args.limit:
                    break
                time.sleep(sleep_seconds * random.uniform(0.9, 1.1))
        time.sleep(sleep_seconds * random.uniform(0.9, 1.1))

    rows = list(rows_by_key.values())
    if args.max_rows and len(rows) > args.max_rows:
        rows = random.Random(42).sample(rows, args.max_rows)

    rows = sorted(
        rows,
        key=lambda row: ((row.get("now") or 0), str(row.get("account") or ""), row.get("lt") or 0),
    )

    write_raw_csv(output_path, rows)

    metadata = {
        "endpoint": f"{args.base_url.rstrip('/')}/transactions",
        "api_key_used": bool(api_key),
        "start_utc": start_dt.isoformat(),
        "end_utc": end_dt.isoformat(),
        "window_hours": args.window_hours,
        "limit": args.limit,
        "max_pages_per_window": args.max_pages_per_window,
        "max_pages_cap": args.max_pages_cap,
        "sort": args.sort,
        "workchain": args.workchain,
        "request_count": request_count,
        "windows_processed": windows_processed,
        "windows_with_limit_hits": windows_with_limit_hits,
        "capped_hours_utc": sorted(capped_hours),
        "unique_transactions": len(rows),
        "output": str(output_path),
        "notes": (
            "If windows_with_limit_hits is greater than zero, at least one request returned "
            "exactly the page limit; the CSV should be treated as a time-window sample unless "
            "additional pages are collected."
        ),
    }

    metadata_path = output_path.with_name("collection_metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://toncenter.com/api/v3")
    parser.add_argument("--output", default="raw_transactions.csv")
    parser.add_argument("--start-date", default=None, help="UTC YYYY-MM-DD or ISO timestamp.")
    parser.add_argument("--end-date", default=None, help="UTC YYYY-MM-DD or ISO timestamp. Defaults to current UTC hour.")
    parser.add_argument("--days", type=int, default=30, help="Lookback days when --start-date is omitted.")
    parser.add_argument("--window-hours", type=int, default=1, help="Collection bucket size in hours.")
    parser.add_argument("--limit", type=int, default=1000, help="Rows per API request; TON Center maximum is 1000.")
    parser.add_argument("--max-pages-per-window", type=int, default=1, help="Increase for more complete hourly windows.")
    parser.add_argument("--max-pages-cap", type=int, default=10, help="Hard cap for dynamic page expansion per window.")
    parser.add_argument("--sort", choices=["asc", "desc", "both"], default="asc")
    parser.add_argument(
        "--workchain",
        default="0",
        help="Workchain filter. Default 0 for basechain user transactions; use 'all' to include every workchain.",
    )
    parser.add_argument("--max-rows", type=int, default=None, help="Optional cap for quick sampling/debugging.")
    parser.add_argument("--sleep", type=float, default=None, help="Seconds between requests. Defaults to 1.1 without API key.")
    parser.add_argument("--max-retries", type=int, default=5)
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

    metadata = collect(args)
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

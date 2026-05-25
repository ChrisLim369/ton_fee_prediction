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
import csv
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests


RAW_COLUMNS = [
    "hash",
    "now",
    "account",
    "lt",
    "mc_block_seqno",
    "total_fees",
    "compute_gas_used",
    "compute_gas_fees",
    "storage_fees_collected",
    "storage_fees_due",
    "total_action_fees",
    "total_fwd_fees",
    "in_msg_import_fee",
    "in_msg_fwd_fee",
    "out_msg_fwd_fee_sum",
    "out_msg_count",
    "vm_steps",
    "msgs_created",
    "tot_actions",
    "msg_size_bits",
    "msg_size_cells",
    "aborted",
    "compute_success",
    "action_success",
    "transaction_type",
    "account_type",
    "bounce",
    "destroyed",
    "balance_change",
    "transaction_value",
    "in_msg_value",
    "out_msg_value_sum",
]


def parse_utc(value: str | None) -> datetime | None:
    """Parse YYYY-MM-DD or ISO timestamp as an aware UTC datetime."""
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    if "T" not in normalized and len(normalized) == 10:
        normalized = f"{normalized}T00:00:00+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def as_int(value: Any, default: int | None = 0) -> int | None:
    """Convert TON Center string/integer numeric fields to int safely."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool | None:
    """Return booleans as booleans and preserve missing flags as null."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def nested(data: dict[str, Any], *keys: str) -> Any:
    """Read a nested dictionary path, returning None if any level is absent."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def sum_message_field(messages: list[dict[str, Any]] | None, field: str) -> int:
    """Sum a numeric field across outbound messages."""
    if not messages:
        return 0
    return sum(as_int(message.get(field), 0) or 0 for message in messages)


def flatten_transaction(tx: dict[str, Any]) -> dict[str, Any]:
    """Flatten one TON Center API v3 transaction into the project raw schema."""
    desc = tx.get("description") or {}
    compute_ph = desc.get("compute_ph") or {}
    storage_ph = desc.get("storage_ph") or {}
    action = desc.get("action") or {}
    msg_size = action.get("tot_msg_size") or {}
    in_msg = tx.get("in_msg") or {}
    out_msgs = tx.get("out_msgs") or []

    balance_before = as_int(nested(tx, "account_state_before", "balance"), None)
    balance_after = as_int(nested(tx, "account_state_after", "balance"), None)
    balance_change = (
        balance_after - balance_before
        if balance_before is not None and balance_after is not None
        else None
    )

    in_msg_value = as_int(in_msg.get("value"), 0) if in_msg else 0
    out_msg_value_sum = sum_message_field(out_msgs, "value")

    return {
        "hash": tx.get("hash"),
        "now": as_int(tx.get("now"), None),
        "account": tx.get("account"),
        "lt": as_int(tx.get("lt"), None),
        "mc_block_seqno": as_int(tx.get("mc_block_seqno"), None),
        "total_fees": as_int(tx.get("total_fees"), 0),
        "compute_gas_used": as_int(compute_ph.get("gas_used"), 0),
        "compute_gas_fees": as_int(compute_ph.get("gas_fees"), 0),
        "storage_fees_collected": as_int(storage_ph.get("storage_fees_collected"), 0),
        "storage_fees_due": as_int(storage_ph.get("storage_fees_due"), 0),
        "total_action_fees": as_int(action.get("total_action_fees"), 0),
        "total_fwd_fees": as_int(action.get("total_fwd_fees"), 0),
        "in_msg_import_fee": as_int(in_msg.get("import_fee"), 0) if in_msg else 0,
        "in_msg_fwd_fee": as_int(in_msg.get("fwd_fee"), 0) if in_msg else 0,
        "out_msg_fwd_fee_sum": sum_message_field(out_msgs, "fwd_fee"),
        "out_msg_count": len(out_msgs),
        "vm_steps": as_int(compute_ph.get("vm_steps"), 0),
        "msgs_created": as_int(action.get("msgs_created"), 0),
        "tot_actions": as_int(action.get("tot_actions"), 0),
        "msg_size_bits": as_int(msg_size.get("bits"), 0),
        "msg_size_cells": as_int(msg_size.get("cells"), 0),
        "aborted": as_bool(desc.get("aborted")),
        "compute_success": as_bool(compute_ph.get("success")),
        "action_success": as_bool(action.get("success")),
        "transaction_type": desc.get("type"),
        "account_type": nested(tx, "account_state_before", "account_status")
        or tx.get("orig_status"),
        "bounce": as_bool(in_msg.get("bounce")) if in_msg else None,
        "destroyed": as_bool(desc.get("destroyed")),
        "balance_change": balance_change,
        # Throughput metric: total TON value carried by inbound and outbound
        # messages for this transaction. Values are in nanoton.
        "transaction_value": in_msg_value + out_msg_value_sum,
        "in_msg_value": in_msg_value,
        "out_msg_value_sum": out_msg_value_sum,
    }


def fetch_transactions(
    session: requests.Session,
    base_url: str,
    api_key: str | None,
    params: dict[str, Any],
    max_retries: int,
) -> list[dict[str, Any]]:
    """Fetch one page from /transactions with retry/backoff for 429/5xx."""
    headers = {"X-API-Key": api_key} if api_key else {}
    url = f"{base_url.rstrip('/')}/transactions"
    last_error: str | None = None

    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=60)
        except requests.RequestException as exc:
            last_error = str(exc)
            wait = min(2**attempt, 30)
            time.sleep(wait)
            continue

        if response.status_code == 200:
            payload = response.json()
            return payload.get("transactions", [])

        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 60)
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            time.sleep(wait)
            continue

        raise RuntimeError(
            f"TON Center request failed with HTTP {response.status_code}: {response.text[:500]}"
        )

    raise RuntimeError(f"TON Center request failed after retries: {last_error}")


def iter_windows(start_dt: datetime, end_dt: datetime, window_hours: int):
    """Yield half-open UTC time windows [start, end)."""
    current = start_dt
    delta = timedelta(hours=window_hours)
    while current < end_dt:
        window_end = min(current + delta, end_dt)
        yield current, window_end
        current = window_end


def write_rows(output_path: Path, rows: list[dict[str, Any]]) -> None:
    """Write raw rows to CSV with the requested stable column order."""
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in RAW_COLUMNS})


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
    session = requests.Session()

    for window_start, window_end in iter_windows(start_dt, end_dt, args.window_hours):
        windows_processed += 1
        for sort in sorts:
            for page in range(args.max_pages_per_window):
                if args.max_rows and len(rows_by_key) >= args.max_rows:
                    break

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

                if args.verbose:
                    print(
                        f"{window_start.isoformat()} sort={sort} page={page + 1} "
                        f"fetched={len(transactions)} unique_rows={len(rows_by_key)}",
                        flush=True,
                    )

                if len(transactions) < args.limit:
                    break
                time.sleep(sleep_seconds)

            if args.max_rows and len(rows_by_key) >= args.max_rows:
                break
        if args.max_rows and len(rows_by_key) >= args.max_rows:
            break
        time.sleep(sleep_seconds)

    rows = sorted(
        rows_by_key.values(),
        key=lambda row: ((row.get("now") or 0), str(row.get("account") or ""), row.get("lt") or 0),
    )
    if args.max_rows:
        rows = rows[: args.max_rows]

    write_rows(output_path, rows)

    metadata = {
        "endpoint": f"{args.base_url.rstrip('/')}/transactions",
        "api_key_used": bool(api_key),
        "start_utc": start_dt.isoformat(),
        "end_utc": end_dt.isoformat(),
        "window_hours": args.window_hours,
        "limit": args.limit,
        "max_pages_per_window": args.max_pages_per_window,
        "sort": args.sort,
        "workchain": args.workchain,
        "request_count": request_count,
        "windows_processed": windows_processed,
        "windows_with_limit_hits": windows_with_limit_hits,
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
    if args.limit < 1 or args.limit > 1000:
        parser.error("--limit must be between 1 and 1000")
    if args.window_hours < 1:
        parser.error("--window-hours must be at least 1")
    if args.max_pages_per_window < 1:
        parser.error("--max-pages-per-window must be at least 1")
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

"""TON Center transaction ingestion helpers."""

from __future__ import annotations

import csv
import logging
import random
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

try:
    from schema import RAW_COLUMNS as RAW_COLUMNS
except ModuleNotFoundError:
    from .schema import RAW_COLUMNS as RAW_COLUMNS


logger = logging.getLogger(__name__)
USER_AGENT = "ton-fee-prediction/1.0 (+https://github.com/ChrisLim369/ton_fee_prediction)"


def parse_utc(value: str | None) -> datetime | None:
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
    if value is None or value == "":
        return default
    try:
        if isinstance(value, str):
            return int(value, 0)
        return int(value)
    except (TypeError, ValueError):
        logger.warning("as_int parse failure: %r", value)
        return default


def as_bool(value: Any) -> bool | None:
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
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def sum_message_field(messages: list[dict[str, Any]] | None, field: str) -> int:
    if not messages:
        return 0
    return sum(as_int(message.get(field), 0) or 0 for message in messages)


def flatten_transaction(tx: dict[str, Any]) -> dict[str, Any]:
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
        "account_type": nested(tx, "account_state_before", "account_status") or tx.get("orig_status"),
        "bounce": as_bool(in_msg.get("bounce")) if in_msg else None,
        "destroyed": as_bool(desc.get("destroyed")),
        "balance_change": balance_change,
        "transaction_value": in_msg_value + out_msg_value_sum,
        "in_msg_value": in_msg_value,
        "out_msg_value_sum": out_msg_value_sum,
    }


def fetch_transactions(
    session: requests.Session,
    base_url: str,
    api_key: str | None,
    params: dict[str, Any],
    max_retries: int = 5,
) -> list[dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["X-API-Key"] = api_key
    url = f"{base_url.rstrip('/')}/transactions"
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=60)
        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(min(2**attempt, 30) * random.uniform(0.9, 1.1))
            continue

        if response.status_code == 200:
            try:
                return response.json().get("transactions", [])
            except ValueError as exc:
                last_error = str(exc)
                time.sleep(min(2**attempt, 30) * random.uniform(0.9, 1.1))
                continue

        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 60)
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            time.sleep(wait * random.uniform(0.9, 1.1))
            continue

        raise RuntimeError(f"TON Center request failed with HTTP {response.status_code}: {response.text[:500]}")

    raise RuntimeError(f"TON Center request failed after retries: {last_error}")


def iter_windows(start_dt: datetime, end_dt: datetime, window_hours: int):
    current = start_dt
    delta = timedelta(hours=window_hours)
    while current < end_dt:
        window_end = min(current + delta, end_dt)
        yield current, window_end
        current = window_end


def write_raw_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in RAW_COLUMNS})


"""Shared helpers for TON fee data collection, feature engineering, and models."""

from __future__ import annotations

import csv
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

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

HOURLY_COLUMNS = [
    "hour",
    "tx_count",
    "unique_accounts",
    "avg_total_fee",
    "median_total_fee",
    "p90_total_fee",
    "min_total_fee",
    "max_total_fee",
    "std_total_fee",
    "avg_gas_used",
    "median_gas_used",
    "avg_compute_fee",
    "avg_storage_fee",
    "avg_action_fee",
    "avg_forward_fee",
    "avg_import_fee",
    "avg_vm_steps",
    "avg_msgs_created",
    "avg_out_msg_count",
    "avg_msg_size_bits",
    "avg_msg_size_cells",
    "failed_tx_ratio",
    "compute_success_ratio",
    "action_success_ratio",
    "avg_transaction_value",
    "total_transaction_value",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "fee_lag_1h",
    "fee_lag_3h",
    "fee_lag_6h",
    "fee_lag_12h",
    "fee_lag_24h",
    "rolling_avg_fee_3h",
    "rolling_avg_fee_6h",
    "rolling_avg_fee_12h",
    "rolling_avg_fee_24h",
    "rolling_std_fee_6h",
    "rolling_std_fee_24h",
    "fee_change_1h",
    "fee_change_3h",
    "fee_change_6h",
    "fee_change_12h",
    "fee_change_24h",
    "tx_count_change_1h",
    "tx_count_change_3h",
    "tx_count_change_6h",
    "tx_count_change_24h",
    "gas_used_change_1h",
    "gas_used_change_3h",
    "gas_used_change_6h",
    "gas_used_change_24h",
    "p90_fee_change_1h",
    "p90_fee_change_3h",
    "p90_fee_change_6h",
    "p90_fee_change_24h",
    "same_hour_prev_day_fee",
    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
    "target_next_hour_avg_fee",
]

MODEL_FEATURE_COLUMNS = [
    "tx_count",
    "unique_accounts",
    "avg_total_fee",
    "median_total_fee",
    "p90_total_fee",
    "min_total_fee",
    "max_total_fee",
    "std_total_fee",
    "avg_gas_used",
    "median_gas_used",
    "avg_compute_fee",
    "avg_storage_fee",
    "avg_action_fee",
    "avg_forward_fee",
    "avg_import_fee",
    "avg_vm_steps",
    "avg_msgs_created",
    "avg_out_msg_count",
    "avg_msg_size_bits",
    "avg_msg_size_cells",
    "failed_tx_ratio",
    "compute_success_ratio",
    "action_success_ratio",
    "avg_transaction_value",
    "total_transaction_value",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "fee_lag_1h",
    "fee_lag_3h",
    "fee_lag_6h",
    "fee_lag_12h",
    "fee_lag_24h",
    "rolling_avg_fee_3h",
    "rolling_avg_fee_6h",
    "rolling_avg_fee_12h",
    "rolling_avg_fee_24h",
    "rolling_std_fee_6h",
    "rolling_std_fee_24h",
    "fee_change_1h",
    "fee_change_3h",
    "fee_change_6h",
    "fee_change_12h",
    "fee_change_24h",
    "tx_count_change_1h",
    "tx_count_change_3h",
    "tx_count_change_6h",
    "tx_count_change_24h",
    "gas_used_change_1h",
    "gas_used_change_3h",
    "gas_used_change_6h",
    "gas_used_change_24h",
    "p90_fee_change_1h",
    "p90_fee_change_3h",
    "p90_fee_change_6h",
    "p90_fee_change_24h",
    "same_hour_prev_day_fee",
    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
]

NUMERIC_COLUMNS = [
    "now",
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
    "balance_change",
    "transaction_value",
    "in_msg_value",
    "out_msg_value_sum",
]

BOOL_COLUMNS = ["aborted", "compute_success", "action_success", "bounce", "destroyed"]

ZERO_FILL_COLUMNS = [
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
    "transaction_value",
    "in_msg_value",
    "out_msg_value_sum",
]

RAW_DICTIONARY = {
    "hash": "Transaction hash from TON Center v3.",
    "now": "Transaction generation Unix timestamp in UTC seconds.",
    "account": "Account address associated with the transaction.",
    "lt": "Logical time of the transaction.",
    "mc_block_seqno": "Masterchain block sequence number.",
    "total_fees": "Total transaction fees in nanoton.",
    "compute_gas_used": "Compute phase gas units used.",
    "compute_gas_fees": "Compute phase gas fees in nanoton.",
    "storage_fees_collected": "Storage phase fees collected in nanoton.",
    "storage_fees_due": "Storage phase fees due in nanoton.",
    "total_action_fees": "Action phase total action fees in nanoton.",
    "total_fwd_fees": "Action phase total forward fees in nanoton.",
    "in_msg_import_fee": "Inbound message import fee in nanoton.",
    "in_msg_fwd_fee": "Inbound message forward fee in nanoton.",
    "out_msg_fwd_fee_sum": "Sum of outbound message forward fees in nanoton.",
    "out_msg_count": "Number of outbound messages emitted by the transaction.",
    "vm_steps": "TON VM steps executed in the compute phase.",
    "msgs_created": "Number of messages created by the action phase.",
    "tot_actions": "Total number of action phase actions.",
    "msg_size_bits": "Total action message size in bits.",
    "msg_size_cells": "Total action message size in cells.",
    "aborted": "True when the transaction description marks the transaction aborted.",
    "compute_success": "True when the compute phase succeeded; blank if no compute phase was present.",
    "action_success": "True when the action phase succeeded; blank if no action phase was present.",
    "transaction_type": "TON transaction description type.",
    "account_type": "Account status before the transaction when available.",
    "bounce": "Inbound message bounce flag when an inbound message exists.",
    "destroyed": "True when the transaction destroyed the account.",
    "balance_change": "Account balance after minus before in nanoton.",
    "transaction_value": "Inbound plus outbound message value throughput in nanoton.",
    "in_msg_value": "Inbound message value in nanoton.",
    "out_msg_value_sum": "Sum of outbound message values in nanoton.",
}

HOURLY_DICTIONARY = {
    "hour": "UTC hour bucket start timestamp.",
    "tx_count": "Number of raw transactions in the hourly bucket.",
    "unique_accounts": "Number of unique account addresses in the hourly bucket.",
    "avg_total_fee": "Mean total_fees per transaction in nanoton.",
    "median_total_fee": "Median total_fees per transaction in nanoton.",
    "p90_total_fee": "90th percentile total_fees per transaction in nanoton.",
    "min_total_fee": "Minimum total_fees in nanoton.",
    "max_total_fee": "Maximum total_fees in nanoton.",
    "std_total_fee": "Sample standard deviation of total_fees in nanoton.",
    "avg_gas_used": "Mean compute_gas_used.",
    "median_gas_used": "Median compute_gas_used.",
    "avg_compute_fee": "Mean compute_gas_fees in nanoton.",
    "avg_storage_fee": "Mean storage_fees_collected in nanoton.",
    "avg_action_fee": "Mean total_action_fees in nanoton.",
    "avg_forward_fee": "Mean of total_fwd_fees plus outbound forward fee sum in nanoton.",
    "avg_import_fee": "Mean inbound import fee in nanoton.",
    "avg_vm_steps": "Mean VM steps.",
    "avg_msgs_created": "Mean messages created.",
    "avg_out_msg_count": "Mean outbound message count.",
    "avg_msg_size_bits": "Mean total action message size in bits.",
    "avg_msg_size_cells": "Mean total action message size in cells.",
    "failed_tx_ratio": "Mean aborted flag per hour.",
    "compute_success_ratio": "Mean compute_success flag per hour, skipping missing phases.",
    "action_success_ratio": "Mean action_success flag per hour, skipping missing phases.",
    "avg_transaction_value": "Mean transaction_value in nanoton.",
    "total_transaction_value": "Sum transaction_value in nanoton.",
    "hour_of_day": "UTC hour number, 0-23.",
    "day_of_week": "UTC day of week, Monday=0.",
    "is_weekend": "1 for Saturday/Sunday UTC, otherwise 0.",
    "fee_lag_1h": "avg_total_fee shifted back 1 hourly row.",
    "fee_lag_3h": "avg_total_fee shifted back 3 hourly rows.",
    "fee_lag_6h": "avg_total_fee shifted back 6 hourly rows.",
    "fee_lag_12h": "avg_total_fee shifted back 12 hourly rows.",
    "fee_lag_24h": "avg_total_fee shifted back 24 hourly rows.",
    "rolling_avg_fee_3h": "Prior 3-hour rolling mean of avg_total_fee.",
    "rolling_avg_fee_6h": "Prior 6-hour rolling mean of avg_total_fee.",
    "rolling_avg_fee_12h": "Prior 12-hour rolling mean of avg_total_fee.",
    "rolling_avg_fee_24h": "Prior 24-hour rolling mean of avg_total_fee.",
    "rolling_std_fee_6h": "Prior 6-hour rolling standard deviation of avg_total_fee.",
    "rolling_std_fee_24h": "Prior 24-hour rolling standard deviation of avg_total_fee.",
    "fee_change_1h": "Current avg_total_fee minus avg_total_fee from 1 hourly row earlier.",
    "fee_change_3h": "Current avg_total_fee minus avg_total_fee from 3 hourly rows earlier.",
    "fee_change_6h": "Current avg_total_fee minus avg_total_fee from 6 hourly rows earlier.",
    "fee_change_12h": "Current avg_total_fee minus avg_total_fee from 12 hourly rows earlier.",
    "fee_change_24h": "Current avg_total_fee minus avg_total_fee from 24 hourly rows earlier.",
    "tx_count_change_1h": "Current tx_count minus tx_count from 1 hourly row earlier.",
    "tx_count_change_3h": "Current tx_count minus tx_count from 3 hourly rows earlier.",
    "tx_count_change_6h": "Current tx_count minus tx_count from 6 hourly rows earlier.",
    "tx_count_change_24h": "Current tx_count minus tx_count from 24 hourly rows earlier.",
    "gas_used_change_1h": "Current avg_gas_used minus avg_gas_used from 1 hourly row earlier.",
    "gas_used_change_3h": "Current avg_gas_used minus avg_gas_used from 3 hourly rows earlier.",
    "gas_used_change_6h": "Current avg_gas_used minus avg_gas_used from 6 hourly rows earlier.",
    "gas_used_change_24h": "Current avg_gas_used minus avg_gas_used from 24 hourly rows earlier.",
    "p90_fee_change_1h": "Current p90_total_fee minus p90_total_fee from 1 hourly row earlier.",
    "p90_fee_change_3h": "Current p90_total_fee minus p90_total_fee from 3 hourly rows earlier.",
    "p90_fee_change_6h": "Current p90_total_fee minus p90_total_fee from 6 hourly rows earlier.",
    "p90_fee_change_24h": "Current p90_total_fee minus p90_total_fee from 24 hourly rows earlier.",
    "same_hour_prev_day_fee": "avg_total_fee from the same UTC hour on the previous day.",
    "hour_sin": "Sine encoding of UTC hour of day.",
    "hour_cos": "Cosine encoding of UTC hour of day.",
    "day_sin": "Sine encoding of UTC day of week.",
    "day_cos": "Cosine encoding of UTC day of week.",
    "target_next_hour_avg_fee": "Next hourly row's avg_total_fee in nanoton.",
}


def resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


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
        return int(value)
    except (TypeError, ValueError):
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
    headers = {"X-API-Key": api_key} if api_key else {}
    url = f"{base_url.rstrip('/')}/transactions"
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=60)
        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(min(2**attempt, 30))
            continue

        if response.status_code == 200:
            return response.json().get("transactions", [])

        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 60)
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            time.sleep(wait)
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


def normalize_bool(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.lower().str.strip()
    mapped = normalized.map({"true": 1.0, "false": 0.0, "1": 1.0, "0": 0.0})
    return mapped.astype("Float64")


def read_raw_transactions(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [column for column in RAW_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"raw CSV is missing required columns: {missing}")

    df = df[RAW_COLUMNS].copy()
    df = df.drop_duplicates(subset=["hash", "lt"], keep="first")

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in BOOL_COLUMNS:
        df[column] = normalize_bool(df[column])

    df[ZERO_FILL_COLUMNS] = df[ZERO_FILL_COLUMNS].fillna(0)
    df = df.dropna(subset=["now"])
    df["timestamp"] = pd.to_datetime(df["now"], unit="s", utc=True)
    df["hour"] = df["timestamp"].dt.floor("h")
    return df


def build_hourly_features(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df["forward_fee_total"] = df["total_fwd_fees"] + df["out_msg_fwd_fee_sum"]

    grouped = df.groupby("hour", sort=True)
    hourly = grouped.agg(
        tx_count=("hash", "count"),
        unique_accounts=("account", "nunique"),
        avg_total_fee=("total_fees", "mean"),
        median_total_fee=("total_fees", "median"),
        p90_total_fee=("total_fees", lambda series: series.quantile(0.90)),
        min_total_fee=("total_fees", "min"),
        max_total_fee=("total_fees", "max"),
        std_total_fee=("total_fees", "std"),
        avg_gas_used=("compute_gas_used", "mean"),
        median_gas_used=("compute_gas_used", "median"),
        avg_compute_fee=("compute_gas_fees", "mean"),
        avg_storage_fee=("storage_fees_collected", "mean"),
        avg_action_fee=("total_action_fees", "mean"),
        avg_forward_fee=("forward_fee_total", "mean"),
        avg_import_fee=("in_msg_import_fee", "mean"),
        avg_vm_steps=("vm_steps", "mean"),
        avg_msgs_created=("msgs_created", "mean"),
        avg_out_msg_count=("out_msg_count", "mean"),
        avg_msg_size_bits=("msg_size_bits", "mean"),
        avg_msg_size_cells=("msg_size_cells", "mean"),
        failed_tx_ratio=("aborted", "mean"),
        compute_success_ratio=("compute_success", "mean"),
        action_success_ratio=("action_success", "mean"),
        avg_transaction_value=("transaction_value", "mean"),
        total_transaction_value=("transaction_value", "sum"),
    ).reset_index()

    return recompute_hourly_derived_features(hourly)


def recompute_hourly_derived_features(hourly_df: pd.DataFrame) -> pd.DataFrame:
    """Recompute lag, rolling, calendar, and target columns for hourly rows.

    This is used after merging freshly collected recent hourly aggregates into
    the committed lightweight history, where raw transaction history is not
    available in CI.
    """
    hourly = hourly_df.copy()
    if "hour" not in hourly.columns:
        raise ValueError("hourly feature dataset must include an hour column")

    hourly["hour"] = pd.to_datetime(hourly["hour"], utc=True)
    hourly = hourly.drop_duplicates(subset=["hour"], keep="last")
    hourly = hourly.sort_values("hour").reset_index(drop=True)

    hourly["hour_of_day"] = hourly["hour"].dt.hour
    hourly["day_of_week"] = hourly["hour"].dt.dayofweek
    hourly["is_weekend"] = hourly["day_of_week"].isin([5, 6]).astype(int)

    for lag in [1, 3, 6, 12, 24]:
        hourly[f"fee_lag_{lag}h"] = hourly["avg_total_fee"].shift(lag)

    shifted_fee = hourly["avg_total_fee"].shift(1)
    for window in [3, 6, 12, 24]:
        hourly[f"rolling_avg_fee_{window}h"] = shifted_fee.rolling(window=window, min_periods=1).mean()
    for window in [6, 24]:
        hourly[f"rolling_std_fee_{window}h"] = shifted_fee.rolling(window=window, min_periods=2).std()

    # Change features use current-hour observed values minus prior observed
    # values. These are safe for next-hour prediction because they never look
    # beyond the current feature hour.
    for lag in [1, 3, 6, 12, 24]:
        hourly[f"fee_change_{lag}h"] = hourly["avg_total_fee"] - hourly["avg_total_fee"].shift(lag)
    for lag in [1, 3, 6, 24]:
        hourly[f"tx_count_change_{lag}h"] = hourly["tx_count"] - hourly["tx_count"].shift(lag)
        hourly[f"gas_used_change_{lag}h"] = hourly["avg_gas_used"] - hourly["avg_gas_used"].shift(lag)
        hourly[f"p90_fee_change_{lag}h"] = hourly["p90_total_fee"] - hourly["p90_total_fee"].shift(lag)

    hourly["same_hour_prev_day_fee"] = hourly["avg_total_fee"].shift(24)
    hourly["hour_sin"] = np.sin(2 * np.pi * hourly["hour_of_day"] / 24)
    hourly["hour_cos"] = np.cos(2 * np.pi * hourly["hour_of_day"] / 24)
    hourly["day_sin"] = np.sin(2 * np.pi * hourly["day_of_week"] / 7)
    hourly["day_cos"] = np.cos(2 * np.pi * hourly["day_of_week"] / 7)

    hourly["target_next_hour_avg_fee"] = hourly["avg_total_fee"].shift(-1)
    if "std_total_fee" in hourly.columns:
        hourly["std_total_fee"] = hourly["std_total_fee"].fillna(0)

    for column in HOURLY_COLUMNS:
        if column not in hourly.columns:
            hourly[column] = np.nan

    hourly["hour"] = hourly["hour"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return hourly[HOURLY_COLUMNS]


def write_data_dictionary(path: Path) -> None:
    lines = [
        "# Data Dictionary",
        "",
        "All fee and value fields are stored in nanoton unless noted otherwise.",
        "",
        "## raw_transactions.csv",
        "",
    ]
    for column in RAW_COLUMNS:
        lines.append(f"- `{column}`: {RAW_DICTIONARY[column]}")

    lines.extend(["", "## hourly_features.csv", ""])
    for column in HOURLY_COLUMNS:
        lines.append(f"- `{column}`: {HOURLY_DICTIONARY[column]}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(
    raw_df: pd.DataFrame,
    hourly_df: pd.DataFrame,
    raw_path: Path,
    hourly_path: Path,
    summary_path: Path,
    metadata_path: Path | None,
) -> None:
    missing_counts = raw_df[RAW_COLUMNS].isna().sum().sort_values(ascending=False)
    fee_stats = raw_df["total_fees"].describe(percentiles=[0.5, 0.9, 0.95, 0.99])
    metadata = {}
    if metadata_path and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    first_ts = raw_df["timestamp"].min()
    last_ts = raw_df["timestamp"].max()
    non_null_targets = hourly_df["target_next_hour_avg_fee"].notna().sum()

    lines = [
        "# TON Transaction Fee Dataset Summary",
        "",
        "## API Endpoint",
        "",
        "- TON Center API v3 `GET /transactions`",
        "- Base URL: `https://toncenter.com/api/v3`",
        "- Authentication: optional `X-API-Key` header via `TONCENTER_API_KEY`.",
        "",
        "## Collection Coverage",
        "",
        f"- Raw CSV: `{raw_path.name}`",
        f"- Hourly CSV: `{hourly_path.name}`",
        f"- Transactions after de-duplication: {len(raw_df):,}",
        f"- Date range UTC: {first_ts.isoformat() if pd.notna(first_ts) else 'n/a'} to {last_ts.isoformat() if pd.notna(last_ts) else 'n/a'}",
        f"- Hourly rows: {len(hourly_df):,}",
        f"- Hourly rows with next-hour target: {non_null_targets:,}",
        "",
        "## Collection Metadata",
        "",
    ]

    if metadata:
        for key in [
            "endpoint",
            "start_utc",
            "end_utc",
            "window_hours",
            "limit",
            "max_pages_per_window",
            "sort",
            "workchain",
            "request_count",
            "windows_processed",
            "windows_with_limit_hits",
            "api_key_used",
            "new_rows_added",
            "status",
        ]:
            if key in metadata:
                lines.append(f"- {key}: {metadata.get(key)}")
        if metadata.get("windows_with_limit_hits", 0):
            lines.append(
                "- Limitation: at least one hourly window reached the request limit, "
                "so this run is a sampled transaction-level dataset rather than a "
                "complete chain-wide export for every hour."
            )
    else:
        lines.append("- No collection metadata JSON was found.")

    lines.extend(
        [
            "",
            "## Fee Statistics",
            "",
            fee_stats.to_string(),
            "",
            "## Missing Value Counts",
            "",
            missing_counts.to_string(),
            "",
            "## Modeling Notes",
            "",
            "- The target column is `target_next_hour_avg_fee`.",
            "- Lag and rolling features are shifted so they only use prior-hour fee information.",
            "- UTC is used for primary time features. Convert `hour` to Asia/Seoul for KST dashboards when needed.",
            "- If collection hit API page limits, treat `tx_count` and `unique_accounts` as sample counts, not total network counts.",
        ]
    )

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_model_matrix(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    x = df[feature_columns].copy()
    for column in feature_columns:
        x[column] = pd.to_numeric(x[column], errors="coerce")
    return x


def split_model_data(
    hourly_df: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    test_fraction: float,
) -> dict[str, Any]:
    data = hourly_df.copy()
    if "hour" not in data.columns:
        raise ValueError("hourly feature dataset must include an hour column")
    data[target_column] = pd.to_numeric(data[target_column], errors="coerce")
    x = prepare_model_matrix(data, feature_columns)
    usable = x.notna().any(axis=1) & data[target_column].notna()
    x = x.loc[usable].reset_index(drop=True)
    y = data.loc[usable, target_column].astype(float).reset_index(drop=True)
    hours = data.loc[usable, "hour"].reset_index(drop=True)

    if len(x) < 10:
        raise ValueError("Need at least 10 hourly rows with targets to train the model.")

    split_index = max(1, int(len(x) * (1 - test_fraction)))
    if split_index >= len(x):
        split_index = len(x) - 1

    x_train = x.iloc[:split_index].copy()
    y_train = y.iloc[:split_index].to_numpy(dtype=float)
    x_test = x.iloc[split_index:].copy()
    y_test = y.iloc[split_index:].to_numpy(dtype=float)
    test_hours = hours.iloc[split_index:].reset_index(drop=True)

    impute_values = x_train.median(numeric_only=True).fillna(0)
    x_train = x_train.fillna(impute_values)
    x_test = x_test.fillna(impute_values)

    means = x_train.mean()
    stds = x_train.std(ddof=0).replace(0, 1).fillna(1)
    x_train_scaled = (x_train - means) / stds
    x_test_scaled = (x_test - means) / stds

    return {
        "x_train_scaled": x_train_scaled,
        "x_test_scaled": x_test_scaled,
        "y_train": y_train,
        "y_test": y_test,
        "test_hours": test_hours,
        "impute_values": impute_values,
        "means": means,
        "stds": stds,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
    }


def build_model_candidates() -> list[dict[str, Any]]:
    return [
        {
            "model_name": "linear_regression",
            "model_type": "ordinary_least_squares_linear_regression",
            "alpha": 0.0,
            "target_transform": "none",
        },
        {
            "model_name": "linear_regression_log1p_target",
            "model_type": "ordinary_least_squares_linear_regression",
            "alpha": 0.0,
            "target_transform": "log1p",
        },
        {
            "model_name": "ridge_alpha_1",
            "model_type": "ridge_regression",
            "alpha": 1.0,
            "target_transform": "none",
        },
        {
            "model_name": "ridge_alpha_10",
            "model_type": "ridge_regression",
            "alpha": 10.0,
            "target_transform": "none",
        },
        {
            "model_name": "ridge_alpha_100",
            "model_type": "ridge_regression",
            "alpha": 100.0,
            "target_transform": "none",
        },
        {
            "model_name": "ridge_alpha_1_log1p_target",
            "model_type": "ridge_regression",
            "alpha": 1.0,
            "target_transform": "log1p",
        },
        {
            "model_name": "ridge_alpha_10_log1p_target",
            "model_type": "ridge_regression",
            "alpha": 10.0,
            "target_transform": "log1p",
        },
        {
            "model_name": "ridge_alpha_100_log1p_target",
            "model_type": "ridge_regression",
            "alpha": 100.0,
            "target_transform": "log1p",
        },
        {
            "model_name": "gradient_boosted_stumps_50_lr_0_05",
            "model_type": "gradient_boosted_regression_trees",
            "max_depth": 1,
            "n_estimators": 50,
            "learning_rate": 0.05,
            "min_samples_leaf": 20,
            "target_transform": "none",
        },
        {
            "model_name": "gradient_boosted_stumps_100_lr_0_05",
            "model_type": "gradient_boosted_regression_trees",
            "max_depth": 1,
            "n_estimators": 100,
            "learning_rate": 0.05,
            "min_samples_leaf": 20,
            "target_transform": "none",
        },
        {
            "model_name": "gradient_boosted_stumps_200_lr_0_03",
            "model_type": "gradient_boosted_regression_trees",
            "max_depth": 1,
            "n_estimators": 200,
            "learning_rate": 0.03,
            "min_samples_leaf": 20,
            "target_transform": "none",
        },
        {
            "model_name": "gradient_boosted_trees_depth_3_50_lr_0_1",
            "model_type": "gradient_boosted_regression_trees",
            "max_depth": 3,
            "n_estimators": 50,
            "learning_rate": 0.1,
            "min_samples_leaf": 20,
            "target_transform": "none",
        },
    ]


def fit_model_candidate(
    candidate: dict[str, Any],
    split: dict[str, Any],
    feature_columns: list[str],
    target_column: str,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float], pd.DataFrame]:
    if candidate["model_type"] == "gradient_boosted_regression_trees":
        return fit_gradient_boosted_tree_model(
            split=split,
            feature_columns=feature_columns,
            target_column=target_column,
            model_name=str(candidate["model_name"]),
            max_depth=int(candidate["max_depth"]),
            n_estimators=int(candidate["n_estimators"]),
            learning_rate=float(candidate["learning_rate"]),
            min_samples_leaf=int(candidate["min_samples_leaf"]),
            target_transform=str(candidate["target_transform"]),
        )

    return fit_regression_model(
        split=split,
        feature_columns=feature_columns,
        target_column=target_column,
        **candidate,
    )


def regression_coefficients(
    x_scaled: pd.DataFrame,
    y: np.ndarray,
    alpha: float = 0.0,
) -> np.ndarray:
    train_design = np.column_stack([np.ones(len(x_scaled)), x_scaled.to_numpy(dtype=float)])
    if alpha <= 0:
        beta, *_ = np.linalg.lstsq(train_design, y, rcond=None)
        return beta.astype(float)

    penalty = np.eye(train_design.shape[1])
    penalty[0, 0] = 0.0
    lhs = train_design.T @ train_design + alpha * penalty
    rhs = train_design.T @ y
    beta, *_ = np.linalg.lstsq(lhs, rhs, rcond=None)
    return beta.astype(float)


def compute_metrics(y_true: np.ndarray, predictions: np.ndarray) -> dict[str, float]:
    residuals = y_true - predictions
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals**2)))
    total_var = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1 - np.sum(residuals**2) / total_var) if total_var else 0.0
    nonzero = y_true != 0
    mape = (
        float(np.mean(np.abs(residuals[nonzero] / y_true[nonzero])) * 100)
        if np.any(nonzero)
        else float("nan")
    )
    return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}


def predict_design(
    beta: np.ndarray,
    x_scaled: pd.DataFrame,
    target_transform: str,
) -> np.ndarray:
    design = np.column_stack([np.ones(len(x_scaled)), x_scaled.to_numpy(dtype=float)])
    raw_predictions = design @ beta
    if target_transform == "log1p":
        raw_predictions = np.expm1(raw_predictions)
    return np.maximum(0.0, raw_predictions.astype(float))


def _tree_predict_one(tree: dict[str, Any], row: np.ndarray) -> float:
    node = tree
    while node.get("feature_index") is not None:
        feature_index = int(node["feature_index"])
        threshold = float(node["threshold"])
        node = node["left"] if row[feature_index] <= threshold else node["right"]
    return float(node["value"])


def predict_tree_ensemble(model: dict[str, Any], x_scaled: pd.DataFrame) -> np.ndarray:
    x_values = x_scaled.to_numpy(dtype=float)
    predictions = np.full(
        len(x_values),
        float(model["initial_prediction"]),
        dtype=float,
    )
    learning_rate = float(model["learning_rate"])
    for tree in model["trees"]:
        predictions += learning_rate * np.array([_tree_predict_one(tree, row) for row in x_values])
    if model.get("target_transform") == "log1p":
        predictions = np.expm1(predictions)
    return np.maximum(0.0, predictions.astype(float))


def _build_regression_tree(
    x_values: np.ndarray,
    y_values: np.ndarray,
    row_indices: np.ndarray,
    depth: int,
    max_depth: int,
    min_samples_leaf: int,
    feature_importance: np.ndarray,
) -> dict[str, Any]:
    node_values = y_values[row_indices]
    node_prediction = float(np.mean(node_values))
    node_sse = float(np.sum((node_values - node_prediction) ** 2))

    if (
        depth >= max_depth
        or len(row_indices) < 2 * min_samples_leaf
        or node_sse <= 1e-12
    ):
        return {"value": node_prediction, "feature_index": None}

    best_split: tuple[float, int, float, np.ndarray, np.ndarray] | None = None
    feature_count = x_values.shape[1]
    quantiles = np.linspace(0.1, 0.9, 9)

    for feature_index in range(feature_count):
        feature_values = x_values[row_indices, feature_index]
        thresholds = np.unique(np.quantile(feature_values, quantiles))
        for threshold in thresholds:
            left_mask = feature_values <= threshold
            left_count = int(left_mask.sum())
            right_count = len(row_indices) - left_count
            if left_count < min_samples_leaf or right_count < min_samples_leaf:
                continue

            left_indices = row_indices[left_mask]
            right_indices = row_indices[~left_mask]
            left_values = y_values[left_indices]
            right_values = y_values[right_indices]
            left_sse = float(np.sum((left_values - np.mean(left_values)) ** 2))
            right_sse = float(np.sum((right_values - np.mean(right_values)) ** 2))
            split_sse = left_sse + right_sse
            if best_split is None or split_sse < best_split[0]:
                best_split = (
                    split_sse,
                    feature_index,
                    float(threshold),
                    left_indices,
                    right_indices,
                )

    if best_split is None or best_split[0] >= node_sse:
        return {"value": node_prediction, "feature_index": None}

    split_sse, feature_index, threshold, left_indices, right_indices = best_split
    feature_importance[feature_index] += max(0.0, node_sse - split_sse)
    return {
        "value": node_prediction,
        "feature_index": int(feature_index),
        "threshold": float(threshold),
        "left": _build_regression_tree(
            x_values,
            y_values,
            left_indices,
            depth + 1,
            max_depth,
            min_samples_leaf,
            feature_importance,
        ),
        "right": _build_regression_tree(
            x_values,
            y_values,
            right_indices,
            depth + 1,
            max_depth,
            min_samples_leaf,
            feature_importance,
        ),
    }


def fit_gradient_boosted_tree_model(
    split: dict[str, Any],
    feature_columns: list[str],
    model_name: str,
    max_depth: int,
    n_estimators: int,
    learning_rate: float,
    min_samples_leaf: int = 20,
    target_transform: str = "none",
    target_column: str = "target_next_hour_avg_fee",
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float], pd.DataFrame]:
    if target_transform == "log1p":
        train_target = np.log1p(split["y_train"])
    elif target_transform == "none":
        train_target = split["y_train"]
    else:
        raise ValueError(f"Unsupported target transform: {target_transform}")

    x_train_values = split["x_train_scaled"].to_numpy(dtype=float)
    initial_prediction = float(np.mean(train_target))
    train_predictions = np.full(len(train_target), initial_prediction, dtype=float)
    trees: list[dict[str, Any]] = []
    feature_importance_values = np.zeros(len(feature_columns), dtype=float)

    for _ in range(n_estimators):
        residuals = train_target - train_predictions
        tree = _build_regression_tree(
            x_values=x_train_values,
            y_values=residuals,
            row_indices=np.arange(len(residuals)),
            depth=0,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            feature_importance=feature_importance_values,
        )
        tree_train_predictions = np.array([_tree_predict_one(tree, row) for row in x_train_values])
        train_predictions += learning_rate * tree_train_predictions
        trees.append(tree)

    model = {
        "model_name": model_name,
        "model_type": "gradient_boosted_regression_trees",
        "target_column": target_column,
        "target_transform": target_transform,
        "feature_columns": feature_columns,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "initial_prediction": initial_prediction,
        "learning_rate": float(learning_rate),
        "n_estimators": int(n_estimators),
        "max_depth": int(max_depth),
        "min_samples_leaf": int(min_samples_leaf),
        "trees": trees,
        "impute_values": {column: float(split["impute_values"][column]) for column in feature_columns},
        "feature_means": {column: float(split["means"][column]) for column in feature_columns},
        "feature_stds": {column: float(split["stds"][column]) for column in feature_columns},
    }

    predictions = predict_tree_ensemble(model, split["x_test_scaled"])
    metrics = compute_metrics(split["y_test"], predictions)
    metrics.update(
        {
            "model_name": model_name,
            "model_type": "gradient_boosted_regression_trees",
            "target_transform": target_transform,
            "alpha": 0.0,
            "max_depth": int(max_depth),
            "n_estimators": int(n_estimators),
            "learning_rate": float(learning_rate),
            "min_samples_leaf": int(min_samples_leaf),
            "train_rows": split["train_rows"],
            "test_rows": split["test_rows"],
        }
    )
    model["metrics"] = metrics

    residuals = split["y_test"] - predictions
    actual_vs_predicted = pd.DataFrame(
        {
            "hour": split["test_hours"],
            "actual_next_hour_avg_fee": split["y_test"],
            "predicted_next_hour_avg_fee": predictions,
            "error": residuals,
            "absolute_error": np.abs(residuals),
            "model_name": model_name,
        }
    )

    total_importance = float(feature_importance_values.sum())
    normalized_importance = (
        feature_importance_values / total_importance
        if total_importance > 0
        else feature_importance_values
    )
    importance_table = pd.DataFrame(
        {
            "model_name": model_name,
            "feature": feature_columns,
            "coefficient_scaled": np.nan,
            "abs_coefficient_scaled": normalized_importance,
            "tree_importance": normalized_importance,
        }
    ).sort_values("abs_coefficient_scaled", ascending=False)

    return model, importance_table, metrics, actual_vs_predicted


def fit_regression_model(
    split: dict[str, Any],
    feature_columns: list[str],
    model_name: str,
    model_type: str,
    alpha: float = 0.0,
    target_transform: str = "none",
    target_column: str = "target_next_hour_avg_fee",
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float], pd.DataFrame]:
    y_train = split["y_train"]
    if target_transform == "log1p":
        train_target = np.log1p(y_train)
    elif target_transform == "none":
        train_target = y_train
    else:
        raise ValueError(f"Unsupported target transform: {target_transform}")

    beta = regression_coefficients(split["x_train_scaled"], train_target, alpha=alpha)
    intercept = float(beta[0])
    coefficients = beta[1:].astype(float)

    predictions = predict_design(beta, split["x_test_scaled"], target_transform)
    metrics = compute_metrics(split["y_test"], predictions)
    metrics.update(
        {
            "model_name": model_name,
            "model_type": model_type,
            "target_transform": target_transform,
            "alpha": float(alpha),
            "train_rows": split["train_rows"],
            "test_rows": split["test_rows"],
        }
    )

    residuals = split["y_test"] - predictions
    actual_vs_predicted = pd.DataFrame(
        {
            "hour": split["test_hours"],
            "actual_next_hour_avg_fee": split["y_test"],
            "predicted_next_hour_avg_fee": predictions,
            "error": residuals,
            "absolute_error": np.abs(residuals),
            "model_name": model_name,
        }
    )

    model = {
        "model_name": model_name,
        "model_type": model_type,
        "target_column": target_column,
        "target_transform": target_transform,
        "alpha": float(alpha),
        "feature_columns": feature_columns,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "intercept": intercept,
        "coefficients_scaled": dict(zip(feature_columns, coefficients.tolist(), strict=True)),
        "impute_values": {column: float(split["impute_values"][column]) for column in feature_columns},
        "feature_means": {column: float(split["means"][column]) for column in feature_columns},
        "feature_stds": {column: float(split["stds"][column]) for column in feature_columns},
        "metrics": metrics,
    }

    coefficient_table = pd.DataFrame(
        {
            "model_name": model_name,
            "feature": feature_columns,
            "coefficient_scaled": coefficients,
            "abs_coefficient_scaled": np.abs(coefficients),
        }
    ).sort_values("abs_coefficient_scaled", ascending=False)

    return model, coefficient_table, metrics, actual_vs_predicted


def train_model_suite(
    hourly_df: pd.DataFrame,
    feature_columns: list[str] = MODEL_FEATURE_COLUMNS,
    target_column: str = "target_next_hour_avg_fee",
    test_fraction: float = 0.2,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    split = split_model_data(hourly_df, feature_columns, target_column, test_fraction)
    candidates = build_model_candidates()

    trained: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    coefficient_tables: list[pd.DataFrame] = []
    prediction_tables: list[pd.DataFrame] = []

    for candidate in candidates:
        model, coefficients, metrics, actual_vs_predicted = fit_model_candidate(
            candidate,
            split,
            feature_columns,
            target_column,
        )
        trained.append(model)
        comparison_rows.append(metrics)
        coefficient_tables.append(coefficients)
        prediction_tables.append(actual_vs_predicted)

    comparison = pd.DataFrame(comparison_rows).sort_values(
        ["r2", "rmse", "mae"],
        ascending=[False, True, True],
    )
    best_model_name = str(comparison.iloc[0]["model_name"])
    best_model = next(model for model in trained if model["model_name"] == best_model_name)
    feature_importance = pd.concat(coefficient_tables, ignore_index=True)
    best_actual_vs_predicted = next(
        table for table in prediction_tables if str(table["model_name"].iloc[0]) == best_model_name
    )

    summary = {
        "best_model_name": best_model_name,
        "best_r2": float(comparison.iloc[0]["r2"]),
        "best_mae": float(comparison.iloc[0]["mae"]),
        "best_rmse": float(comparison.iloc[0]["rmse"]),
        "baseline_r2": float(comparison.loc[comparison["model_name"] == "linear_regression", "r2"].iloc[0]),
        "baseline_mae": float(comparison.loc[comparison["model_name"] == "linear_regression", "mae"].iloc[0]),
        "baseline_rmse": float(comparison.loc[comparison["model_name"] == "linear_regression", "rmse"].iloc[0]),
        "train_rows": int(split["train_rows"]),
        "test_rows": int(split["test_rows"]),
    }
    summary["r2_improvement"] = summary["best_r2"] - summary["baseline_r2"]
    summary["mae_improvement"] = summary["baseline_mae"] - summary["best_mae"]
    summary["rmse_improvement"] = summary["baseline_rmse"] - summary["best_rmse"]

    return best_model, comparison, feature_importance, best_actual_vs_predicted, summary


def _split_from_row_ranges(
    x: pd.DataFrame,
    y: pd.Series,
    hours: pd.Series,
    train_start: int,
    train_end: int,
    test_end: int,
) -> dict[str, Any]:
    x_train = x.iloc[train_start:train_end].copy()
    y_train = y.iloc[train_start:train_end].to_numpy(dtype=float)
    x_test = x.iloc[train_end:test_end].copy()
    y_test = y.iloc[train_end:test_end].to_numpy(dtype=float)
    test_hours = hours.iloc[train_end:test_end].reset_index(drop=True)

    impute_values = x_train.median(numeric_only=True).fillna(0)
    x_train = x_train.fillna(impute_values)
    x_test = x_test.fillna(impute_values)

    means = x_train.mean()
    stds = x_train.std(ddof=0).replace(0, 1).fillna(1)
    x_train_scaled = (x_train - means) / stds
    x_test_scaled = (x_test - means) / stds

    return {
        "x_train_scaled": x_train_scaled,
        "x_test_scaled": x_test_scaled,
        "y_train": y_train,
        "y_test": y_test,
        "test_hours": test_hours,
        "impute_values": impute_values,
        "means": means,
        "stds": stds,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
    }


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
            "fold_count": "folds",
        }
    )
    summary["r2_win_count"] = summary["model_name"].map(win_counts).fillna(0).astype(int)
    summary = summary.sort_values(
        ["mean_r2", "median_r2", "mean_rmse"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    fold_results = fold_results.merge(winners, on="fold", how="left")
    return summary, fold_results


def fit_linear_regression(
    hourly_df: pd.DataFrame,
    feature_columns: list[str] = MODEL_FEATURE_COLUMNS,
    target_column: str = "target_next_hour_avg_fee",
    test_fraction: float = 0.2,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, float]]:
    """Compatibility wrapper for the original baseline training path."""
    split = split_model_data(hourly_df, feature_columns, target_column, test_fraction)
    model, coefficients, metrics, _ = fit_regression_model(
        split=split,
        feature_columns=feature_columns,
        model_name="linear_regression",
        model_type="ordinary_least_squares_linear_regression",
        alpha=0.0,
        target_transform="none",
        target_column=target_column,
    )
    return model, coefficients, metrics


def predict_with_model(model: dict[str, Any], feature_row: dict[str, Any]) -> float:
    if model.get("model_type") == "gradient_boosted_regression_trees":
        values: dict[str, float] = {}
        for feature in model["feature_columns"]:
            raw = feature_row.get(feature)
            if raw is None or pd.isna(raw):
                raw = model["impute_values"][feature]
            values[feature] = (
                float(raw) - float(model["feature_means"][feature])
            ) / float(model["feature_stds"][feature])
        x_scaled = pd.DataFrame([values], columns=model["feature_columns"])
        return float(predict_tree_ensemble(model, x_scaled)[0])

    value = float(model["intercept"])
    for feature in model["feature_columns"]:
        raw = feature_row.get(feature)
        if raw is None or pd.isna(raw):
            raw = model["impute_values"][feature]
        scaled = (float(raw) - model["feature_means"][feature]) / model["feature_stds"][feature]
        value += float(model["coefficients_scaled"][feature]) * scaled
    if model.get("target_transform") == "log1p":
        value = float(np.expm1(value))
    return max(0.0, value)

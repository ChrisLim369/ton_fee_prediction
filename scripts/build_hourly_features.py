#!/usr/bin/env python3
"""Build hourly TON transaction fee features from raw_transactions.csv."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


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
    "target_next_hour_avg_fee",
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
    "target_next_hour_avg_fee": "Next hourly row's avg_total_fee in nanoton.",
}


def normalize_bool(series: pd.Series) -> pd.Series:
    """Convert bool-like CSV values to nullable float flags for ratios."""
    normalized = series.astype("string").str.lower().str.strip()
    mapped = normalized.map({"true": 1.0, "false": 0.0, "1": 1.0, "0": 0.0})
    return mapped.astype("Float64")


def read_raw(path: Path) -> pd.DataFrame:
    """Read the raw CSV, enforce expected columns, and prepare dtypes."""
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

    # Numeric feature inputs use zero for absent fee/count/size/value phases.
    zero_fill_columns = [
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
    df[zero_fill_columns] = df[zero_fill_columns].fillna(0)

    df = df.dropna(subset=["now"])
    df["timestamp"] = pd.to_datetime(df["now"], unit="s", utc=True)
    df["hour"] = df["timestamp"].dt.floor("h")
    return df


def build_hourly_features(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw transactions to hourly features and prediction target."""
    df = raw_df.copy()

    # Forward fees include action phase forward fees and the explicit sum of
    # outbound message forward fees requested in the raw schema.
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

    # Time-based calendar features are calculated in UTC to keep the modeling
    # table timezone-stable. Dashboard code can convert hour to KST if needed.
    hourly["hour_of_day"] = hourly["hour"].dt.hour
    hourly["day_of_week"] = hourly["hour"].dt.dayofweek
    hourly["is_weekend"] = hourly["day_of_week"].isin([5, 6]).astype(int)

    # Lag features expose previous hourly fee levels to a linear model.
    for lag in [1, 3, 6, 12, 24]:
        hourly[f"fee_lag_{lag}h"] = hourly["avg_total_fee"].shift(lag)

    # Rolling features are shifted by one hour so they only use information
    # available before the prediction hour.
    shifted_fee = hourly["avg_total_fee"].shift(1)
    for window in [3, 6, 12, 24]:
        hourly[f"rolling_avg_fee_{window}h"] = shifted_fee.rolling(window=window, min_periods=1).mean()
    for window in [6, 24]:
        hourly[f"rolling_std_fee_{window}h"] = shifted_fee.rolling(window=window, min_periods=2).std()

    # Supervised target: next hourly row's average total transaction fee.
    hourly["target_next_hour_avg_fee"] = hourly["avg_total_fee"].shift(-1)

    hourly["std_total_fee"] = hourly["std_total_fee"].fillna(0)
    hourly = hourly.sort_values("hour").reset_index(drop=True)
    hourly["hour"] = hourly["hour"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return hourly[HOURLY_COLUMNS]


def write_data_dictionary(path: Path) -> None:
    """Write concise data dictionaries for both generated CSV files."""
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

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(
    raw_df: pd.DataFrame,
    hourly_df: pd.DataFrame,
    raw_path: Path,
    hourly_path: Path,
    summary_path: Path,
    metadata_path: Path | None,
) -> None:
    """Write a compact Markdown summary of collection coverage and quality."""
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
        ]:
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

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(args: argparse.Namespace) -> None:
    raw_path = Path(args.raw)
    hourly_path = Path(args.output)
    dictionary_path = Path(args.dictionary)
    summary_path = Path(args.summary)
    metadata_path = Path(args.metadata) if args.metadata else raw_path.with_name("collection_metadata.json")

    raw_df = read_raw(raw_path)
    hourly_df = build_hourly_features(raw_df)

    hourly_path.parent.mkdir(parents=True, exist_ok=True)
    hourly_df.to_csv(hourly_path, index=False)

    dictionary_path.parent.mkdir(parents=True, exist_ok=True)
    write_data_dictionary(dictionary_path)
    write_summary(raw_df, hourly_df, raw_path, hourly_path, summary_path, metadata_path)

    print(
        json.dumps(
            {
                "raw_transactions": len(raw_df),
                "hourly_rows": len(hourly_df),
                "raw_date_min_utc": raw_df["timestamp"].min().isoformat(),
                "raw_date_max_utc": raw_df["timestamp"].max().isoformat(),
                "output": str(hourly_path),
                "dictionary": str(dictionary_path),
                "summary": str(summary_path),
            },
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default="raw_transactions.csv")
    parser.add_argument("--output", default="hourly_features.csv")
    parser.add_argument("--dictionary", default="docs/data_dictionary.md")
    parser.add_argument("--summary", default="docs/summary_report.md")
    parser.add_argument("--metadata", default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

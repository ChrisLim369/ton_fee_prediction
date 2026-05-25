"""Hourly feature engineering helpers for TON fee data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from schema import BOOL_COLUMNS as BOOL_COLUMNS
    from schema import HOURLY_COLUMNS as HOURLY_COLUMNS
    from schema import HOURLY_DICTIONARY as HOURLY_DICTIONARY
    from schema import NUMERIC_COLUMNS as NUMERIC_COLUMNS
    from schema import RAW_COLUMNS as RAW_COLUMNS
    from schema import RAW_DICTIONARY as RAW_DICTIONARY
    from schema import ZERO_FILL_COLUMNS as ZERO_FILL_COLUMNS
except ModuleNotFoundError:
    from .schema import BOOL_COLUMNS as BOOL_COLUMNS
    from .schema import HOURLY_COLUMNS as HOURLY_COLUMNS
    from .schema import HOURLY_DICTIONARY as HOURLY_DICTIONARY
    from .schema import NUMERIC_COLUMNS as NUMERIC_COLUMNS
    from .schema import RAW_COLUMNS as RAW_COLUMNS
    from .schema import RAW_DICTIONARY as RAW_DICTIONARY
    from .schema import ZERO_FILL_COLUMNS as ZERO_FILL_COLUMNS


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


def capped_hours_from_metadata(collection_metadata: dict[str, Any] | None) -> set[pd.Timestamp]:
    if not collection_metadata:
        return set()
    return {
        pd.Timestamp(hour).tz_convert("UTC")
        for hour in collection_metadata.get("capped_hours_utc", [])
    }


def build_hourly_features(
    raw_df: pd.DataFrame,
    collection_metadata: dict[str, Any] | None = None,
) -> pd.DataFrame:
    df = raw_df.copy()
    df["forward_fee_total"] = df["total_fwd_fees"]

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
    capped_hours = capped_hours_from_metadata(collection_metadata)
    if capped_hours:
        hourly["is_capped_hour"] = hourly["hour"].isin(capped_hours).astype(int)
    else:
        page_limit = (collection_metadata or {}).get("limit")
        if page_limit:
            hourly["is_capped_hour"] = (hourly["tx_count"] >= int(page_limit)).astype(int)
        else:
            hourly["is_capped_hour"] = 0

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
    hourly = hourly.sort_values("hour").set_index("hour").asfreq("h")
    if "is_capped_hour" in hourly.columns:
        hourly["is_capped_hour"] = hourly["is_capped_hour"].fillna(0).astype(int)

    hourly["hour_of_day"] = hourly.index.hour
    hourly["day_of_week"] = hourly.index.dayofweek
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

    hourly["hour_sin"] = np.sin(2 * np.pi * hourly["hour_of_day"] / 24)
    hourly["hour_cos"] = np.cos(2 * np.pi * hourly["hour_of_day"] / 24)
    hourly["day_sin"] = np.sin(2 * np.pi * hourly["day_of_week"] / 7)
    hourly["day_cos"] = np.cos(2 * np.pi * hourly["day_of_week"] / 7)

    hourly["target_next_hour_avg_fee"] = hourly["avg_total_fee"].shift(-1)
    if "std_total_fee" in hourly.columns:
        hourly["std_total_fee"] = hourly["std_total_fee"].fillna(0)
    if "tx_count" in hourly.columns:
        hourly = hourly[hourly["tx_count"].notna()].copy()
    if "is_capped_hour" not in hourly.columns:
        hourly["is_capped_hour"] = 0

    for column in HOURLY_COLUMNS:
        if column not in hourly.columns:
            hourly[column] = np.nan

    hourly["hour"] = hourly.index.strftime("%Y-%m-%dT%H:%M:%SZ")
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



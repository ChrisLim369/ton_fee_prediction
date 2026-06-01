import numpy as np
import pandas as pd

from src.features import recompute_hourly_derived_features


def hourly_frame(hours: pd.DatetimeIndex, fees: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hour": hours.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tx_count": [fee * 100 for fee in fees],
            "is_capped_hour": 0,
            "unique_accounts": [10 for _ in fees],
            "avg_total_fee": fees,
            "median_total_fee": fees,
            "p90_total_fee": fees,
            "min_total_fee": fees,
            "max_total_fee": fees,
            "std_total_fee": [0.0 for _ in fees],
            "avg_gas_used": fees,
            "median_gas_used": fees,
            "avg_compute_fee": fees,
            "avg_storage_fee": fees,
            "avg_action_fee": fees,
            "avg_forward_fee": fees,
            "avg_import_fee": fees,
            "avg_vm_steps": fees,
            "avg_msgs_created": fees,
            "avg_out_msg_count": fees,
            "avg_msg_size_bits": fees,
            "avg_msg_size_cells": fees,
            "failed_tx_ratio": [0.0 for _ in fees],
            "compute_success_ratio": [1.0 for _ in fees],
            "action_success_ratio": [1.0 for _ in fees],
            "avg_transaction_value": fees,
            "total_transaction_value": fees,
        }
    )


def test_recompute_hourly_features_has_expected_offsets() -> None:
    hours = pd.date_range("2024-01-01T00:00:00Z", periods=50, freq="h")
    fees = [float(index) for index in range(1, 51)]

    result = recompute_hourly_derived_features(hourly_frame(hours, fees)).reset_index(drop=True)

    assert result.loc[10, "fee_lag_1h"] == 10.0
    assert result.loc[30, "fee_lag_24h"] == 7.0
    assert result.loc[10, "rolling_avg_fee_3h"] == 9.0
    assert result.loc[10, "fee_change_1h"] == 1.0
    assert result.loc[10, "target_next_hour_avg_fee"] == 12.0


def test_recompute_hourly_features_uses_time_index_across_gaps() -> None:
    hours = pd.date_range("2024-01-01T00:00:00Z", periods=50, freq="h")
    fees = [float(index) for index in range(1, 51)]
    df = hourly_frame(hours, fees).drop(index=range(24, 31)).reset_index(drop=True)

    result = recompute_hourly_derived_features(df).reset_index(drop=True)
    result_hours = set(result["hour"])
    after_gap = result[result["hour"] == "2024-01-02T07:00:00Z"].iloc[0]
    points_into_gap = result[result["hour"] == "2024-01-03T00:00:00Z"].iloc[0]
    later = result[result["hour"] == "2024-01-02T10:00:00Z"].iloc[0]

    assert "2024-01-02T00:00:00Z" not in result_hours
    assert "2024-01-02T06:00:00Z" not in result_hours
    assert after_gap["fee_lag_24h"] == 8.0
    assert np.isnan(points_into_gap["fee_lag_24h"])
    assert later["fee_lag_24h"] == 11.0


def test_recompute_hourly_features_keeps_larger_tx_count_duplicate_and_recomputes_cap() -> None:
    hour = "2024-01-01T00:00:00Z"
    low_count_capped = hourly_frame(pd.DatetimeIndex([pd.Timestamp(hour)]), [100.0])
    low_count_capped["tx_count"] = 100
    low_count_capped["collection_cap"] = 100
    low_count_capped["is_capped_hour"] = 1
    high_count_complete = hourly_frame(pd.DatetimeIndex([pd.Timestamp(hour)]), [200.0])
    high_count_complete["tx_count"] = 120
    high_count_complete["collection_cap"] = 200
    high_count_complete["is_capped_hour"] = 1

    result = recompute_hourly_derived_features(pd.concat([low_count_capped, high_count_complete], ignore_index=True))

    row = result.iloc[0]
    assert row["tx_count"] == 120
    assert row["avg_total_fee"] == 200.0
    assert row["collection_cap"] == 200
    assert row["is_capped_hour"] == 0

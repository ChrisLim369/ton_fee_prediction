import numpy as np
import pandas as pd

from src.features import recompute_hourly_derived_features
from src.models.backtest import rolling_backtest_model_suite
from src.models.suite import build_model_candidates, train_model_suite
from src.schema import MODEL_FEATURE_COLUMNS


def synthetic_hourly_features(rows: int = 720) -> pd.DataFrame:
    hours = pd.date_range("2024-01-01T00:00:00Z", periods=rows, freq="h")
    hour_index = np.arange(rows, dtype=float)
    fees = 1_000_000 + 500_000 * np.sin(2 * np.pi * hour_index / 24) + 10_000 * np.sin(hour_index / 5)
    base = pd.DataFrame(
        {
            "hour": hours.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tx_count": 100 + (hour_index % 24),
            "is_capped_hour": 0,
            "unique_accounts": 80 + (hour_index % 10),
            "avg_total_fee": fees,
            "median_total_fee": fees * 0.95,
            "p90_total_fee": fees * 1.2,
            "min_total_fee": fees * 0.6,
            "max_total_fee": fees * 1.5,
            "std_total_fee": np.full(rows, 1000.0),
            "avg_gas_used": 500 + hour_index % 20,
            "median_gas_used": 480 + hour_index % 20,
            "avg_compute_fee": fees * 0.35,
            "avg_storage_fee": fees * 0.05,
            "avg_action_fee": fees * 0.1,
            "avg_forward_fee": fees * 0.03,
            "avg_import_fee": fees * 0.02,
            "avg_vm_steps": 1000 + hour_index,
            "avg_msgs_created": 2 + hour_index % 3,
            "avg_out_msg_count": 1 + hour_index % 2,
            "avg_msg_size_bits": 256 + hour_index,
            "avg_msg_size_cells": 2 + hour_index % 4,
            "failed_tx_ratio": np.zeros(rows),
            "compute_success_ratio": np.ones(rows),
            "action_success_ratio": np.ones(rows),
            "avg_transaction_value": fees * 10,
            "total_transaction_value": fees * 100,
        }
    )
    result = recompute_hourly_derived_features(base)
    for column in MODEL_FEATURE_COLUMNS:
        assert column in result.columns
    return result


def test_train_model_suite_returns_complete_best_model_and_candidate_comparison() -> None:
    hourly = synthetic_hourly_features()
    rolling_summary, _ = rolling_backtest_model_suite(
        hourly,
        min_train_rows=240,
        test_rows=24,
        step_rows=24,
        max_folds=1,
    )

    best_model, comparison, _, _, _ = train_model_suite(hourly, rolling_summary=rolling_summary)

    assert {"model_name", "model_type", "target_column", "feature_columns", "trained_at_utc", "metrics"} <= set(
        best_model
    )
    assert {"mae", "rmse", "r2", "mape", "directional_accuracy"} <= set(best_model["metrics"])
    assert len(comparison) == len(build_model_candidates())

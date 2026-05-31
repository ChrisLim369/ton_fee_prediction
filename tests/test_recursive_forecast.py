import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import generate_forecast  # noqa: E402
from src.features import recompute_hourly_derived_features
from src.schema import MODEL_FEATURE_COLUMNS


def synthetic_features(rows: int = 96) -> pd.DataFrame:
    hours = pd.date_range("2024-02-01T00:00:00Z", periods=rows, freq="h")
    hour_index = np.arange(rows, dtype=float)
    fees = 1_000_000 + 250_000 * np.sin(2 * np.pi * hour_index / 24)
    base = pd.DataFrame(
        {
            "hour": hours.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tx_count": 100 + hour_index,
            "is_capped_hour": 0,
            "unique_accounts": 80 + hour_index % 5,
            "avg_total_fee": fees,
            "median_total_fee": fees,
            "p90_total_fee": fees * 1.1,
            "min_total_fee": fees * 0.8,
            "max_total_fee": fees * 1.2,
            "std_total_fee": np.full(rows, 1000.0),
            "avg_gas_used": 500 + hour_index,
            "median_gas_used": 480 + hour_index,
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
    return recompute_hourly_derived_features(base)


def persistence_model() -> dict[str, object]:
    return {
        "model_name": "persistence",
        "model_type": "naive",
        "baseline_kind": "persistence",
        "target_column": "target_next_hour_avg_fee",
        "feature_columns": MODEL_FEATURE_COLUMNS,
        "trained_at_utc": "2024-01-01T00:00:00+00:00",
        "metrics": {},
        "naive_state": {"last_24_avg_total_fee": []},
    }


def ridge_model(intercept: float) -> dict[str, object]:
    return {
        "model_name": "ridge_alpha_1",
        "model_type": "ridge_regression",
        "target_column": "target_next_hour_avg_fee",
        "target_transform": "none",
        "alpha": 1.0,
        "feature_columns": MODEL_FEATURE_COLUMNS,
        "trained_at_utc": "2024-01-01T00:00:00+00:00",
        "intercept": intercept,
        "coefficients_scaled": {column: 0.0 for column in MODEL_FEATURE_COLUMNS},
        "impute_values": {column: 0.0 for column in MODEL_FEATURE_COLUMNS},
        "feature_means": {column: 0.0 for column in MODEL_FEATURE_COLUMNS},
        "feature_stds": {column: 1.0 for column in MODEL_FEATURE_COLUMNS},
        "metrics": {},
    }


def run_generate(tmp_path: Path, features: pd.DataFrame, model: dict[str, object]) -> pd.DataFrame:
    features_path = tmp_path / "hourly_features.csv"
    model_path = tmp_path / "best_model.json"
    output_path = tmp_path / "predictions.csv"
    features.to_csv(features_path, index=False)
    model_path.write_text(json.dumps(model), encoding="utf-8")

    result = generate_forecast.generate(
        argparse.Namespace(
            features=str(features_path),
            model=str(model_path),
            output=str(output_path),
            horizon_hours=24,
            return_frame=True,
        )
    )
    assert isinstance(result, pd.DataFrame)
    return result


def assert_bounded_forecast(result: pd.DataFrame, history: pd.DataFrame) -> None:
    predictions = result["predicted_avg_total_fee"]
    assert len(result) == 24
    assert np.isfinite(predictions).all()
    assert predictions.between(0, history["avg_total_fee"].max() * 3).all()


def test_recursive_forecast_is_bounded_for_persistence_model(tmp_path: Path) -> None:
    features = synthetic_features()
    result = run_generate(tmp_path, features, persistence_model())

    assert_bounded_forecast(result, features)


def test_recursive_forecast_is_bounded_for_ridge_model(tmp_path: Path) -> None:
    features = synthetic_features()
    result = run_generate(tmp_path, features, ridge_model(float(features["avg_total_fee"].max() * 100)))

    assert_bounded_forecast(result, features)


def test_recursive_forecast_matches_generate_output(tmp_path: Path) -> None:
    features = synthetic_features()
    model = persistence_model()
    result = run_generate(tmp_path, features, model)
    df = generate_forecast.numeric_hourly(tmp_path / "hourly_features.csv", model["feature_columns"])
    generated_at = datetime.fromisoformat(result.iloc[0]["forecast_generated_at"].replace("Z", "+00:00"))

    direct = pd.DataFrame(generate_forecast.recursive_forecast(df, model, 24, generated_at))

    pd.testing.assert_frame_equal(result, direct)

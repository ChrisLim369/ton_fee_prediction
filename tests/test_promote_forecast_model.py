import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import generate_forecast  # noqa: E402
import promote_forecast_model  # noqa: E402


def write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    best_model = tmp_path / "models" / "best_model.json"
    model_metrics = tmp_path / "models" / "model_metrics.json"
    model_comparison = tmp_path / "models" / "model_comparison.csv"
    hourly_features = tmp_path / "hourly_features.csv"
    best_model.parent.mkdir()

    best_model.write_text(
        json.dumps(
            {
                "model_name": "persistence",
                "model_type": "naive",
                "baseline_kind": "persistence",
                "target_column": "target_next_hour_avg_fee",
                "feature_columns": ["avg_total_fee", "hour_of_day"],
            }
        ),
        encoding="utf-8",
    )
    model_metrics.write_text(
        json.dumps(
            {
                "model": "models/best_model.json",
                "best_model_name": "persistence",
                "best_mae": 20.0,
                "best_rmse": 30.0,
                "best_r2": 0.1,
                "best_directional_accuracy": 0.4,
                "selected_by": "test",
                "train_rows": 10,
                "test_rows": 5,
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "mae": 9.0,
                "rmse": 10.0,
                "r2": 0.7,
                "mape": 1.2,
                "directional_accuracy": 0.8,
                "model_name": "rolling_mean_6h",
                "model_type": "naive",
                "target_transform": "none",
                "alpha": 0.0,
                "train_rows": 10,
                "test_rows": 5,
            }
        ]
    ).to_csv(model_comparison, index=False)
    rows = 30
    pd.DataFrame(
        {
            "hour": pd.date_range("2026-01-01T00:00:00Z", periods=rows, freq="h").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "avg_total_fee": [float(index) for index in range(rows)],
            "hour_of_day": [index % 24 for index in range(rows)],
        }
    ).to_csv(hourly_features, index=False)
    return best_model, model_metrics, model_comparison, hourly_features


def test_promote_writes_rolling_model_metrics_and_is_idempotent(tmp_path: Path) -> None:
    best_model_path, metrics_path, comparison_path, features_path = write_inputs(tmp_path)

    promote_forecast_model.promote(best_model_path, metrics_path, comparison_path, features_path)
    first_model_text = best_model_path.read_text(encoding="utf-8")
    first_metrics_text = metrics_path.read_text(encoding="utf-8")
    promote_forecast_model.promote(best_model_path, metrics_path, comparison_path, features_path)

    assert best_model_path.read_text(encoding="utf-8") == first_model_text
    assert metrics_path.read_text(encoding="utf-8") == first_metrics_text

    model = json.loads(first_model_text)
    metrics = json.loads(first_metrics_text)
    assert model["model_name"] == "rolling_mean_6h"
    assert model["model_type"] == "naive"
    assert model["baseline_kind"] == "rolling_mean_6h"
    assert model["feature_columns"] == ["avg_total_fee", "hour_of_day"]
    assert model["metrics"]["mae"] == 9.0
    assert model["naive_state"]["last_24_avg_total_fee"] == [float(index) for index in range(6, 30)]
    assert metrics["best_model_name"] == "rolling_mean_6h"
    assert metrics["best_mae"] == 9.0
    assert metrics["best_rmse"] == 10.0
    assert metrics["best_r2"] == 0.7
    assert metrics["best_directional_accuracy"] == 0.8
    assert "horizon-aware" in metrics["selected_by"]

    df = generate_forecast.numeric_hourly(features_path, model["feature_columns"])
    forecasts = generate_forecast.recursive_forecast(df, model, 3, datetime(2026, 1, 2, tzinfo=UTC))
    assert {row["model_name"] for row in forecasts} == {"rolling_mean_6h"}

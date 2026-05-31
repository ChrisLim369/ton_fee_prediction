import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import forecast_intervals  # noqa: E402
from tests.test_recursive_forecast import persistence_model, synthetic_features  # noqa: E402


def test_replay_residuals_group_by_horizon() -> None:
    features = synthetic_features(rows=36)
    features["avg_total_fee"] = np.arange(1, len(features) + 1, dtype=float) * 10
    features["hour_dt"] = pd.to_datetime(features["hour"], utc=True)

    residuals = forecast_intervals.replay_residuals(
        hourly=features,
        model=persistence_model(),
        horizon_hours=3,
        step_hours=1,
        min_history_hours=5,
    )

    assert residuals[1][0] == 10.0
    assert residuals[2][0] == 20.0
    assert residuals[3][0] == 30.0


def test_summarize_intervals_uses_na_for_small_horizon_samples() -> None:
    by_horizon, overall = forecast_intervals.summarize_intervals({1: [1.0] * 19}, [80, 50])

    assert by_horizon["1"]["80"] == {"width_lo": None, "width_hi": None, "coverage": None}
    assert by_horizon["1"]["50"] == {"width_lo": None, "width_hi": None, "coverage": None}
    assert overall["80"] == {"n": 0, "coverage": None}


def test_apply_intervals_preserves_points_and_orders_bounds() -> None:
    predictions = pd.DataFrame(
        {
            "forecast_generated_at": ["2024-01-01T00:00:00Z"],
            "forecast_hour": ["2024-01-01T01:00:00Z"],
            "horizon_hours": [1],
            "predicted_avg_total_fee": [100.0],
            "predicted_avg_total_fee_ton": [0.0000001],
            "model_name": ["persistence"],
            "model_trained_at_utc": ["2024-01-01T00:00:00Z"],
        }
    )
    by_horizon = {
        "1": {
            "n": 25,
            "80": {"width_lo": -120.0, "width_hi": -10.0, "coverage": 0.8},
            "50": {"width_lo": 25.0, "width_hi": 20.0, "coverage": 0.5},
        }
    }

    output = forecast_intervals.apply_intervals_to_predictions(predictions, by_horizon, [80, 50])

    assert output.loc[0, "predicted_avg_total_fee"] == 100.0
    assert output.loc[0, "predicted_avg_total_fee_lo80"] == 0.0
    assert output.loc[0, "predicted_avg_total_fee_hi80"] >= output.loc[0, "predicted_avg_total_fee_hi50"]
    assert output.loc[0, "predicted_avg_total_fee_hi50"] >= 100.0
    assert output.loc[0, "predicted_avg_total_fee_lo50"] <= 100.0
    assert output.loc[0, "predicted_avg_total_fee_lo50"] >= output.loc[0, "predicted_avg_total_fee_lo80"]


def test_run_adds_interval_columns_without_changing_point_predictions(tmp_path: Path) -> None:
    features = synthetic_features(rows=240)
    model = persistence_model()
    generated_at = datetime(2024, 1, 1, tzinfo=UTC)
    hourly = features.copy()
    hourly["hour_dt"] = pd.to_datetime(hourly["hour"], utc=True)
    predictions = pd.DataFrame(generate_predictions(hourly, model, generated_at))

    features_path = tmp_path / "hourly_features.csv"
    model_path = tmp_path / "best_model.json"
    predictions_path = tmp_path / "predictions.csv"
    report_path = tmp_path / "forecast_intervals.md"
    json_path = tmp_path / "forecast_intervals.json"
    features.to_csv(features_path, index=False)
    model_path.write_text(json.dumps(model), encoding="utf-8")
    predictions.to_csv(predictions_path, index=False)

    forecast_intervals.run(
        forecast_intervals.build_parser().parse_args(
            [
                "--features",
                str(features_path),
                "--model",
                str(model_path),
                "--predictions",
                str(predictions_path),
                "--report",
                str(report_path),
                "--json",
                str(json_path),
                "--horizon-hours",
                "3",
                "--min-history-hours",
                "24",
            ]
        )
    )

    output = pd.read_csv(predictions_path)
    assert output["predicted_avg_total_fee"].tolist() == predictions["predicted_avg_total_fee"].tolist()
    for suffix in ["lo80", "hi80", "lo50", "hi50", "lo80_ton", "hi80_ton", "lo50_ton", "hi50_ton"]:
        assert f"predicted_avg_total_fee_{suffix}" in output.columns
    assert (output["predicted_avg_total_fee_lo80"] >= 0).all()
    assert report_path.read_text(encoding="utf-8").startswith("# Forecast Prediction Intervals")


def generate_predictions(
    hourly: pd.DataFrame,
    model: dict[str, object],
    generated_at: datetime,
) -> list[dict[str, object]]:
    import generate_forecast

    return generate_forecast.recursive_forecast(hourly, model, 3, generated_at)

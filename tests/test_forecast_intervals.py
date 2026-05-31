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
    by_horizon = forecast_intervals.summarize_intervals({1: [1.0] * 19}, [80, 50])

    assert by_horizon["1"]["80"] == {"width_lo": None, "width_hi": None}
    assert by_horizon["1"]["50"] == {"width_lo": None, "width_hi": None}


def test_calibration_out_of_sample_is_not_quantile_identity() -> None:
    residuals = {1: [0.0] * 70 + [100.0] * 30}

    by_horizon, overall = forecast_intervals.calibration_out_of_sample(
        residuals,
        [80],
        fit_fraction=0.7,
        min_residuals=20,
    )

    assert by_horizon["1"]["calibration"] == {
        "method": "out_of_sample_chronological",
        "fit_fraction": 0.7,
        "fit_n": 70,
        "check_n": 30,
    }
    assert by_horizon["1"]["80"]["coverage_oos"] == 0.0
    assert overall["80"] == {"check_n": 30, "coverage_oos": 0.0}


def test_calibration_out_of_sample_requires_minimum_check_samples() -> None:
    by_horizon, overall = forecast_intervals.calibration_out_of_sample(
        {1: list(range(25))},
        [80],
        fit_fraction=0.8,
        min_residuals=20,
    )

    assert by_horizon["1"]["80"]["coverage_oos"] is None
    assert overall["80"] == {"check_n": 0, "coverage_oos": None}


def test_attach_calibration_keeps_production_widths_from_full_residuals() -> None:
    residuals = {1: [0.0] * 70 + [100.0] * 30}
    widths = forecast_intervals.summarize_intervals(residuals, [80], min_residuals=20)
    calibration, _overall = forecast_intervals.calibration_out_of_sample(
        residuals,
        [80],
        fit_fraction=0.7,
        min_residuals=20,
    )

    output = forecast_intervals.attach_calibration(widths, calibration, [80])

    assert output["1"]["80"]["width_lo"] == widths["1"]["80"]["width_lo"]
    assert output["1"]["80"]["width_hi"] == widths["1"]["80"]["width_hi"]
    assert output["1"]["80"]["coverage_oos"] == 0.0


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
                "--calibration-fit-fraction",
                "0.7",
            ]
        )
    )

    output = pd.read_csv(predictions_path)
    assert output["predicted_avg_total_fee"].tolist() == predictions["predicted_avg_total_fee"].tolist()
    for suffix in ["lo80", "hi80", "lo50", "hi50", "lo80_ton", "hi80_ton", "lo50_ton", "hi50_ton"]:
        assert f"predicted_avg_total_fee_{suffix}" in output.columns
    assert (output["predicted_avg_total_fee_lo80"] >= 0).all()
    assert report_path.read_text(encoding="utf-8").startswith("# Forecast Prediction Intervals")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "coverage" not in payload["by_horizon"]["1"]["80"]
    assert "coverage_oos" in payload["by_horizon"]["1"]["80"]
    assert payload["calibration"]["method"] == "out_of_sample_chronological"


def generate_predictions(
    hourly: pd.DataFrame,
    model: dict[str, object],
    generated_at: datetime,
) -> list[dict[str, object]]:
    import generate_forecast

    return generate_forecast.recursive_forecast(hourly, model, 3, generated_at)

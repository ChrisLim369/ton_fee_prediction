import pandas as pd

from tests.test_recursive_forecast import persistence_model, run_generate, synthetic_features

EXPECTED_COLUMNS = [
    "forecast_generated_at",
    "forecast_hour",
    "horizon_hours",
    "predicted_avg_total_fee",
    "predicted_avg_total_fee_ton",
    "model_name",
    "model_trained_at_utc",
]


def test_generate_returns_predictions_with_expected_format(tmp_path) -> None:
    result = run_generate(tmp_path, synthetic_features(), persistence_model())

    assert result.columns.tolist() == EXPECTED_COLUMNS
    assert result.notna().all().all()
    assert pd.api.types.is_integer_dtype(result["horizon_hours"])
    assert pd.api.types.is_numeric_dtype(result["predicted_avg_total_fee"])
    assert pd.api.types.is_numeric_dtype(result["predicted_avg_total_fee_ton"])

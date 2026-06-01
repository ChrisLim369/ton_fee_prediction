import pandas as pd

from src.models import suite


def hourly_features() -> pd.DataFrame:
    rows = 12
    return pd.DataFrame(
        {
            "hour": pd.date_range("2026-01-01T00:00:00Z", periods=rows, freq="h").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "avg_total_fee": [100.0 + index for index in range(rows)],
            "feature": [float(index) for index in range(rows)],
            "target_next_hour_avg_fee": [101.0 + index for index in range(rows)],
        }
    )


def select_model(monkeypatch, rolling_rows: list[dict[str, object]]) -> tuple[dict[str, object], dict[str, object]]:
    candidates = [
        {"model_name": "persistence", "model_type": "naive", "target_transform": "none"},
        {"model_name": "rolling_mean_6h", "model_type": "naive", "target_transform": "none"},
        {"model_name": "learned_model", "model_type": "ridge_regression", "target_transform": "none"},
    ]

    def fake_fit_model_candidate(candidate, split, feature_columns, target_column):
        model_name = str(candidate["model_name"])
        metrics = {
            "model_name": model_name,
            "model_type": str(candidate["model_type"]),
            "target_transform": str(candidate["target_transform"]),
            "mae": 10.0,
            "rmse": 12.0,
            "r2": 0.1,
            "mape": 1.0,
            "directional_accuracy": 0.5,
        }
        model = {"model_name": model_name, "metrics": metrics}
        coefficients = pd.DataFrame([{"model_name": model_name, "feature": "feature", "coefficient": 0.0}])
        actual_vs_predicted = pd.DataFrame(
            [
                {
                    "hour": "2026-01-01T10:00:00Z",
                    "actual_next_hour_avg_fee": 111.0,
                    "predicted_next_hour_avg_fee": 110.0,
                    "error": -1.0,
                    "absolute_error": 1.0,
                    "model_name": model_name,
                }
            ]
        )
        return model, coefficients, metrics, actual_vs_predicted

    monkeypatch.setattr(suite, "build_model_candidates", lambda: candidates)
    monkeypatch.setattr(suite, "fit_model_candidate", fake_fit_model_candidate)

    best_model, _, _, _, summary = suite.train_model_suite(
        hourly_features(),
        feature_columns=["feature"],
        rolling_summary=pd.DataFrame(rolling_rows),
    )
    return best_model, summary


def test_train_model_suite_selects_persistence_when_it_has_lowest_rolling_mean_mae(monkeypatch) -> None:
    best_model, summary = select_model(
        monkeypatch,
        [
            {"model_name": "persistence", "mean_mae": 100.0, "median_rmse": 120.0},
            {"model_name": "rolling_mean_6h", "mean_mae": 105.0, "median_rmse": 125.0},
            {"model_name": "learned_model", "mean_mae": 110.0, "median_rmse": 90.0},
        ],
    )

    assert best_model["model_name"] == "persistence"
    assert summary["selected_by"] == "rolling backtest naive fallback by mean MAE"


def test_train_model_suite_selects_model_with_positive_skill_vs_persistence(monkeypatch) -> None:
    best_model, summary = select_model(
        monkeypatch,
        [
            {"model_name": "persistence", "mean_mae": 100.0, "median_rmse": 120.0},
            {"model_name": "rolling_mean_6h", "mean_mae": 102.0, "median_rmse": 122.0},
            {"model_name": "learned_model", "mean_mae": 80.0, "median_rmse": 100.0},
        ],
    )

    assert best_model["model_name"] == "learned_model"
    assert summary["selected_by"] == "rolling backtest MAE skill vs persistence"


def test_train_model_suite_falls_back_to_naive_when_no_candidate_beats_persistence(monkeypatch) -> None:
    best_model, summary = select_model(
        monkeypatch,
        [
            {"model_name": "persistence", "mean_mae": 100.0, "median_rmse": 140.0},
            {"model_name": "rolling_mean_6h", "mean_mae": 120.0, "median_rmse": 130.0},
            {"model_name": "learned_model", "mean_mae": 110.0, "median_rmse": 80.0},
        ],
    )

    assert best_model["model_name"] == "persistence"
    assert summary["selected_by"] == "rolling backtest naive fallback by mean MAE"

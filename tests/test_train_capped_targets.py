import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import train_model  # noqa: E402


def hourly(rows: int = 4, include_capped: bool = True) -> pd.DataFrame:
    data = pd.DataFrame(
        {
            "hour": pd.date_range("2026-01-01T00:00:00Z", periods=rows, freq="h").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "avg_total_fee": [100.0, 110.0, 120.0, 130.0][:rows],
            "target_next_hour_avg_fee": [110.0, 120.0, 130.0, None][:rows],
        }
    )
    if include_capped:
        data["is_capped_hour"] = [0, 1, 0, 0][:rows]
    return data


def args_for(tmp_path, features, exclude=False) -> argparse.Namespace:
    return argparse.Namespace(
        features=str(features),
        best_model=str(tmp_path / "models" / "best_model.json"),
        metrics=str(tmp_path / "models" / "model_metrics.json"),
        coefficients=str(tmp_path / "models" / "model_coefficients.csv"),
        comparison=str(tmp_path / "models" / "model_comparison.csv"),
        rolling_backtest=str(tmp_path / "models" / "rolling_backtest.csv"),
        rolling_backtest_folds=str(tmp_path / "models" / "rolling_backtest_folds.csv"),
        feature_importance=str(tmp_path / "models" / "feature_importance.csv"),
        actual_vs_predicted=str(tmp_path / "actual_vs_predicted.csv"),
        report=str(tmp_path / "docs" / "model_evaluation_report.md"),
        target="target_next_hour_avg_fee",
        test_fraction=0.2,
        rolling_min_train_rows=2,
        rolling_test_rows=1,
        rolling_step_rows=1,
        rolling_max_folds=1,
        feature_columns=["avg_total_fee"],
        exclude_capped_targets=exclude,
    )


def test_drop_capped_target_rows_removes_rows_whose_next_hour_is_capped() -> None:
    filtered = train_model.drop_capped_target_rows(hourly())

    assert filtered["hour"].tolist() == [
        "2026-01-01T01:00:00Z",
        "2026-01-01T02:00:00Z",
        "2026-01-01T03:00:00Z",
    ]


def test_drop_capped_target_rows_returns_same_data_without_cap_column() -> None:
    data = hourly(include_capped=False)
    filtered = train_model.drop_capped_target_rows(data)

    pd.testing.assert_frame_equal(filtered, data)


def test_train_flag_off_keeps_input_rows_and_selection_result(tmp_path, monkeypatch) -> None:
    features = tmp_path / "hourly_features.csv"
    hourly().to_csv(features, index=False)
    seen_rows: list[int] = []

    def fake_rolling(hourly_df, **_kwargs):
        seen_rows.append(len(hourly_df))
        return (
            pd.DataFrame(
                [
                    {
                        "model_name": "fake_model",
                        "model_type": "fake",
                        "target_transform": "none",
                        "mean_r2": 0.5,
                        "median_rmse": 10.0,
                        "mean_mae": 1.0,
                        "mean_rmse": 2.0,
                        "folds": 1,
                    }
                ]
            ),
            pd.DataFrame([{"fold": 1, "model_name": "fake_model"}]),
        )

    def fake_train_suite(hourly_df, **_kwargs):
        seen_rows.append(len(hourly_df))
        best_model = {"model_name": "fake_model"}
        comparison = pd.DataFrame([{"model_name": "fake_model", "r2": 0.5}])
        feature_importance = pd.DataFrame([{"model_name": "fake_model", "feature": "avg_total_fee"}])
        actual_vs_predicted = pd.DataFrame(
            [
                {
                    "hour": "2026-01-01T00:00:00Z",
                    "actual_next_hour_avg_fee": 110.0,
                    "predicted_next_hour_avg_fee": 109.0,
                    "error": -1.0,
                    "absolute_error": 1.0,
                    "model_name": "fake_model",
                }
            ]
        )
        summary = {
            "best_model_name": "fake_model",
            "selected_by": "test",
            "best_r2": 0.5,
            "best_mae": 1.0,
            "best_rmse": 2.0,
            "best_directional_accuracy": 0.75,
        }
        return best_model, comparison, feature_importance, actual_vs_predicted, summary

    monkeypatch.setattr(train_model, "rolling_backtest_model_suite", fake_rolling)
    monkeypatch.setattr(train_model, "train_model_suite", fake_train_suite)
    monkeypatch.setattr(train_model, "PROJECT_ROOT", tmp_path)

    result = train_model.train(args_for(tmp_path, features, exclude=False))

    assert seen_rows == [4, 4]
    assert result["best_model_name"] == "fake_model"
    assert "capped_target_exclusion" not in result

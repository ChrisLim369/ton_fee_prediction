import json

import pandas as pd

from src.track_accuracy import append_forecast_log, reconcile_and_report


def write_predictions(path) -> None:
    pd.DataFrame(
        [
            {
                "forecast_generated_at": "2026-01-02T03:30:00Z",
                "forecast_hour": "2026-01-02T04:00:00Z",
                "horizon_hours": 1,
                "predicted_avg_total_fee": 110.0,
                "predicted_avg_total_fee_ton": 0.000000110,
                "model_name": "test_model",
                "model_trained_at_utc": "2026-01-02T00:00:00Z",
            },
            {
                "forecast_generated_at": "2026-01-02T03:30:00Z",
                "forecast_hour": "2026-01-02T05:00:00Z",
                "horizon_hours": 2,
                "predicted_avg_total_fee": 80.0,
                "predicted_avg_total_fee_ton": 0.000000080,
                "model_name": "test_model",
                "model_trained_at_utc": "2026-01-02T00:00:00Z",
            },
            {
                "forecast_generated_at": "2026-01-02T03:30:00Z",
                "forecast_hour": "2026-01-02T06:00:00Z",
                "horizon_hours": 3,
                "predicted_avg_total_fee": 130.0,
                "predicted_avg_total_fee_ton": 0.000000130,
                "model_name": "test_model",
                "model_trained_at_utc": "2026-01-02T00:00:00Z",
            },
        ]
    ).to_csv(path, index=False)


def write_hourly(path, include_actuals: bool) -> None:
    rows = [
        {"hour": "2026-01-02T02:00:00Z", "avg_total_fee": 90.0, "is_capped_hour": 0},
        {"hour": "2026-01-02T03:00:00Z", "avg_total_fee": 95.0, "is_capped_hour": 0},
    ]
    if include_actuals:
        rows.extend(
            [
                {"hour": "2026-01-02T04:00:00Z", "avg_total_fee": 100.0, "is_capped_hour": 0},
                {"hour": "2026-01-02T05:00:00Z", "avg_total_fee": 100.0, "is_capped_hour": 1},
            ]
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_append_is_deduped_and_stores_last_observed_anchor(tmp_path) -> None:
    predictions = tmp_path / "predictions.csv"
    hourly = tmp_path / "hourly_features.csv"
    log = tmp_path / "forecast_log.csv"
    write_predictions(predictions)
    write_hourly(hourly, include_actuals=False)

    first = append_forecast_log(predictions, hourly, log)
    second = append_forecast_log(predictions, hourly, log)

    ledger = pd.read_csv(log)
    assert first["log_rows"] == 3
    assert second["log_rows"] == 3
    assert len(ledger) == 3
    assert set(ledger["last_observed_hour"]) == {"2026-01-02T03:00:00Z"}
    assert set(ledger["last_observed_fee"]) == {95.0}


def test_reconcile_calculates_live_errors_pending_rows_and_small_sample_nulls(tmp_path) -> None:
    predictions = tmp_path / "predictions.csv"
    hourly = tmp_path / "hourly_features.csv"
    log = tmp_path / "forecast_log.csv"
    accuracy = tmp_path / "forecast_accuracy.csv"
    metrics_path = tmp_path / "models" / "operational_metrics.json"
    report = tmp_path / "docs" / "operational_accuracy.md"
    write_predictions(predictions)
    write_hourly(hourly, include_actuals=False)
    append_forecast_log(predictions, hourly, log)
    write_hourly(hourly, include_actuals=True)

    metrics = reconcile_and_report(log, hourly, accuracy, metrics_path, report)

    rows = pd.read_csv(accuracy).sort_values("horizon_hours").reset_index(drop=True)
    assert len(rows) == 2
    assert rows.loc[0, "error"] == 10.0
    assert rows.loc[0, "absolute_error"] == 10.0
    assert rows.loc[0, "pct_error"] == 10.0
    assert rows.loc[0, "direction_correct"]
    assert rows.loc[1, "actual_is_capped"] == 1
    assert metrics["pending_rows"] == 1
    assert metrics["reconciled_rows"] == 2
    assert metrics["status"] == "accumulating"
    assert metrics["overall"]["mape"] is None
    assert metrics["overall"]["r2"] is None
    assert metrics["overall"]["skill_score"] is None
    assert metrics["by_capped"]["clean"]["n"] == 1
    assert metrics["by_capped"]["capped"]["n"] == 1
    assert json.loads(metrics_path.read_text(encoding="utf-8"))["status"] == "accumulating"
    assert "in-sample backtests" in report.read_text(encoding="utf-8")


def test_track_accuracy_does_not_seed_from_backtest_files(tmp_path, monkeypatch) -> None:
    predictions = tmp_path / "predictions.csv"
    hourly = tmp_path / "hourly_features.csv"
    log = tmp_path / "forecast_log.csv"
    accuracy = tmp_path / "forecast_accuracy.csv"
    metrics_path = tmp_path / "models" / "operational_metrics.json"
    report = tmp_path / "docs" / "operational_accuracy.md"
    write_predictions(predictions)
    write_hourly(hourly, include_actuals=False)

    original_read_csv = pd.read_csv
    read_paths: list[str] = []

    def recording_read_csv(path, *args, **kwargs):
        read_paths.append(str(path))
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", recording_read_csv)
    append_forecast_log(predictions, hourly, log)
    reconcile_and_report(log, hourly, accuracy, metrics_path, report)

    assert all("actual_vs_predicted" not in path for path in read_paths)
    assert all("rolling_backtest" not in path for path in read_paths)

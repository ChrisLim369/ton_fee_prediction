import json

import pandas as pd

from src import capping_report


def hourly_frame(rows: int = 10) -> pd.DataFrame:
    hours = pd.date_range("2026-01-01T00:00:00Z", periods=rows, freq="h")
    return pd.DataFrame(
        {
            "hour": hours.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "avg_total_fee": [100 + index for index in range(rows)],
            "tx_count": [5000, 5000, 5000, 1000, 1000, 1000, 1000, 1000, 1000, 1000][:rows],
            "is_capped_hour": [0, 1, 0, 0, 0, 0, 0, 0, 0, 0][:rows],
        }
    )


def holdout_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hour": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T01:00:00Z",
                "2026-01-01T02:00:00Z",
                "2026-01-01T09:00:00Z",
            ],
            "actual_next_hour_avg_fee": [120.0, 110.0, 130.0, 999.0],
            "predicted_next_hour_avg_fee": [100.0, 100.0, 125.0, 999.0],
            "error": [-20.0, -10.0, -5.0, 0.0],
            "absolute_error": [20.0, 10.0, 5.0, 0.0],
            "model_name": ["test"] * 4,
        }
    )


def test_target_is_capped_uses_next_hour_and_drops_missing_target_hour() -> None:
    hourly = hourly_frame()
    hourly["hour_dt"] = pd.to_datetime(hourly["hour"], utc=True)
    labeled = capping_report.label_holdout_targets(hourly, holdout_frame())

    assert labeled["hour"].tolist() == [
        "2026-01-01T00:00:00Z",
        "2026-01-01T01:00:00Z",
        "2026-01-01T02:00:00Z",
    ]
    assert labeled["target_is_capped"].astype(int).tolist() == [1, 0, 0]


def test_holdout_segments_reuse_compute_metrics_and_small_n_nulls(tmp_path, monkeypatch) -> None:
    hourly_path = tmp_path / "hourly_features.csv"
    holdout_path = tmp_path / "actual_vs_predicted.csv"
    hourly_frame().to_csv(hourly_path, index=False)
    holdout_frame().to_csv(holdout_path, index=False)
    calls = []

    def fake_compute_metrics(y_true, predictions, current_fee=None):
        calls.append((list(y_true), list(predictions), current_fee))
        return {
            "mae": 123.0,
            "rmse": 456.0,
            "mape": 78.0,
            "r2": 0.9,
            "directional_accuracy": float("nan"),
        }

    monkeypatch.setattr(capping_report, "compute_metrics", fake_compute_metrics)
    payload = capping_report.build_payload(hourly_path, holdout_path)

    assert len(calls) == 2
    assert payload["segments"]["clean"]["n"] == 2
    assert payload["segments"]["capped"]["n"] == 1
    assert payload["segments"]["clean"]["mae"] == 123.0
    assert payload["segments"]["clean"]["mape"] is None
    assert payload["segments"]["clean"]["r2"] is None
    assert payload["segments"]["clean"]["directional_accuracy"] is None


def test_capping_report_outputs_warnings_and_json(tmp_path) -> None:
    hourly_path = tmp_path / "hourly_features.csv"
    holdout_path = tmp_path / "actual_vs_predicted.csv"
    report_path = tmp_path / "docs" / "capping_diagnostic.md"
    json_path = tmp_path / "models" / "capping_diagnostic.json"
    hourly_frame().to_csv(hourly_path, index=False)
    holdout_frame().to_csv(holdout_path, index=False)

    payload = capping_report.build_payload(hourly_path, holdout_path)
    capping_report.write_report(report_path, payload)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    report = report_path.read_text(encoding="utf-8")
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert "7.5%" in report
    assert "Confounding" in report
    assert "Under-flag" in report
    assert "R2 raw replay" in report
    assert saved["segments"]["clean"]["persistence_mae"] is None
    assert saved["segments"]["capped"]["skill_score"] is None

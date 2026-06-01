import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import refresh_forecast_outputs  # noqa: E402


def hourly_rows(values: list[tuple[str, int, float, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "hour": hour,
                "tx_count": tx_count,
                "avg_total_fee": avg_fee,
                "p90_total_fee": avg_fee,
                "avg_gas_used": 1000.0,
                "std_total_fee": 0.0,
                "is_capped_hour": capped,
            }
            for hour, tx_count, avg_fee, capped in values
        ]
    )


def test_assess_refresh_health_flags_hourly_row_regression() -> None:
    status, reason = refresh_forecast_outputs.assess_refresh_health(
        previous_hourly_rows=100,
        current_hourly_rows=99,
        previous_latest_hour="2026-05-31T10:00:00Z",
        current_latest_hour="2026-05-31T11:00:00Z",
    )

    assert status == "degraded"
    assert reason and "row count regressed" in reason


def test_assess_refresh_health_flags_latest_hour_regression() -> None:
    status, reason = refresh_forecast_outputs.assess_refresh_health(
        previous_hourly_rows=100,
        current_hourly_rows=100,
        previous_latest_hour="2026-05-31T10:00:00Z",
        current_latest_hour="2026-05-31T09:00:00Z",
    )

    assert status == "degraded"
    assert reason and "timestamp regressed" in reason


def test_assess_refresh_health_allows_missing_previous_baseline() -> None:
    assert refresh_forecast_outputs.assess_refresh_health(None, 10, None, "2026-05-31T10:00:00Z") == (
        "success",
        None,
    )


def test_update_metadata_ignores_small_raw_final_rows_when_hourly_history_extends(tmp_path: Path) -> None:
    args = argparse.Namespace(
        last_updated=str(tmp_path / "last_updated.json"),
        metadata=str(tmp_path / "collection_metadata.json"),
        recent_raw="raw_transactions.csv",
        predictions=str(tmp_path / "predictions.csv"),
        use_raw_latest_state=True,
    )
    (tmp_path / "last_updated.json").write_text(
        json.dumps({"final_rows": 13_300_000}),
        encoding="utf-8",
    )
    pd.DataFrame([{"forecast_generated_at": "2026-05-31T16:00:00Z"}]).to_csv(
        tmp_path / "predictions.csv",
        index=False,
    )

    payload = refresh_forecast_outputs.update_metadata(
        args,
        collection_status={"final_rows": 72_000},
        merge_status={
            "previous_hourly_rows": 1512,
            "previous_latest_hour": "2026-05-31T05:00:00Z",
            "recent_raw_rows": 72_000,
            "recent_hourly_rows": 72,
            "hourly_rows": 1522,
            "oldest_feature_hour": "2026-03-29T00:00:00Z",
            "latest_feature_hour": "2026-05-31T15:00:00Z",
        },
        forecast_status={"forecast_start": "2026-05-31T16:00:00Z", "forecast_end": "2026-06-01T15:00:00Z"},
    )

    assert payload["status"] == "success"
    assert "degradation_reason" not in payload
    assert payload["previous_known_full_raw_rows"] == 13_300_000
    assert payload["final_rows"] == 72_000


def test_update_metadata_degrades_on_hourly_history_regression(tmp_path: Path) -> None:
    args = argparse.Namespace(
        last_updated=str(tmp_path / "last_updated.json"),
        metadata=str(tmp_path / "collection_metadata.json"),
        recent_raw="raw_transactions.csv",
        predictions=str(tmp_path / "predictions.csv"),
        use_raw_latest_state=True,
    )

    payload = refresh_forecast_outputs.update_metadata(
        args,
        collection_status={"final_rows": 72_000},
        merge_status={
            "previous_hourly_rows": 1512,
            "previous_latest_hour": "2026-05-31T15:00:00Z",
            "recent_raw_rows": 72_000,
            "recent_hourly_rows": 72,
            "hourly_rows": 1511,
            "oldest_feature_hour": "2026-03-29T00:00:00Z",
            "latest_feature_hour": "2026-05-31T15:00:00Z",
        },
        forecast_status={},
    )

    assert payload["status"] == "degraded"
    assert "hourly feature row count regressed" in payload["degradation_reason"]


def test_merge_hourly_features_keeps_larger_tx_count_row_on_overlap(tmp_path: Path, monkeypatch) -> None:
    hourly_path = tmp_path / "hourly_features.csv"
    existing = hourly_rows(
        [
            ("2026-05-31T00:00:00Z", 10, 100.0, 0),
            ("2026-05-31T01:00:00Z", 20, 200.0, 0),
        ]
    )
    existing.to_csv(hourly_path, index=False)
    recent = hourly_rows(
        [
            ("2026-05-31T01:00:00Z", 999, 999.0, 1),
            ("2026-05-31T02:00:00Z", 30, 300.0, 0),
        ]
    )

    monkeypatch.setattr(refresh_forecast_outputs, "read_raw_transactions", lambda _path: pd.DataFrame({"raw": [1]}))
    monkeypatch.setattr(refresh_forecast_outputs, "build_hourly_features", lambda _raw, _status: recent)

    status = refresh_forecast_outputs.merge_hourly_features(
        argparse.Namespace(recent_raw=str(tmp_path / "raw.csv"), hourly_features=str(hourly_path)),
        collection_status={},
    )
    output = pd.read_csv(hourly_path)
    overlap = output.loc[output["hour"] == "2026-05-31T01:00:00Z"].iloc[0]
    new_hour = output.loc[output["hour"] == "2026-05-31T02:00:00Z"].iloc[0]

    assert status["previous_hourly_rows"] == 2
    assert status["previous_latest_hour"] == "2026-05-31T01:00:00Z"
    assert status["hourly_rows"] == 3
    assert overlap["avg_total_fee"] == 999.0
    assert overlap["is_capped_hour"] == 1
    assert new_hour["avg_total_fee"] == 300.0

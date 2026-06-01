import pandas as pd

from src.features import build_hourly_features, normalize_bool, read_raw_transactions, write_data_dictionary
from src.schema import RAW_COLUMNS


def raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {column: 0 for column in RAW_COLUMNS}
    row.update(
        {
            "hash": "hash-default",
            "now": 1_710_000_000,
            "account": "EQDdefault",
            "lt": 1,
            "transaction_type": "trans_ord",
            "account_type": "active",
            "aborted": False,
            "compute_success": True,
            "action_success": True,
            "bounce": False,
            "destroyed": False,
        }
    )
    row.update(overrides)
    return row


def raw_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=RAW_COLUMNS).copy()
    df["timestamp"] = pd.to_datetime(df["now"], unit="s", utc=True)
    df["hour"] = df["timestamp"].dt.floor("h")
    return df


def raw_rows_for_hour(hour_start: str, rows: int, offset: int = 0) -> list[dict[str, object]]:
    timestamp = int(pd.Timestamp(hour_start).timestamp())
    return [
        raw_row(
            hash=f"hash-{offset + index}",
            lt=offset + index,
            now=timestamp,
            total_fees=1000,
            account=f"EQD{offset + index}",
        )
        for index in range(rows)
    ]


def test_read_raw_transactions_drops_rows_without_now(tmp_path) -> None:
    path = tmp_path / "raw.csv"
    rows = [
        raw_row(hash="missing-now", now=pd.NA, lt=1),
        raw_row(hash="valid-now", now=1_710_000_000, lt=2),
    ]
    pd.DataFrame(rows, columns=RAW_COLUMNS).to_csv(path, index=False)

    df = read_raw_transactions(path)

    assert list(df["hash"]) == ["valid-now"]


def test_build_hourly_features_preserves_negative_total_fee() -> None:
    df = raw_frame([raw_row(total_fees=-1000)])

    hourly = build_hourly_features(df)

    assert hourly.iloc[0]["avg_total_fee"] == -1000
    assert hourly.iloc[0]["min_total_fee"] == -1000


def test_build_hourly_features_omits_empty_hour_bucket() -> None:
    first = raw_row(hash="h1", now=1_710_000_000, lt=1, total_fees=100)
    third = raw_row(hash="h3", now=1_710_007_200, lt=2, total_fees=300)

    hourly = build_hourly_features(raw_frame([first, third]))

    assert list(hourly["hour"]) == ["2024-03-09T16:00:00Z", "2024-03-09T18:00:00Z"]


def test_build_hourly_features_zero_fee_hour_has_zero_average_and_std() -> None:
    rows = [
        raw_row(hash="zero-1", lt=1, total_fees=0),
        raw_row(hash="zero-2", lt=2, total_fees=0),
    ]

    hourly = build_hourly_features(raw_frame(rows))

    assert hourly.iloc[0]["avg_total_fee"] == 0
    assert hourly.iloc[0]["std_total_fee"] == 0


def test_build_hourly_features_uses_persisted_collection_cap_from_metadata() -> None:
    rows = [
        *raw_rows_for_hour("2026-01-01T00:00:00Z", 50_000),
        *raw_rows_for_hour("2026-01-01T01:00:00Z", 3, offset=50_000),
    ]

    hourly = build_hourly_features(
        raw_frame(rows),
        collection_metadata={"max_pages_cap": 50, "limit": 1000},
    )

    capped = hourly.loc[hourly["hour"] == "2026-01-01T00:00:00Z"].iloc[0]
    uncapped = hourly.loc[hourly["hour"] == "2026-01-01T01:00:00Z"].iloc[0]
    assert capped["collection_cap"] == 50_000
    assert capped["is_capped_hour"] == 1
    assert uncapped["collection_cap"] == 50_000
    assert uncapped["is_capped_hour"] == 0


def test_build_hourly_features_without_metadata_does_not_overflag_high_tx_count() -> None:
    hourly = build_hourly_features(raw_frame(raw_rows_for_hour("2026-01-01T00:00:00Z", 5000)))

    row = hourly.iloc[0]
    assert pd.isna(row["collection_cap"])
    assert row["is_capped_hour"] == 0


def test_write_data_dictionary_includes_collection_cap(tmp_path) -> None:
    path = tmp_path / "data_dictionary.md"

    write_data_dictionary(path)

    text = path.read_text(encoding="utf-8")
    assert "`collection_cap`" in text
    assert "Observed per-run collection upper bound" in text


def test_normalize_bool_maps_strings_and_blanks() -> None:
    normalized = normalize_bool(pd.Series(["True", "False", "", "1", "0"]))

    assert normalized.iloc[0] == 1.0
    assert normalized.iloc[1] == 0.0
    assert pd.isna(normalized.iloc[2])
    assert normalized.iloc[3] == 1.0
    assert normalized.iloc[4] == 0.0

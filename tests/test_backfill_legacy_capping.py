import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backfill_legacy_capping import backfill_legacy_capping  # noqa: E402

FIELDNAMES = ["hour", "tx_count", "is_capped_hour", "collection_cap", "other"]


def row(hour: str, tx_count: str, capped: str, cap: str, other: str) -> dict[str, str]:
    return {
        "hour": hour,
        "tx_count": tx_count,
        "is_capped_hour": capped,
        "collection_cap": cap,
        "other": other,
    }


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_backfill_legacy_capping_only_relabels_underflagged_5000_rows(tmp_path: Path) -> None:
    path = tmp_path / "hourly_features.csv"
    rows = [
        row("2026-01-01T00:00:00Z", "5000", "0", "", "a"),
        row("2026-01-01T01:00:00Z", "5000.0", "", "", "b"),
        row("2026-01-01T02:00:00Z", "5000", "1", "5000", "c"),
        row("2026-01-01T03:00:00Z", "4999", "0", "", "d"),
        row("2026-01-01T04:00:00Z", "5001", "1", "5000", "e"),
    ]
    write_rows(path, rows)

    result = backfill_legacy_capping(path, expected_relabeled=None)

    assert result.total_5000 == 3
    assert result.relabeled == 2
    assert result.already_capped == 1
    assert read_rows(path) == [
        row("2026-01-01T00:00:00Z", "5000", "1", "5000", "a"),
        row("2026-01-01T01:00:00Z", "5000.0", "1", "5000", "b"),
        rows[2],
        rows[3],
        rows[4],
    ]

    second = backfill_legacy_capping(path, expected_relabeled=None)

    assert second.total_5000 == 3
    assert second.relabeled == 0
    assert second.already_capped == 3

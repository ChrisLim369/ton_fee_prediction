#!/usr/bin/env python3
"""Relabel legacy capped hourly rows without touching other CSV cells."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path("hourly_features.csv")
EXPECTED_RELABELS = 719


@dataclass(frozen=True)
class BackfillResult:
    total_5000: int
    relabeled: int
    already_capped: int


def is_zero_or_blank(value: str | None) -> bool:
    return value in (None, "", "0", "0.0")


def is_one(value: str | None) -> bool:
    return value in ("1", "1.0")


def backfill_legacy_capping(path: Path, expected_relabeled: int | None = EXPECTED_RELABELS) -> BackfillResult:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError(f"{path} has no header")
        rows = list(reader)

    relabeled = 0
    total_5000 = 0
    already_capped = 0
    updated_rows: list[dict[str, str]] = []

    for row in rows:
        updated = dict(row)
        is_legacy_plateau = float(row["tx_count"]) == 5000.0
        if is_legacy_plateau:
            total_5000 += 1
            if is_zero_or_blank(row.get("is_capped_hour")):
                updated["collection_cap"] = "5000"
                updated["is_capped_hour"] = "1"
                relabeled += 1
            elif is_one(row.get("is_capped_hour")):
                already_capped += 1
        updated_rows.append(updated)

    result = BackfillResult(total_5000=total_5000, relabeled=relabeled, already_capped=already_capped)
    if expected_relabeled is not None and relabeled not in (expected_relabeled, 0):
        raise ValueError(f"expected {expected_relabeled} relabeled rows, found {relabeled}; {path} was not written")
    if expected_relabeled is not None and relabeled == 0 and already_capped != expected_relabeled:
        raise ValueError(
            f"expected {expected_relabeled} already capped rows on idempotent run, found {already_capped}; "
            f"{path} was not written"
        )

    if relabeled:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(updated_rows)

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--expected-relabeled", type=int, default=EXPECTED_RELABELS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = backfill_legacy_capping(args.path, expected_relabeled=args.expected_relabeled)
    print(f"tx_count==5000 total rows: {result.total_5000}")
    print(f"relabeled rows: {result.relabeled}")
    print(f"already capped rows: {result.already_capped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

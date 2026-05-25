#!/usr/bin/env python3
"""Build hourly TON transaction fee features from raw_transactions.csv."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ton_pipeline import build_hourly_features, read_raw_transactions, write_data_dictionary, write_summary  # noqa: E402


def read_json_optional(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build(args: argparse.Namespace) -> None:
    raw_path = Path(args.raw)
    hourly_path = Path(args.output)
    dictionary_path = Path(args.dictionary)
    summary_path = Path(args.summary)
    metadata_path = Path(args.metadata) if args.metadata else raw_path.with_name("collection_metadata.json")

    raw_df = read_raw_transactions(raw_path)
    collection_metadata = read_json_optional(metadata_path)
    hourly_df = build_hourly_features(raw_df, collection_metadata)

    hourly_path.parent.mkdir(parents=True, exist_ok=True)
    hourly_df.to_csv(hourly_path, index=False)

    dictionary_path.parent.mkdir(parents=True, exist_ok=True)
    write_data_dictionary(dictionary_path)
    write_summary(raw_df, hourly_df, raw_path, hourly_path, summary_path, metadata_path)

    print(
        json.dumps(
            {
                "raw_transactions": len(raw_df),
                "hourly_rows": len(hourly_df),
                "raw_date_min_utc": raw_df["timestamp"].min().isoformat(),
                "raw_date_max_utc": raw_df["timestamp"].max().isoformat(),
                "output": str(hourly_path),
                "dictionary": str(dictionary_path),
                "summary": str(summary_path),
            },
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default="raw_transactions.csv")
    parser.add_argument("--output", default="hourly_features.csv")
    parser.add_argument("--dictionary", default="docs/data_dictionary.md")
    parser.add_argument("--summary", default="docs/summary_report.md")
    parser.add_argument("--metadata", default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

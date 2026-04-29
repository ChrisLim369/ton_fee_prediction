#!/usr/bin/env python3
"""Build hourly feature data from raw_transactions.csv."""

from __future__ import annotations

import argparse
import json
import sys

from ton_pipeline import (
    build_hourly_features,
    read_raw_transactions,
    resolve_path,
    write_data_dictionary,
    write_summary,
)


def build(args: argparse.Namespace) -> dict[str, object]:
    raw_path = resolve_path(args.raw)
    output_path = resolve_path(args.output)
    dictionary_path = resolve_path(args.dictionary)
    summary_path = resolve_path(args.summary)
    metadata_path = resolve_path(args.metadata)

    raw_df = read_raw_transactions(raw_path)
    hourly_df = build_hourly_features(raw_df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    hourly_df.to_csv(output_path, index=False)
    write_data_dictionary(dictionary_path)
    write_summary(raw_df, hourly_df, raw_path, output_path, summary_path, metadata_path)

    result = {
        "raw_transactions": int(len(raw_df)),
        "hourly_rows": int(len(hourly_df)),
        "raw_date_min_utc": raw_df["timestamp"].min().isoformat(),
        "raw_date_max_utc": raw_df["timestamp"].max().isoformat(),
        "output": str(output_path),
        "dictionary": str(dictionary_path),
        "summary": str(summary_path),
    }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default="raw_transactions.csv")
    parser.add_argument("--output", default="hourly_features.csv")
    parser.add_argument("--dictionary", default="docs/data_dictionary.md")
    parser.add_argument("--summary", default="docs/summary_report.md")
    parser.add_argument("--metadata", default="collection_metadata.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print(json.dumps(build(args), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

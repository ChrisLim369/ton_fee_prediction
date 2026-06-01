#!/usr/bin/env python3
"""Mirror root serving artifacts into docs/data for Cloudflare Pages."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIRROR_FILES = (
    ("predictions.csv", "docs/data/predictions.csv"),
    ("hourly_features.csv", "docs/data/hourly_features.csv"),
    ("last_updated.json", "docs/data/last_updated.json"),
    ("collection_metadata.json", "docs/data/collection_metadata.json"),
    ("actual_vs_predicted.csv", "docs/data/actual_vs_predicted.csv"),
    ("forecast_log.csv", "docs/data/forecast_log.csv"),
    ("forecast_accuracy.csv", "docs/data/forecast_accuracy.csv"),
    ("models/best_model.json", "docs/data/models/best_model.json"),
    ("models/model_metrics.json", "docs/data/models/model_metrics.json"),
    ("models/model_comparison.csv", "docs/data/models/model_comparison.csv"),
    ("models/rolling_backtest.csv", "docs/data/models/rolling_backtest.csv"),
    ("models/operational_metrics.json", "docs/data/models/operational_metrics.json"),
    ("models/capping_diagnostic.json", "docs/data/models/capping_diagnostic.json"),
    ("models/forecast_intervals.json", "docs/data/models/forecast_intervals.json"),
)


def mirror_static_data() -> list[Path]:
    copied: list[Path] = []
    for source_name, target_name in MIRROR_FILES:
        source = ROOT / source_name
        target = ROOT / target_name
        if not source.exists():
            raise FileNotFoundError(f"required mirror source is missing: {source_name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def main() -> int:
    copied = mirror_static_data()
    for path in copied:
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

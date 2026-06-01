#!/usr/bin/env python3
"""Warn-only consistency audit for committed serving artifacts."""

from __future__ import annotations

import argparse
import csv
import filecmp
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_KEYS = ("max_pages_cap", "limit", "max_pages_per_window")


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def prediction_model_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if "model_name" not in (reader.fieldnames or []):
            return set()
        return {row["model_name"] for row in reader if row.get("model_name")}


def mirror_target(path: Path) -> Path:
    relative = path.relative_to(ROOT / "docs" / "data")
    if relative.parts[0] == "models":
        return ROOT / relative
    return ROOT / relative.name


def audit_mirror() -> int:
    print("[MIRROR DIFF]")
    differences: list[tuple[Path, Path, str]] = []
    for docs_path in sorted((ROOT / "docs" / "data").rglob("*")):
        if not docs_path.is_file():
            continue
        root_path = mirror_target(docs_path)
        if not root_path.exists():
            differences.append((docs_path, root_path, "missing root counterpart"))
        elif not filecmp.cmp(docs_path, root_path, shallow=False):
            differences.append((docs_path, root_path, "byte mismatch"))

    if differences:
        for docs_path, root_path, reason in differences:
            print(f"- {docs_path.relative_to(ROOT)} <-> {root_path.relative_to(ROOT)}: {reason}")
    else:
        print("- no mirror differences")
    return len(differences)


def semantic_values(base: Path) -> tuple[str | None, str | None, set[str]]:
    best_model = read_json(base / "models" / "best_model.json") or {}
    metrics = read_json(base / "models" / "model_metrics.json") or {}
    predictions = prediction_model_names(base / "predictions.csv")
    return best_model.get("model_name"), metrics.get("best_model_name"), predictions


def semantic_mismatch(best_model_name: str | None, metrics_model_name: str | None, prediction_names: set[str]) -> bool:
    if not best_model_name or not metrics_model_name or len(prediction_names) != 1:
        return True
    return len({best_model_name, metrics_model_name, *prediction_names}) != 1


def audit_semantic() -> int:
    print("\n[SEMANTIC]")
    mismatches = 0
    for label, base in (("root", ROOT), ("docs/data", ROOT / "docs" / "data")):
        best_model_name, metrics_model_name, prediction_names = semantic_values(base)
        print(f"- {label}:")
        print(f"  best_model.model_name: {best_model_name}")
        print(f"  model_metrics.best_model_name: {metrics_model_name}")
        print(f"  predictions.model_name values: {sorted(prediction_names)}")
        if semantic_mismatch(best_model_name, metrics_model_name, prediction_names):
            print("  status: mismatch")
            mismatches += 1
        else:
            print("  status: ok")
    return mismatches


def config_values(path: Path) -> dict[str, Any]:
    data = read_json(path) or {}
    return {key: data.get(key) for key in CONFIG_KEYS}


def audit_config() -> int:
    print("\n[CONFIG]")
    root_values = config_values(ROOT / "last_updated.json")
    docs_values = config_values(ROOT / "docs" / "data" / "last_updated.json")
    print(f"- root last_updated.json: {root_values}")
    print(f"- docs/data last_updated.json: {docs_values}")

    mismatches = 0
    for key in CONFIG_KEYS:
        if root_values.get(key) != docs_values.get(key):
            print(f"- mismatch {key}: root={root_values.get(key)} docs={docs_values.get(key)}")
            mismatches += 1
    if mismatches == 0:
        print("- root/docs collection config matches")
    return mismatches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit 1 when artifact mismatches are found")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mirror_diffs = audit_mirror()
    semantic_mismatches = audit_semantic()
    config_mismatches = audit_config()
    total = mirror_diffs + semantic_mismatches + config_mismatches

    print("\n[SUMMARY]")
    print(f"- mirror_diffs: {mirror_diffs}")
    print(f"- semantic_mismatches: {semantic_mismatches}")
    print(f"- config_mismatches: {config_mismatches}")
    print(f"- total_findings: {total}")
    print(f"- strict: {args.strict}")

    if args.strict and total:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

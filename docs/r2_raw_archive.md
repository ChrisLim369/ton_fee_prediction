# R2 Raw Transaction Archive

R2 stores durable raw transaction backups outside Git. The repository still commits
only lightweight derived data, primarily `hourly_features.csv`.

## Layout

- `raw/seed/`: one-time authoritative full raw seed uploaded from the Mac.
  Example: `raw/seed/raw_full_2026-06-01.csv`.
- `raw/snapshots/`: dated GitHub Actions runner snapshots of
  `raw_transactions.csv`.
  Example: `raw/snapshots/raw_20260601T150000Z.csv`.

Snapshot keys include a UTC timestamp, so workflow uploads never overwrite a
previous object. The workflow treats R2 as non-fatal durability: missing secrets
skip the step, and upload failures do not block the forecast pipeline.

## Recovery

To rebuild the raw archive locally:

1. Download every object under `raw/seed/` and `raw/snapshots/`.
2. Concatenate the CSV files.
3. Drop duplicates with `subset=["hash", "lt"]`.
4. Run the feature build path to regenerate `hourly_features.csv`.

The pipeline already de-duplicates raw transactions by `hash` and `lt`, so
overlap between the seed and later snapshots is expected and safe.

## Limits

`raw/snapshots/` contains the runner's recent raw buffer snapshots, not a
standalone full-history source. The authoritative archive is the Mac seed plus
the accumulated runner snapshots after the seed date.

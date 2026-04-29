# Automation Guide

The project supports incremental updates as new TON transactions are indexed by TON Center API v3.

## Manual Hourly Update

Run these commands from the project root:

```bash
python src/update_data.py
python src/build_features.py
python src/generate_forecast.py
```

Train or refresh the full model suite:

```bash
python src/train_model.py
```

Recommended cadence:

- Every hour: run `update_data.py`, `build_features.py`, and `generate_forecast.py`.
- Once per day: run `train_model.py`, then regenerate the forecast and charts.

## API Key

For higher TON Center API limits, set:

```bash
export TONCENTER_API_KEY="your_key_here"
```

Without an API key, requests are limited by TON Center public access and high-volume hours may be sampled.

For larger historical backfills, use streaming mode so fetched rows are written through a temporary CSV instead of being kept in memory:

```bash
python src/update_data.py \
  --stream \
  --start-date 2026-04-21T06:00:00Z \
  --end-date 2026-04-28T07:00:00Z \
  --limit 1000 \
  --max-pages-per-window 5 \
  --workchain 0
```

## Local Cron

Hourly update:

```cron
0 * * * * cd /path/to/project && /usr/bin/env python3 src/update_data.py && /usr/bin/env python3 src/build_features.py && /usr/bin/env python3 src/generate_forecast.py
```

Daily retraining at 00:10 UTC:

```cron
10 0 * * * cd /path/to/project && /usr/bin/env python3 src/train_model.py && /usr/bin/env python3 src/generate_forecast.py && /usr/bin/env python3 scripts/generate_charts.py
```

The minimal command requested for collection only is:

```cron
0 * * * * python /path/to/project/src/update_data.py
```

## GitHub Actions

A local workflow template can be kept at `.github/workflows/update_data.yml`, but uploading workflow files to GitHub requires a token with the `workflow` scope. If your current GitHub token does not have that scope, commit the project first without the workflow file and add the workflow later from GitHub or from a workflow-scoped token.

When enabled, the workflow runs hourly. It:

- Installs dependencies.
- Runs `python src/update_data.py`.
- Rebuilds `hourly_features.csv`.
- Retrains the model once per day, or when the model is missing.
- Generates `predictions.csv`.
- Commits updated CSVs, predictions, model metrics, and `last_updated.json`.

Add `TONCENTER_API_KEY` as a repository secret if you want higher API throughput.

## Dashboard Inputs

Dashboard code should load:

- `hourly_features.csv` for historical metrics and charts.
- `predictions.csv` for the next 24-hour fee forecast.
- `models/model_comparison.csv` for chronological holdout model comparison.
- `models/rolling_backtest.csv` for rolling validation model comparison.
- `models/model_coefficients.csv` and `models/feature_importance.csv` for feature importance.
- `last_updated.json` for freshness and update status.

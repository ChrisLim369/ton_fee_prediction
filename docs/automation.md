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

The repository contains two scheduled workflows:

- `.github/workflows/hourly_forecast_update.yml`: runs hourly, restores ignored `raw_transactions.csv` from GitHub Actions cache, updates it incrementally, merges refreshed hourly aggregates into `hourly_features.csv`, regenerates `predictions.csv`, regenerates charts, saves the raw CSV back to cache, and commits lightweight outputs.
- `.github/workflows/daily_model_retrain.yml`: runs daily, restores and updates cached raw data, refreshes hourly data, retrains the model suite, regenerates the forecast and charts, saves the raw CSV back to cache, and commits lightweight model outputs.

The workflows intentionally do not commit `raw_transactions.csv`. GitHub Actions uses `src/refresh_forecast_outputs.py` with `actions/cache` so raw state can continue across workflow runs without being tracked by Git. If the cache is evicted or missing, the workflow bootstraps recent raw data and preserves older derived history through `hourly_features.csv`.

Add `TONCENTER_API_KEY` as a repository secret if you want higher API throughput. After a workflow commits lightweight outputs to `main`, Cloudflare Pages redeploys automatically. Keep data collection, model training, and chart generation in GitHub Actions rather than inside the webhook.

Detailed hosted refresh notes are in `docs/automation_forecast_refresh.md`.

## Dashboard Inputs

Dashboard code should load:

- `hourly_features.csv` for historical metrics and charts.
- `predictions.csv` for the next 24-hour fee forecast.
- `models/model_comparison.csv` for chronological holdout model comparison.
- `models/rolling_backtest.csv` for rolling validation model comparison.
- `models/model_coefficients.csv` and `models/feature_importance.csv` for feature importance.
- `last_updated.json` for freshness and update status.

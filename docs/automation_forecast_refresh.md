# Automated Forecast Refresh

This document explains how the Telegram `/forecast` command gets refreshed without doing data collection or model training inside Telegram request handlers.

## Architecture

```text
GitHub Actions workflow
-> restore ignored raw_transactions.csv from GitHub Actions cache
-> update raw_transactions.csv incrementally
-> save raw_transactions.csv back to GitHub Actions cache
-> merge refreshed hourly aggregates into committed hourly_features.csv
-> regenerate predictions.csv
-> regenerate SVG diagnostics and Telegram forecast PNG chart
-> commit lightweight outputs back to GitHub
-> main push triggers Cloudflare Pages deployment
-> Telegram webhook reads the newest static CSV/JSON/chart files
```

Telegram handlers stay read-only. They only read deployed files and send text responses. This keeps `/forecast` fast and prevents Telegram requests from triggering long API calls, training jobs, file writes, or secret exposure.

Webhook single source: `functions/telegram-webhook.ts` is the Cloudflare Pages Function; `src/telegram_bot.py` is local polling/diagnostics only.

## Workflows

Cloudflare Pages redeploys automatically on pushes to `main`. Heavy data collection, model training, and chart generation remain in GitHub Actions so Telegram requests stay lightweight.

Daily forecast workflow:

```text
.github/workflows/hourly_forecast_update.yml
```

Runs on the configured refresh cadence and can also be triggered manually. It executes:

```bash
python src/refresh_forecast_outputs.py \
  --recent-raw raw_transactions.csv \
  --recent-status .automation_raw_last_updated.json \
  --use-raw-latest-state \
  --preserve-raw \
  --bootstrap-days 3 \
  --limit 1000 \
  --max-pages-per-window 1 \
  --workchain 0 \
  --stream
python scripts/generate_charts.py
```

It commits only lightweight outputs:

```text
hourly_features.csv
predictions.csv
last_updated.json
collection_metadata.json
docs/figures/*.svg
docs/figures/*.png
```

Weekly retraining workflow:

```text
.github/workflows/daily_model_retrain.yml
```

Runs on the configured retraining cadence and can also be triggered manually. It refreshes the recent hourly data first, then runs:

```bash
python src/train_model.py
python src/generate_forecast.py
python scripts/generate_charts.py
```

It commits lightweight model and forecast outputs:

```text
models/best_model.json
models/linear_regression_model.json
models/model_metrics.json
models/model_comparison.csv
models/rolling_backtest.csv
models/rolling_backtest_folds.csv
models/model_coefficients.csv
models/feature_importance.csv
actual_vs_predicted.csv
hourly_features.csv
predictions.csv
last_updated.json
collection_metadata.json
docs/model_evaluation_report.md
docs/figures/*.svg
docs/figures/*.png
```

Both workflows use concurrency so overlapping runs do not write at the same time. If no tracked output changes, the workflow exits cleanly without creating an empty commit.

## Raw Data Strategy

`raw_transactions.csv` is intentionally not committed because it is large and can grow quickly.

In the GitHub Actions-only setup, the raw CSV is persisted through GitHub Actions cache:

```text
actions/cache/restore@v4
-> raw_transactions.csv
-> src/refresh_forecast_outputs.py updates it
-> actions/cache/save@v4
```

The cache key starts with:

```text
ton-raw-transactions-
```

This keeps raw data out of Git commits while still letting scheduled runs continue from the previous raw state.

The automated workflow uses:

```text
src/refresh_forecast_outputs.py
```

When used without cache, the script can still collect a recent temporary window into:

```text
.automation_recent_raw_transactions.csv
.automation_recent_last_updated.json
```

Those files are ignored by Git and removed after the refresh. In cache mode, `raw_transactions.csv` is also ignored by Git but preserved for `actions/cache/save`.

The script then:

1. Updates the available raw transaction state.
2. Builds hourly aggregates from the available raw data.
3. Merges those rows into the existing committed `hourly_features.csv`.
4. Recomputes lag, rolling, calendar, and target columns across the merged hourly history.
5. Regenerates `predictions.csv` from `models/best_model.json`.
6. Updates `last_updated.json` and `collection_metadata.json` with freshness fields.

The first Actions run may not have a raw cache yet. In that case the workflow bootstraps a recent 3-day raw window, merges it into the existing committed hourly history, then saves that raw file into the cache. Later runs restore and extend that cached raw file.

GitHub Actions cache is useful for this low-cost setup, but it is not a durable database. Cache entries can be evicted when repository cache storage is full or when they age out. If that happens, the workflow will bootstrap again from recent data and preserve older derived history through `hourly_features.csv`.

## Cloudflare Pages Deployment

The Cloudflare Pages bot reads static CSV/JSON/SVG/PNG files served from the Pages deployment. GitHub Actions mirrors refreshed outputs into `docs/data/`, commits lightweight outputs, and pushes to `main`; that push triggers a Cloudflare Pages deployment automatically.

Cloudflare Pages settings:

```text
Framework: None
Build command: none
Output directory: docs
```

No build hook is required.

## Required Secrets

GitHub Actions:

```text
TONCENTER_API_KEY
```

Cloudflare Pages > Settings > Variables and Secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET
```

Never commit these values.

## Bot Freshness

`/forecast` now shows:

```text
forecast generated timestamp
forecast start/end
latest feature hour
latest raw transaction timestamp
forecast age
freshness status
```

`/status` shows the automated update state in one place. A forecast is marked stale when it is older than 6 hours or when the forecast window has already ended.

## Manual Local Refresh

Use this when you want to refresh lightweight outputs locally without committing `raw_transactions.csv`:

```bash
python3 src/refresh_forecast_outputs.py \
  --lookback-hours 72 \
  --limit 1000 \
  --max-pages-per-window 1 \
  --workchain 0
python3 scripts/generate_charts.py
```

Use this to mimic the GitHub Actions cache mode locally:

```bash
python3 src/refresh_forecast_outputs.py \
  --recent-raw raw_transactions.csv \
  --recent-status .automation_raw_last_updated.json \
  --use-raw-latest-state \
  --preserve-raw \
  --bootstrap-days 3 \
  --limit 1000 \
  --max-pages-per-window 1 \
  --workchain 0 \
  --stream
python3 scripts/generate_charts.py
```

Full local refresh with the large raw CSV still works:

```bash
python3 src/update_data.py --stream
python3 src/build_features.py
python3 src/train_model.py
python3 src/generate_forecast.py
python3 scripts/generate_charts.py
```

Do not commit `raw_transactions.csv`.

## Remaining Limitations

The GitHub Actions-only setup stores raw state in GitHub Actions cache, not in a dedicated database or object store. This is cheaper and simpler than VPS/object storage, but less durable.

If the raw cache is restored, weekly retraining uses hourly features rebuilt from the available cached raw state merged into the existing committed hourly history. If the cache is missing or evicted, the workflow bootstraps recent raw data again and keeps older history from `hourly_features.csv`.

If TON Center page limits are hit, `tx_count` and `unique_accounts` remain sampled activity indicators rather than full-chain counts. For production-grade durability, use a VPS or object storage later.

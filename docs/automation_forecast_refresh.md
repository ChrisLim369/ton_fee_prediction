# Automated Forecast Refresh

This document explains how the Telegram `/forecast` command gets refreshed without doing data collection or model training inside Telegram request handlers.

## Architecture

```text
GitHub Actions schedule
-> collect recent TON transactions into ignored temporary raw CSV
-> merge recent hourly aggregates into committed hourly_features.csv
-> regenerate predictions.csv
-> regenerate SVG charts
-> commit lightweight outputs back to GitHub
-> Netlify redeploys from GitHub or via optional build hook
-> Telegram webhook reads the newest deployed CSV/JSON/SVG files
```

Telegram handlers stay read-only. They only read deployed files and send text responses. This keeps `/forecast` fast and prevents Telegram requests from triggering long API calls, training jobs, file writes, or secret exposure.

## Workflows

Hourly workflow:

```text
.github/workflows/hourly_forecast_update.yml
```

Runs hourly and manually through `workflow_dispatch`. It executes:

```bash
python src/refresh_forecast_outputs.py \
  --lookback-hours 72 \
  --limit 1000 \
  --max-pages-per-window 1 \
  --workchain 0
python scripts/generate_charts.py
```

It commits only lightweight outputs:

```text
hourly_features.csv
predictions.csv
last_updated.json
collection_metadata.json
docs/figures/*.svg
```

Daily workflow:

```text
.github/workflows/daily_model_retrain.yml
```

Runs daily and manually through `workflow_dispatch`. It refreshes the recent hourly data first, then runs:

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
```

Both workflows use concurrency so overlapping runs do not write at the same time. If no tracked output changes, the workflow exits cleanly without creating an empty commit.

## Raw Data Strategy

`raw_transactions.csv` is intentionally not committed because it is large and can grow quickly.

The automated workflow uses:

```text
src/refresh_forecast_outputs.py
```

That script collects a recent temporary window into:

```text
.automation_recent_raw_transactions.csv
.automation_recent_last_updated.json
```

Those files are ignored by Git and removed after the refresh. The script then:

1. Builds hourly aggregates from the recent temporary raw data.
2. Merges those rows into the existing committed `hourly_features.csv`.
3. Recomputes lag, rolling, calendar, and target columns across the merged hourly history.
4. Regenerates `predictions.csv` from `models/best_model.json`.
5. Updates `last_updated.json` and `collection_metadata.json` with freshness fields.

This means GitHub stores lightweight derived history, not the full raw transaction export. `final_rows` in metadata keeps the previous known full local raw row count when available, while `recent_raw_rows_collected` reports the current CI refresh sample size.

## Netlify Redeploy

The Netlify bot bundles CSV/JSON/SVG files at deploy time. Updated GitHub files must therefore trigger a new Netlify deploy.

Use one of these:

1. Connect the Netlify site `ton-fee-forecast` to the GitHub repository and deploy from `main`.
2. Or create a Netlify build hook and save it as the GitHub Actions secret:

```text
NETLIFY_BUILD_HOOK_URL
```

The workflows call the build hook only after they commit updated outputs. The hook URL is passed through an environment variable and is not printed.

## Required Secrets

GitHub Actions:

```text
TONCENTER_API_KEY
NETLIFY_BUILD_HOOK_URL   optional if Netlify is connected to GitHub
```

Netlify:

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

Use this when you want to refresh lightweight outputs locally without uploading `raw_transactions.csv`:

```bash
python3 src/refresh_forecast_outputs.py \
  --lookback-hours 72 \
  --limit 1000 \
  --max-pages-per-window 1 \
  --workchain 0
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

The CI refresh does not store full raw transaction history. It refreshes recent hourly aggregates and merges them into committed derived history. If TON Center page limits are hit, `tx_count` and `unique_accounts` remain sampled activity indicators rather than full-chain counts.

Daily retraining uses the committed hourly feature history, not full raw history. This is acceptable for the current lightweight dashboard, but deeper model research should still be done locally or with a dedicated external raw data store.

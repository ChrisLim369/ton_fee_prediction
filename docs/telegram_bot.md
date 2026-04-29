# Telegram Bot Dashboard

The project supports two Telegram bot runtimes:

- `src/telegram_bot.py`: local long-polling bot for running on your Mac or another always-on machine.
- `netlify/functions/telegram-webhook.mts`: Netlify webhook bot for 24-hour hosted operation.

Both runtimes are read-only dashboards for the TON fee prediction project. They explain the project, show the latest saved forecast, summarize model performance, and describe data quality limitations.

The bot reads existing project outputs only. It does not collect data, rebuild features, retrain models, regenerate forecasts, or write any project files.

Forecast refreshes happen outside Telegram through GitHub Actions. See `docs/automation_forecast_refresh.md` for the hourly forecast update, daily retraining, and Netlify redeploy flow.

## Required Files

The dashboard commands read these files. `netlify.toml` includes them in the Netlify Function bundle:

```text
predictions.csv
hourly_features.csv
models/model_metrics.json
models/model_comparison.csv
models/rolling_backtest.csv
last_updated.json
docs/figures/*.svg
```

`collection_metadata.json` is used as a metadata fallback when `last_updated.json` is not available.

If a file is missing or cannot be parsed, the related command returns a clear Telegram error instead of crashing the bot.

## Run Locally

Set the Telegram bot token in the environment. Do not paste the token into source files or commit it.

```bash
cd /Users/changhyuklim/ton_fee_prediction
export TELEGRAM_BOT_TOKEN="your_token_here"
python3 src/telegram_bot.py
```

The script refuses to start when `TELEGRAM_BOT_TOKEN` is not set.

## Run On Netlify

The Netlify version uses Telegram webhooks, so the bot does not need a terminal process running on your Mac.

### 1. Deploy The Site

Create or link a Netlify project from this repository. The project already includes:

```text
netlify.toml
netlify/functions/telegram-webhook.mts
package.json
tsconfig.json
```

Netlify should build the function and expose it at:

```text
https://YOUR-NETLIFY-SITE.netlify.app/telegram-webhook
```

### 2. Add Netlify Environment Variables

In Netlify, set:

```text
TELEGRAM_BOT_TOKEN=your_botfather_token
```

Optional but recommended:

```text
TELEGRAM_WEBHOOK_SECRET=a_long_random_secret
```

The function validates `TELEGRAM_WEBHOOK_SECRET` against Telegram's `X-Telegram-Bot-Api-Secret-Token` header when the variable is configured.

### 3. Register The Telegram Webhook

After the Netlify deploy is live, register the webhook:

```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_WEBHOOK_SECRET="a_long_random_secret"
export NETLIFY_BOT_URL="https://YOUR-NETLIFY-SITE.netlify.app/telegram-webhook"

curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${NETLIFY_BOT_URL}" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

If you do not configure `TELEGRAM_WEBHOOK_SECRET`, omit the `secret_token` line.

Check the registered webhook:

```bash
curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

### 4. Test

Open your Telegram bot username and send:

```text
/start
/summary
/forecast
```

The same Telegram bot token should not be used by both the local polling script and the Netlify webhook at the same time. For hosted operation, stop the local polling process after registering the webhook.

## Local Validation

Validate that all dashboard commands can render from the saved output files without connecting to Telegram:

```bash
cd /Users/changhyuklim/ton_fee_prediction
python3 -m py_compile src/telegram_bot.py
python3 src/telegram_bot.py --validate
```

`--validate` does not require `TELEGRAM_BOT_TOKEN`.

Validate the Netlify TypeScript function:

```bash
npm install
npm run check:netlify
```

## Commands

```text
/start
/help
/summary
/forecast
/status
/besttime
/model
/compare
/backtest
/quality
/charts
```

## File Roles

Runtime code:

- `src/telegram_bot.py`: local long-polling Telegram bot. Use this for local testing or for a Mac/VPS process that stays running.
- `netlify/functions/telegram-webhook.mts`: Netlify-hosted Telegram webhook. Use this for 24-hour operation without keeping a local terminal open.

Netlify deployment:

- `netlify.toml`: publishes `docs/` as the static directory and includes the dashboard CSV/JSON/SVG artifacts in the function bundle. It intentionally does not include `raw_transactions.csv`.
- `package.json`: Node project metadata and `npm run check:netlify` validation command.
- `package-lock.json`: locked Node dependency versions for reproducible Netlify function validation.
- `tsconfig.json`: TypeScript compiler settings for the Netlify function.

Dashboard inputs:

- `predictions.csv`: next 24-hour forecast shown by `/forecast` and `/besttime`.
- `hourly_features.csv`: feature row counts and latest feature timestamp shown by `/summary` and `/quality`.
- `models/model_metrics.json`: best model metrics shown by `/model` and `/summary`.
- `models/model_comparison.csv`: holdout model ranking shown by `/compare`.
- `models/rolling_backtest.csv`: rolling validation summary shown by `/backtest`.
- `last_updated.json`: latest collection status and raw row metadata shown by `/summary` and `/quality`.
- `collection_metadata.json`: fallback metadata if `last_updated.json` is unavailable.
- `docs/figures/*.svg`: chart inventory shown by `/charts`.

Automation:

- `src/refresh_forecast_outputs.py`: CI-safe refresh script. In GitHub Actions-only mode, it restores ignored `raw_transactions.csv` from Actions cache, updates it incrementally, merges refreshed hourly aggregates into `hourly_features.csv`, and regenerates `predictions.csv`.
- `.github/workflows/hourly_forecast_update.yml`: hourly cached-raw data, forecast, and chart refresh.
- `.github/workflows/daily_model_retrain.yml`: daily cached-raw refresh, model retrain, forecast, and chart refresh.
- `docs/automation_forecast_refresh.md`: hosted refresh architecture and setup guide.

## Command Details

`/summary` shows the data size, feature range, latest raw transaction timestamp, current best model, forecast availability, and the sampled-coverage limitation.

`/forecast` shows the next 24 saved forecast rows with UTC forecast hour, predicted average fee in nanoton, predicted fee in TON, model name, forecast generation time, forecast range, latest feature hour, latest raw transaction timestamp, forecast age, and a stale/fresh warning.

`/status` shows the automated refresh state, last data update time, forecast generation time, forecast age, latest feature hour, latest raw transaction timestamp, recent CI raw sample size, known full raw row count, and stale/fresh status.

`/besttime` finds the lowest predicted average fee in `predictions.csv`, compares it with the highest predicted fee in the same forecast window, and explains that the result is directional rather than guaranteed.

`/model` shows the best saved model, R2, MAE, RMSE, baseline R2, and R2 improvement. It also explains the metrics in practical language.

`/compare` reads `models/model_comparison.csv`, sorts by R2, and shows the top chronological holdout models.

`/backtest` reads `models/rolling_backtest.csv`, sorts by mean R2, and explains why rolling backtests matter for time-series reliability.

`/quality` summarizes raw row count from metadata, hourly rows, duplicate policy, TON Center API page-limit hits, and why transaction count features should be treated as sampled activity.

`/charts` lists generated chart files in `docs/figures/` and explains what each chart represents. The current charts are SVG files, so the bot lists them as text instead of sending them as Telegram preview images.

## Security Notes

- The bot token is read only from `TELEGRAM_BOT_TOKEN`.
- The local script and Netlify function do not print the token.
- Do not commit `.env` files or shell history containing the token.
- Do not upload `raw_transactions.csv` to GitHub.

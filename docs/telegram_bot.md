# Telegram Bot Dashboard

The project supports one hosted Telegram webhook and one local diagnostic runtime:

- `functions/telegram-webhook.ts`: Cloudflare Pages Function and the single source for hosted Telegram webhooks.
- `src/telegram_bot.py`: local long-polling bot for local testing and diagnostics.

Both runtimes are read-only dashboards for the TON fee prediction project. They explain the project, show the latest saved forecast, summarize model performance, and describe data quality limitations.

The bot reads existing project outputs only. It does not collect data, rebuild features, retrain models, regenerate forecasts, or write any project files.

Forecast refreshes happen outside Telegram through GitHub Actions. See `docs/automation_forecast_refresh.md` for the hourly forecast update, daily retraining, and Cloudflare Pages deployment flow.

## Required Files

The dashboard commands read deployed files. GitHub Actions mirrors these outputs into `docs/data/`, and Cloudflare Pages serves them statically:

```text
predictions.csv
hourly_features.csv
models/model_metrics.json
models/model_comparison.csv
models/rolling_backtest.csv
last_updated.json
docs/figures/*.svg
docs/figures/forecast_next_24h.png
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

## Run On Cloudflare Pages

The Cloudflare Pages version uses Telegram webhooks, so the bot does not need a terminal process running on your Mac.

### 1. Deploy The Site

Create or link a Cloudflare Pages project from this repository. Use these build settings:

```text
Framework: None
Build command: none
Output directory: docs
```

The repository already includes:

```text
functions/telegram-webhook.ts
wrangler.jsonc
tsconfig.worker.json
package.json
```

Cloudflare Pages exposes the webhook at:

```text
https://<project>.pages.dev/telegram-webhook
```

`GET /telegram-webhook` returns health-check JSON.

### 2. Add Cloudflare Pages Environment Variables

In Cloudflare Pages > Settings > Variables and Secrets, set encrypted variables:

```text
TELEGRAM_BOT_TOKEN=your_botfather_token
TELEGRAM_WEBHOOK_SECRET=a_long_random_secret
```

The function validates `TELEGRAM_WEBHOOK_SECRET` against Telegram's `X-Telegram-Bot-Api-Secret-Token` header.

### 3. Register The Telegram Webhook

After the Cloudflare Pages deploy is live, register the webhook:

```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_WEBHOOK_SECRET="a_long_random_secret"
export CLOUDFLARE_BOT_URL="https://<project>.pages.dev/telegram-webhook"

curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${CLOUDFLARE_BOT_URL}" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

Check the registered webhook:

```bash
curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

### 4. Test

Open your Telegram bot username and send:

```text
/start
/forecast
/besttime
/timezone
```

The hosted webhook source is `functions/telegram-webhook.ts`. Do not run `src/telegram_bot.py` polling with the same Telegram bot token while the Cloudflare webhook is active.

## Local Validation

Validate that all dashboard commands can render from the saved output files without connecting to Telegram:

```bash
cd /Users/changhyuklim/ton_fee_prediction
python3 -m py_compile src/telegram_bot.py
python3 src/telegram_bot.py --validate
```

`--validate` does not require `TELEGRAM_BOT_TOKEN`.

Validate the Cloudflare Pages Function:

```bash
npm install
npm run check:worker
```

## Commands

```text
/forecast
/besttime
/timezone
```

The bot still supports internal diagnostic commands when typed directly, but `/start`, `/help`, and the webhook health response intentionally show only the user-facing commands above.

## Timezone Display

Telegram does not include the user's exact device timezone in normal bot messages. The bot now estimates the display timezone from Telegram `language_code` when it can, for example Korean users are shown `Asia/Seoul`, and falls back to UTC when it cannot infer a reliable timezone.

Users can override the timezone per command with an IANA timezone name:

```text
/forecast Asia/Seoul
/besttime America/New_York
/status Europe/London
```

Use `/timezone` to see the current detected timezone and override examples. Stored forecast files remain in UTC; only the Telegram display text is converted.

## File Roles

Runtime code:

- `functions/telegram-webhook.ts`: Cloudflare Pages Function and the single hosted webhook source.
- `src/telegram_bot.py`: local long-polling Telegram bot for local testing and diagnostics.

Cloudflare Pages deployment:

- `wrangler.jsonc`: Cloudflare Pages config; static output directory is `docs`.
- `package.json`: Node project metadata and `npm run check:worker` validation command.
- `package-lock.json`: locked Node dependency versions for reproducible worker validation.
- `tsconfig.worker.json`: TypeScript compiler settings for `functions/**` and worker tests.

Dashboard inputs:

- `predictions.csv`: next 24-hour forecast shown by `/forecast` and `/besttime`.
- `hourly_features.csv`: feature row counts and latest feature timestamp shown by `/summary` and `/quality`.
- `models/model_metrics.json`: best model metrics shown by `/model` and `/summary`.
- `models/model_comparison.csv`: holdout model ranking shown by `/compare`.
- `models/rolling_backtest.csv`: rolling validation summary shown by `/backtest`.
- `last_updated.json`: latest collection status and raw row metadata shown by `/summary` and `/quality`.
- `collection_metadata.json`: fallback metadata if `last_updated.json` is unavailable.
- `docs/figures/*.svg`: diagnostic chart inventory shown by `/charts`.
- `docs/figures/forecast_next_24h.png`: Telegram-ready forecast chart sent after `/forecast`.

Automation:

- `src/refresh_forecast_outputs.py`: CI-safe refresh script. In GitHub Actions-only mode, it restores ignored `raw_transactions.csv` from Actions cache, updates it incrementally, merges refreshed hourly aggregates into `hourly_features.csv`, and regenerates `predictions.csv`.
- `.github/workflows/hourly_forecast_update.yml`: hourly cached-raw data, forecast, and chart refresh.
- `.github/workflows/daily_model_retrain.yml`: daily cached-raw refresh, model retrain, forecast, and chart refresh.
- `docs/automation_forecast_refresh.md`: hosted refresh architecture and setup guide.

## Command Details

`/forecast` shows a compact forecast card with the cheapest hour, forecast range, top cheap windows, freshness, and a Telegram-ready PNG chart of the next 24 hours.

`/besttime` finds the lowest predicted average fee in `predictions.csv`, compares it with the highest predicted fee in the same forecast window, and explains that the result is directional rather than guaranteed.

`/timezone` explains timezone detection and shows examples for overriding the displayed timezone.

## Internal Diagnostic Commands

These commands remain available for project owner/debugging use, but they are hidden from the public command list to keep the bot simple for normal users:

```text
/summary
/status
/model
/compare
/backtest
/quality
/charts
```

`/summary` shows the data size, feature range, latest raw transaction timestamp, current best model, forecast availability, and the sampled-coverage limitation.

`/status` shows the automated refresh state, last data update time, forecast generation time, forecast age, latest feature hour, latest raw transaction timestamp, recent CI raw sample size, known full raw row count, and stale/fresh status.

`/model` shows the best saved model, R2, MAE, RMSE, baseline R2, and R2 improvement. It also explains the metrics in practical language.

`/compare` reads `models/model_comparison.csv`, sorts by R2, and shows the top chronological holdout models.

`/backtest` reads `models/rolling_backtest.csv`, sorts by mean R2, and explains why rolling backtests matter for time-series reliability.

`/quality` summarizes raw row count from metadata, hourly rows, duplicate policy, TON Center API page-limit hits, and why transaction count features should be treated as sampled activity.

`/charts` lists generated chart files in `docs/figures/` and explains what each chart represents. `/forecast` sends the main PNG chart directly; the remaining charts are primarily diagnostic outputs.

## Security Notes

- The bot token is read only from `TELEGRAM_BOT_TOKEN`.
- The local script and Cloudflare Pages Function do not print the token.
- Do not commit `.env` files or shell history containing the token.
- Do not upload `raw_transactions.csv` to GitHub.

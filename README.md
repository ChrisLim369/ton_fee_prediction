# TON Transaction Fee Prediction Using On-Chain Metrics

This project collects raw TON transaction data from TON Center API v3 and builds an hourly feature table for next-hour average transaction fee prediction. It compares linear, ridge, and lightweight nonlinear gradient-boosted tree models, then uses the selected best model for a 24-hour forecast.

Korean project guide: `docs/USER_GUIDE_KO.md`

## Data Source

- Mainnet endpoint: `https://toncenter.com/api/v3/transactions`
- Documentation: TON Center API v3 `GET /transactions`
- Optional API key: set `TONCENTER_API_KEY` to send the key through the `X-API-Key` header.

Without an API key, TON Center limits requests to 1 request per second, so large historical exports should be collected over multiple runs or with an API key.

## Reproduce

```bash
python3 scripts/collect_transactions.py \
  --days 30 \
  --window-hours 1 \
  --limit 100 \
  --max-pages-per-window 1 \
  --workchain 0 \
  --sort asc \
  --output raw_transactions.csv \
  --verbose

python3 scripts/build_hourly_features.py \
  --raw raw_transactions.csv \
  --output hourly_features.csv
```

The default `--workchain 0` focuses on basechain user transactions. Use `--workchain all` to include masterchain/system transactions too.

For deeper collection, increase `--limit` up to 1000 and `--max-pages-per-window`. If any window hits the configured limit, the run should be treated as an hourly sample rather than a complete transaction export.

## Continuous Updates

Manual update:

```bash
python src/update_data.py
python src/build_features.py
python src/generate_forecast.py
```

Daily model-suite retraining:

```bash
python src/train_model.py
```

`train_model.py` compares multiple chronological holdout models and runs an expanding-window rolling backtest:

- plain linear regression baseline
- linear regression with `log1p` target
- ridge regression with several alpha values
- ridge regression with `log1p` target
- lightweight gradient-boosted regression trees

The best model is written to `models/best_model.json`, and forecasts use that file by default.

Generate SVG charts:

```bash
python scripts/generate_charts.py
```

Local cron example:

```cron
0 * * * * python /path/to/project/src/update_data.py
```

See `docs/automation.md` for the full hourly update, daily retraining, and GitHub Actions schedule.

Automated hosted refresh:

- `.github/workflows/hourly_forecast_update.yml` refreshes recent data, `hourly_features.csv`, `predictions.csv`, and charts every hour.
- `.github/workflows/daily_model_retrain.yml` refreshes recent data, retrains the model suite daily, regenerates forecasts, and updates model artifacts.
- `src/refresh_forecast_outputs.py` is the CI-safe refresh entry point. In GitHub Actions-only mode, it restores ignored `raw_transactions.csv` from Actions cache, updates it incrementally, merges hourly aggregates into the committed lightweight feature history, and never commits `raw_transactions.csv`.
- Netlify must be connected to GitHub or a `NETLIFY_BUILD_HOOK_URL` GitHub secret must be configured so committed forecast outputs trigger a fresh deploy.

See `docs/automation_forecast_refresh.md` for the deployed Telegram forecast refresh architecture.

## Telegram Bot Dashboard

The project includes a read-only Telegram chatbot dashboard that explains the project, shows the latest saved forecast, summarizes model performance, and documents data quality limitations.

Local polling mode:

```bash
cd /Users/changhyuklim/ton_fee_prediction
export TELEGRAM_BOT_TOKEN="your_token_here"
python3 src/telegram_bot.py
```

Netlify hosted webhook mode:

```text
https://ton-fee-forecast.netlify.app/telegram-webhook
```

Set `TELEGRAM_BOT_TOKEN` in Netlify environment variables, deploy this repository, then register the Telegram webhook with BotFather's token through the Telegram `setWebhook` API. Optional `TELEGRAM_WEBHOOK_SECRET` is supported for webhook request validation.

The bot reads existing output files such as `predictions.csv`, `hourly_features.csv`, `models/model_metrics.json`, `models/model_comparison.csv`, and `models/rolling_backtest.csv`. It does not retrain models or modify data inside Telegram request handlers.

User-facing commands are intentionally minimal:

```text
/forecast
/besttime
/timezone
```

Forecast and best-time timestamps are displayed in the detected Telegram language timezone when possible. Users can override the display timezone per command, for example `/forecast Asia/Seoul` or `/besttime America/New_York`.

Validate locally without starting Telegram polling:

```bash
python3 -m py_compile src/telegram_bot.py
python3 src/telegram_bot.py --validate
npm run check:netlify
```

See `docs/telegram_bot.md` for commands and operational notes.

Telegram and Netlify files:

- `src/telegram_bot.py`: local polling version for development or Mac/VPS operation.
- `netlify/functions/telegram-webhook.mts`: hosted Telegram webhook function for Netlify.
- `src/refresh_forecast_outputs.py`: GitHub Actions-safe refresh script for hourly forecast outputs without committing the full raw CSV.
- `.github/workflows/hourly_forecast_update.yml`: hourly lightweight forecast refresh workflow.
- `.github/workflows/daily_model_retrain.yml`: daily retraining and model artifact refresh workflow.
- `netlify.toml`: Netlify build/function settings and included dashboard artifact files.
- `package.json`, `package-lock.json`, `tsconfig.json`: TypeScript validation and Netlify Function dependency metadata.
- `docs/telegram_bot.md`: full dashboard, deployment, webhook, and troubleshooting guide.
- `docs/automation_forecast_refresh.md`: automated forecast refresh and Netlify redeploy guide.

## Outputs

- `raw_transactions.csv`: transaction-level rows.
- `hourly_features.csv`: hourly features, lags, rolling metrics, and next-hour prediction target.
- `predictions.csv`: next 24-hour predicted average transaction fees.
- `collection_metadata.json`: API request and sampling metadata.
- `last_updated.json`: incremental update state, latest timestamp, latest logical time, and status.
- `docs/data_dictionary.md`: column definitions for both CSVs.
- `docs/summary_report.md`: coverage, missing values, fee statistics, and limitations.
- `models/linear_regression_model.json`: legacy compatibility path; currently stores the selected best model.
- `models/best_model.json`: selected best model from the model comparison run.
- `models/model_metrics.json`: chronological holdout metrics.
- `models/model_comparison.csv`: model comparison table with MAE, RMSE, R2, and MAPE.
- `models/rolling_backtest.csv`: expanding-window rolling backtest summary by model.
- `models/rolling_backtest_folds.csv`: fold-level rolling backtest details and winners.
- `models/model_coefficients.csv`: coefficient-based feature importance table.
- `models/feature_importance.csv`: coefficients for all compared coefficient-based models.
- `actual_vs_predicted.csv`: test-period actual vs predicted values for the selected best model.
- `docs/model_evaluation_report.md`: short model evaluation summary.
- `docs/visualizations.md`: Markdown page linking generated SVG charts.
- `docs/telegram_bot.md`: Telegram chatbot dashboard guide.
- `docs/figures/`: generated SVG charts for fees, model comparisons, backtests, and forecasts.

# Cloudflare Migration

Once the Git connection is configured, the daily pushes from GitHub Actions trigger Cloudflare Pages deployments automatically.

Manual steps:

1. Cloudflare account -> Pages -> "Connect to Git" -> connect `ChrisLim369/ton_fee_prediction`.
   Build settings: Framework=None, Build command=(empty), Output directory=`docs`.
2. Run `npx wrangler login`.
3. Register environment variables/secrets in the dashboard or with:
   ```sh
   npx wrangler pages secret put TELEGRAM_BOT_TOKEN --project-name ton-fee-prediction
   npx wrangler pages secret put TELEGRAM_WEBHOOK_SECRET --project-name ton-fee-prediction
   ```
   Generate a new random string for `TELEGRAM_WEBHOOK_SECRET`.
4. Re-register the Telegram webhook:
   ```sh
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook" \
     -d "url=https://<pages-domain>/telegram-webhook" \
     -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
   ```
5. Pages -> Settings -> Builds & deployments -> Build watch paths (recommended):
   ```text
   src/**, scripts/**, functions/**, wrangler.jsonc, package.json, package-lock.json,
   tsconfig.json, .github/workflows/**, docs/data/**, docs/figures/**
   ```
   `docs/data` and `docs/figures` are refreshed daily and must publish.
6. Verify in Telegram: `/forecast Asia/Seoul` returns the KST forecast and chart PNG.
7. After one stable week on Cloudflare, remove the Netlify site/directory in a separate cleanup.

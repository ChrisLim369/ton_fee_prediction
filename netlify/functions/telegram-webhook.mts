import type { Config, Context } from "@netlify/functions";
import { readdir, readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

declare const Netlify: {
  env: {
    get(name: string): string | undefined;
  };
};

type CsvRow = Record<string, string>;
type JsonObject = Record<string, unknown>;
type TelegramMessage = {
  chat?: { id?: number | string };
  from?: { language_code?: string };
  text?: string;
};
type TelegramUpdate = {
  message?: TelegramMessage;
};

const FORECAST_STALE_HOURS = 6;
const LANGUAGE_TIMEZONE_MAP: Record<string, string> = {
  ko: "Asia/Seoul",
  ja: "Asia/Tokyo",
  zh: "Asia/Shanghai",
  "zh-cn": "Asia/Shanghai",
  "zh-hans": "Asia/Shanghai",
  "zh-tw": "Asia/Taipei",
  "zh-hant": "Asia/Taipei",
  ru: "Europe/Moscow",
  uk: "Europe/Kyiv",
  tr: "Europe/Istanbul",
  "pt-br": "America/Sao_Paulo",
  "es-mx": "America/Mexico_City",
  "en-gb": "Europe/London",
};

type TimeContext = {
  timezone: string;
  source: string;
};
type ForecastStats = {
  rows: CsvRow[];
  cheapest: { row: CsvRow; fee: number };
  highest: { row: CsvRow; fee: number };
  difference: number;
  percent: number;
};

export default async (req: Request, context: Context) => {
  if (req.method === "GET") {
    return jsonResponse({
      status: "ok",
      service: "TON fee prediction Telegram webhook",
      commands: [
        "/forecast",
        "/besttime",
        "/timezone",
      ],
      note: "Only user-facing commands are listed. Internal diagnostics remain callable when typed directly.",
    });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const configuredSecret = Netlify.env.get("TELEGRAM_WEBHOOK_SECRET");
  if (configuredSecret) {
    const receivedSecret = req.headers.get("x-telegram-bot-api-secret-token");
    if (receivedSecret !== configuredSecret) {
      return new Response("Forbidden", { status: 403 });
    }
  }

  const token = Netlify.env.get("TELEGRAM_BOT_TOKEN");
  if (!token) {
    console.error("TELEGRAM_BOT_TOKEN is not configured.");
    return new Response("Bot token is not configured", { status: 500 });
  }

  let update: TelegramUpdate;
  try {
    update = (await req.json()) as TelegramUpdate;
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }

  const chatId = update.message?.chat?.id;
  if (!chatId) {
    return jsonResponse({ ok: true, ignored: "missing chat id" });
  }

  const dashboard = new Dashboard(await findProjectRoot());
  const responseText = await dashboard.handle(update.message ?? {});
  if (!responseText) {
    return jsonResponse({ ok: true, ignored: "non-command message" });
  }

  await sendTelegramMessage(token, chatId, responseText);
  if (commandName(update.message?.text ?? "") === "/forecast") {
    try {
      await sendTelegramPhoto(token, chatId, `${new URL(req.url).origin}/figures/forecast_next_24h.png`, "24-hour forecast chart");
    } catch (error) {
      console.error("Forecast chart send failed:", error);
    }
  }
  return jsonResponse({ ok: true });
};

export const config: Config = {
  path: "/telegram-webhook",
};

class DashboardError extends Error {}

class Dashboard {
  constructor(private readonly root: string) {}

  async handle(message: TelegramMessage): Promise<string | null> {
    const text = message.text;
    if (!text || !text.trim().startsWith("/")) {
      return null;
    }

    const command = commandName(text);
    const timeContext = resolveTimeContext(message);
    try {
      switch (command) {
        case "/start":
          return this.start();
        case "/help":
          return this.help();
        case "/summary":
          return await this.summary(timeContext);
        case "/forecast":
          return await this.forecast(timeContext);
        case "/status":
          return await this.status(timeContext);
        case "/besttime":
          return await this.besttime(timeContext);
        case "/timezone":
          return this.timezone(timeContext);
        case "/model":
          return await this.model();
        case "/compare":
          return await this.compare();
        case "/backtest":
          return await this.backtest();
        case "/quality":
          return await this.quality(timeContext);
        case "/charts":
          return await this.charts();
        default:
          return "Unknown command. Use /help to see available dashboard commands.";
      }
    } catch (error) {
      if (error instanceof DashboardError) {
        return `Dashboard data is not available yet: ${error.message}`;
      }
      console.error("Unexpected dashboard error:", error);
      return "Unexpected dashboard error. Check the Netlify function logs.";
    }
  }

  start(): string {
    return [
      "TON Fee Forecast Bot",
      "",
      "I estimate the next 24 hours of TON transaction fees using recent on-chain activity.",
      "",
      commandList(),
    ].join("\n");
  }

  help(): string {
    return [
      "TON Fee Forecast Bot",
      "",
      "I estimate the next 24 hours of TON transaction fees using recent on-chain activity.",
      "",
      commandList(),
    ].join("\n");
  }

  async summary(timeContext: TimeContext): Promise<string> {
    const metadata = await this.metadata();
    const hourly = await readCsvOverview(this.path("hourly_features.csv"));
    const predictions = await readCsvOverview(this.path("predictions.csv"));
    const metrics = await readJsonOptional(this.path("models/model_metrics.json"));

    return [
      "Project Summary",
      "",
      "What it does: predicts the next-hour average TON transaction fee from hourly on-chain features.",
      timeContextNote(timeContext),
      `Raw rows: ${formatCount(metadata.final_rows)}`,
      `Hourly feature rows: ${formatCount(hourly.rows)}`,
      `Feature date range: ${formatTimestamp(hourly.first.hour, timeContext)} to ${formatTimestamp(hourly.last.hour, timeContext)}`,
      `Latest raw transaction timestamp: ${formatTimestamp(metadata.latest_iso_utc, timeContext)}`,
      `Latest feature timestamp: ${formatTimestamp(hourly.last.hour, timeContext)}`,
      `Best model: ${stringValue(metrics.best_model_name)}`,
      `Holdout R2: ${formatMetric(metrics.best_r2)}`,
      `Holdout MAE: ${formatNanoton(metrics.best_mae)}`,
      `Forecast rows: ${formatCount(predictions.rows)}`,
      `Forecast range: ${formatTimestamp(predictions.first.forecast_hour, timeContext)} to ${formatTimestamp(predictions.last.forecast_hour, timeContext)}`,
      `Forecast generated at: ${formatTimestamp(predictions.first.forecast_generated_at, timeContext)}`,
      "",
      "Important limitation: some collection windows hit TON Center API page limits, so activity counts are sampled indicators rather than guaranteed full-chain volume.",
    ].join("\n");
  }

  async forecast(timeContext: TimeContext): Promise<string> {
    const rows = sortByNumber(await readCsvRows(this.path("predictions.csv")), "horizon_hours", false);
    if (rows.length === 0) {
      throw new DashboardError("predictions.csv has no forecast rows.");
    }
    const stats = forecastStats(rows);
    const freshness = freshnessStatus(rows[0].forecast_generated_at, rows[rows.length - 1].forecast_hour);
    const topCheapest = stats.rows
      .map((row) => ({ row, fee: toNumber(row.predicted_avg_total_fee) }))
      .filter((item): item is { row: CsvRow; fee: number } => item.fee !== null)
      .sort((left, right) => left.fee - right.fee)
      .slice(0, 3);

    const lines = [
      "TON Fee Forecast",
      "",
      timeContextNote(timeContext),
      `Window: ${formatTimestamp(rows[0].forecast_hour, timeContext)} -> ${formatTimestamp(rows[rows.length - 1].forecast_hour, timeContext)}`,
      `Generated: ${formatTimestamp(rows[0].forecast_generated_at, timeContext)} (${formatAgeHours(rows[0].forecast_generated_at)} old)`,
      `Freshness: ${freshness.label}`,
      "",
      "Cheapest hour",
      `${formatTimestamp(stats.cheapest.row.forecast_hour, timeContext)}`,
      `${compactTon(stats.cheapest.fee)} (${formatNanoton(stats.cheapest.fee)})`,
      "",
      `Forecast range: ${compactTon(stats.cheapest.fee)} - ${compactTon(stats.highest.fee)}`,
      `Peak spread: ${compactTon(stats.difference)} (${stats.percent.toFixed(1)}% below highest hour)`,
      "",
      "Top cheap windows:",
    ];

    topCheapest.forEach((item, index) => {
      lines.push(`${index + 1}. ${formatTimestamp(item.row.forecast_hour, timeContext)} - ${compactTon(item.fee)}`);
    });
    for (const warning of freshness.warnings) {
      lines.push(`Warning: ${warning}`);
    }
    lines.push("", "Chart: see the 24-hour forecast image below.", "Directional estimate, not a guarantee.");
    return lines.join("\n");
  }

  async status(timeContext: TimeContext): Promise<string> {
    const metadata = await this.metadata();
    const hourly = await readCsvOverview(this.path("hourly_features.csv"));
    const predictions = await readCsvOverview(this.path("predictions.csv"));
    const forecastGenerated = predictions.first.forecast_generated_at || stringValue(metadata.forecast_generated_at);
    const forecastEnd = predictions.last.forecast_hour || stringValue(metadata.forecast_end);
    const freshness = freshnessStatus(forecastGenerated, forecastEnd);

    const lines = [
      "Forecast Refresh Status",
      "",
      timeContextNote(timeContext),
      `Automation mode: ${stringValue(metadata.automation_mode) === "n/a" ? "manual/local output" : stringValue(metadata.automation_mode)}`,
      `Last data update finished: ${formatTimestamp(metadata.update_finished_at_utc, timeContext)}`,
      `Forecast generated at: ${formatTimestamp(forecastGenerated, timeContext)}`,
      `Forecast age: ${formatAgeHours(forecastGenerated)}`,
      `Forecast range: ${formatTimestamp(predictions.first.forecast_hour, timeContext)} to ${formatTimestamp(forecastEnd, timeContext)}`,
      `Latest feature hour: ${formatTimestamp(hourly.last.hour, timeContext)}`,
      `Latest raw transaction timestamp: ${formatTimestamp(metadata.latest_iso_utc, timeContext)}`,
      `Recent raw rows collected by automation: ${formatCount(metadata.recent_raw_rows_collected)}`,
      `Known full raw rows: ${formatCount(metadata.final_rows)}`,
      `Freshness: ${freshness.label}`,
      "",
      "Telegram handlers are read-only. Data collection, feature refresh, forecasting, charts, and Netlify redeploys run in the scheduled GitHub Actions pipeline.",
    ];
    for (const warning of freshness.warnings) {
      lines.push(`Warning: ${warning}`);
    }
    return lines.join("\n");
  }

  async besttime(timeContext: TimeContext): Promise<string> {
    const rows = await readCsvRows(this.path("predictions.csv"));
    const stats = forecastStats(rows);

    return [
      "Best Time To Send TON",
      "",
      timeContextNote(timeContext),
      "Best hour",
      `${formatTimestamp(stats.cheapest.row.forecast_hour, timeContext)}`,
      "",
      "Predicted fee",
      `${compactTon(stats.cheapest.fee)}`,
      `${formatNanoton(stats.cheapest.fee)}`,
      "",
      "Savings vs peak hour",
      `${compactTon(stats.difference)} lower`,
      `about ${stats.percent.toFixed(1)}% cheaper`,
      "",
      `Lowest  [${asciiBar(stats.cheapest.fee, stats.highest.fee)}] ${compactTon(stats.cheapest.fee)}`,
      `Highest [${asciiBar(stats.highest.fee, stats.highest.fee)}] ${compactTon(stats.highest.fee)}`,
      "",
      "This is the model's estimated cheapest hour in the next 24 hours. Actual network behavior can change quickly.",
    ].join("\n");
  }

  timezone(timeContext: TimeContext): string {
    return [
      "Timezone Display",
      "",
      timeContextNote(timeContext),
      "",
      "Telegram messages do not include the user's exact device timezone. The bot estimates from Telegram language when possible and falls back to UTC when it cannot infer a reliable timezone.",
      "",
      "Override examples:",
      "/forecast Asia/Seoul",
      "/besttime America/New_York",
      "/status Europe/London",
      "",
      "Use IANA timezone names such as Asia/Seoul, America/Los_Angeles, Europe/Paris, or UTC.",
    ].join("\n");
  }

  async model(): Promise<string> {
    const metrics = await readJson(this.path("models/model_metrics.json"));
    const r2 = toNumber(metrics.best_r2);
    const mae = toNumber(metrics.best_mae);
    const rmse = toNumber(metrics.best_rmse);

    return [
      "Best Model",
      "",
      `Model: ${stringValue(metrics.best_model_name)}`,
      `R2: ${formatMetric(r2)}`,
      `MAE: ${formatNanoton(mae)}`,
      `RMSE: ${formatNanoton(rmse)}`,
      "",
      `R2: the model explains about ${percentFromR2(r2)} of the variation in next-hour average fees. Fee movement remains noisy and difficult to predict when this value is low or negative.`,
      `MAE: on average, the prediction is off by about ${formatNanoton(mae)}. This is usually the most practical error number for reading the dashboard.`,
      `RMSE: ${formatNanoton(rmse)}. RMSE penalizes large misses more than MAE, so it rises when the model has occasional large errors.`,
    ].join("\n");
  }

  async compare(): Promise<string> {
    const rows = sortByNumber(await readCsvRows(this.path("models/model_comparison.csv")), "r2", true);
    if (rows.length === 0) {
      throw new DashboardError("models/model_comparison.csv has no rows.");
    }

    const lines = ["Model Comparison", "", "Top chronological holdout models by R2:", ""];
    rows.slice(0, 6).forEach((row, index) => {
      lines.push(
        `${index + 1}. ${stringValue(row.model_name)} | R2 ${formatMetric(row.r2)} | MAE ${formatNanoton(
          row.mae,
        )} | RMSE ${formatNanoton(row.rmse)}`,
      );
    });
    lines.push(
      "",
      `Selected model: ${stringValue(rows[0].model_name)}. It is selected because it has the best chronological holdout R2 in the saved comparison while keeping MAE/RMSE competitive.`,
      "Interpretation: the nonlinear boosted model performs better than linear alternatives, but the R2 is still modest, so it should be used as a directional forecasting tool.",
    );
    return lines.join("\n");
  }

  async backtest(): Promise<string> {
    const rows = sortByNumber(await readCsvRows(this.path("models/rolling_backtest.csv")), "mean_r2", true);
    if (rows.length === 0) {
      throw new DashboardError("models/rolling_backtest.csv has no rows.");
    }

    const metrics = await readJsonOptional(this.path("models/model_metrics.json"));
    const holdoutR2 = toNumber(metrics.best_r2);
    const rollingR2 = toNumber(rows[0].mean_r2);

    const lines = [
      "Rolling Backtest",
      "",
      `Best model by mean R2: ${stringValue(rows[0].model_name)}`,
      `Mean R2: ${formatMetric(rollingR2)}`,
      `Mean MAE: ${formatNanoton(rows[0].mean_mae)}`,
      `Mean RMSE: ${formatNanoton(rows[0].mean_rmse)}`,
      `Folds: ${formatCount(rows[0].folds)}`,
      "",
      "Top rolling models:",
      "",
    ];

    rows.slice(0, 5).forEach((row, index) => {
      lines.push(
        `${index + 1}. ${stringValue(row.model_name)} | mean R2 ${formatMetric(row.mean_r2)} | mean MAE ${formatNanoton(
          row.mean_mae,
        )}`,
      );
    });

    lines.push(
      "",
      "Why this matters: rolling backtest checks whether the model works across multiple time windows instead of only one train/test split.",
    );
    if (holdoutR2 !== null && rollingR2 !== null && rollingR2 < holdoutR2 / 2) {
      lines.push(
        "Interpretation: rolling R2 is much lower than holdout R2, so performance is not stable across all time periods.",
      );
    } else {
      lines.push(
        "Interpretation: compare rolling metrics with holdout metrics before relying on the forecast; higher consistency across folds means a more reliable signal.",
      );
    }
    return lines.join("\n");
  }

  async quality(timeContext: TimeContext): Promise<string> {
    const metadata = await this.metadata();
    const hourly = await readCsvOverview(this.path("hourly_features.csv"));

    return [
      "Data Quality And Limitations",
      "",
      timeContextNote(timeContext),
      `Raw rows from metadata: ${formatCount(metadata.final_rows)}`,
      `Hourly feature rows: ${formatCount(hourly.rows)}`,
      `Feature range: ${formatTimestamp(hourly.first.hour, timeContext)} to ${formatTimestamp(hourly.last.hour, timeContext)}`,
      `Latest raw transaction timestamp: ${formatTimestamp(metadata.latest_iso_utc, timeContext)}`,
      "Duplicate policy: raw transactions are de-duplicated by hash + lt.",
      `API page-limit hits: ${formatCount(metadata.windows_with_limit_hits)} windows hit the configured page limit.`,
      `Collection page settings: limit=${formatCount(metadata.limit)}, max_pages_per_window=${formatCount(
        metadata.max_pages_per_window,
      )}`,
      "",
      "Interpretation: tx_count and unique_accounts are useful sampled activity features, but they may not represent full-chain transaction volume when page limits are hit.",
      "Forecast reliability: the best model has positive R2, but the value is low. Use the forecast as a directional signal, not a production-grade guarantee.",
    ].join("\n");
  }

  async charts(): Promise<string> {
    let files: string[];
    try {
      files = (await readdir(this.path("docs/figures"))).filter((name) => /\.(svg|png|jpe?g)$/i.test(name)).sort();
    } catch (error) {
      throw new DashboardError(`Missing directory: docs/figures (${String(error)})`);
    }

    if (files.length === 0) {
      return "No generated chart files were found in docs/figures/.";
    }

    const lines = ["Generated Charts", "", "Available chart files:", ""];
    for (const file of files) {
      lines.push(`- ${file}: ${chartDescription(file)}`);
    }
    lines.push(
      "",
      "`/forecast` sends the Telegram-ready PNG chart directly. Other generated chart files are listed here for project diagnostics.",
    );
    return lines.join("\n");
  }

  private async metadata(): Promise<JsonObject> {
    try {
      return await readJson(this.path("last_updated.json"));
    } catch {
      return await readJson(this.path("collection_metadata.json"));
    }
  }

  private path(relativePath: string): string {
    return join(this.root, relativePath);
  }
}

async function findProjectRoot(): Promise<string> {
  const currentFileDir = dirname(fileURLToPath(import.meta.url));
  const candidates = [
    process.cwd(),
    resolve(currentFileDir, "../../.."),
    resolve(currentFileDir, "../.."),
    currentFileDir,
  ];

  for (const candidate of candidates) {
    try {
      await readFile(join(candidate, "predictions.csv"), "utf8");
      return candidate;
    } catch {
      // Try the next candidate.
    }
  }
  return process.cwd();
}

async function readJson(path: string): Promise<JsonObject> {
  try {
    return JSON.parse(await readFile(path, "utf8")) as JsonObject;
  } catch (error) {
    throw new DashboardError(`Could not read JSON file ${shortPath(path)}: ${String(error)}`);
  }
}

async function readJsonOptional(path: string): Promise<JsonObject> {
  try {
    return await readJson(path);
  } catch {
    return {};
  }
}

async function readCsvRows(path: string): Promise<CsvRow[]> {
  let text: string;
  try {
    text = await readFile(path, "utf8");
  } catch (error) {
    throw new DashboardError(`Missing CSV file ${shortPath(path)}: ${String(error)}`);
  }

  const rows = parseCsv(text);
  if (rows.length < 1) {
    return [];
  }
  const headers = rows[0];
  return rows.slice(1).map((values) => {
    const row: CsvRow = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });
    return row;
  });
}

async function readCsvOverview(path: string): Promise<{ rows: number; first: CsvRow; last: CsvRow }> {
  const rows = await readCsvRows(path);
  return {
    rows: rows.length,
    first: rows[0] ?? {},
    last: rows[rows.length - 1] ?? {},
  };
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (quoted) {
      if (char === "\"" && next === "\"") {
        field += "\"";
        index += 1;
      } else if (char === "\"") {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }

    if (char === "\"") {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }

  if (field || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

async function sendTelegramMessage(token: string, chatId: number | string, text: string): Promise<void> {
  for (const chunk of splitMessage(text)) {
    const payload = new URLSearchParams({
      chat_id: String(chatId),
      text: chunk,
      disable_web_page_preview: "true",
    });
    const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      body: payload,
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Telegram sendMessage failed with HTTP ${response.status}: ${body.slice(0, 300)}`);
    }
  }
}

async function sendTelegramPhoto(token: string, chatId: number | string, photoUrl: string, caption?: string): Promise<void> {
  const payload = new URLSearchParams({
    chat_id: String(chatId),
    photo: photoUrl,
  });
  if (caption) {
    payload.set("caption", caption);
  }
  const response = await fetch(`https://api.telegram.org/bot${token}/sendPhoto`, {
    method: "POST",
    body: payload,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Telegram sendPhoto failed with HTTP ${response.status}: ${body.slice(0, 300)}`);
  }
}

function splitMessage(text: string): string[] {
  const maxLength = 3900;
  if (text.length <= maxLength) {
    return [text];
  }

  const chunks: string[] = [];
  let current = "";
  for (const line of text.split("\n")) {
    const next = current ? `${current}\n${line}` : line;
    if (next.length > maxLength && current) {
      chunks.push(current);
      current = line;
    } else {
      current = next;
    }
  }
  if (current) {
    chunks.push(current);
  }
  return chunks;
}

function commandList(): string {
  return [
    "Commands:",
    "/forecast - Next 24-hour predicted average transaction fees",
    "/besttime - Estimated cheapest hour to send a transaction",
    "/timezone - Show timezone detection and override examples",
    "",
    "Times are shown in the detected Telegram language timezone when possible.",
    "You can override it by adding an IANA timezone, for example: /forecast Asia/Seoul",
    "",
    "Forecasts are directional estimates, not guarantees.",
  ].join("\n");
}

function commandName(text: string): string {
  return text.trim().split(/\s+/, 1)[0].toLowerCase().split("@", 1)[0];
}

function resolveTimeContext(message: TelegramMessage): TimeContext {
  const override = timezoneFromCommand(message.text);
  if (override) {
    return override;
  }

  const language = message.from?.language_code;
  if (language) {
    const normalized = language.trim().toLowerCase().replace("_", "-");
    const timezone = LANGUAGE_TIMEZONE_MAP[normalized] ?? LANGUAGE_TIMEZONE_MAP[normalized.split("-", 1)[0]];
    if (timezone && isValidTimeZone(timezone)) {
      return { timezone, source: `Telegram language ${language}` };
    }
  }

  return { timezone: "UTC", source: "fallback" };
}

function timezoneFromCommand(text: string | undefined): TimeContext | null {
  if (!text) {
    return null;
  }
  const parts = text.trim().split(/\s+/, 2);
  if (parts.length < 2) {
    return null;
  }
  const aliases: Record<string, string> = {
    UTC: "UTC",
    GMT: "UTC",
    KST: "Asia/Seoul",
    JST: "Asia/Tokyo",
    EST: "America/New_York",
    EDT: "America/New_York",
    CST: "America/Chicago",
    CDT: "America/Chicago",
    MST: "America/Denver",
    MDT: "America/Denver",
    PST: "America/Los_Angeles",
    PDT: "America/Los_Angeles",
  };
  const requested = parts[1].trim();
  const timezone = aliases[requested.toUpperCase()] ?? requested;
  return isValidTimeZone(timezone) ? { timezone, source: "command override" } : null;
}

function isValidTimeZone(timezone: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: timezone }).format(new Date());
    return true;
  } catch {
    return false;
  }
}

function timeContextNote(timeContext: TimeContext): string {
  if (timeContext.source === "fallback") {
    return "Time zone: UTC fallback. Telegram does not expose a user's exact timezone; add an IANA timezone to override, e.g. /forecast Asia/Seoul.";
  }
  return `Time zone: ${timeContext.timezone} (${timeContext.source}).`;
}

function sortByNumber(rows: CsvRow[], column: string, reverse: boolean): CsvRow[] {
  return [...rows].sort((left, right) => {
    const leftValue = toNumber(left[column]);
    const rightValue = toNumber(right[column]);
    const leftRank = leftValue ?? (reverse ? Number.NEGATIVE_INFINITY : Number.POSITIVE_INFINITY);
    const rightRank = rightValue ?? (reverse ? Number.NEGATIVE_INFINITY : Number.POSITIVE_INFINITY);
    return reverse ? rightRank - leftRank : leftRank - rightRank;
  });
}

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function toInteger(value: unknown): number | null {
  const numeric = toNumber(value);
  return numeric === null ? null : Math.trunc(numeric);
}

function forecastStats(rows: CsvRow[]): ForecastStats {
  const sortedRows = sortByNumber(rows, "horizon_hours", false);
  const numericRows = sortedRows
    .map((row) => ({ row, fee: toNumber(row.predicted_avg_total_fee) }))
    .filter((item): item is { row: CsvRow; fee: number } => item.fee !== null);

  if (numericRows.length === 0) {
    throw new DashboardError("predictions.csv does not contain numeric predicted_avg_total_fee values.");
  }

  const cheapest = numericRows.reduce((best, item) => (item.fee < best.fee ? item : best));
  const highest = numericRows.reduce((best, item) => (item.fee > best.fee ? item : best));
  const difference = highest.fee - cheapest.fee;
  const percent = highest.fee ? (difference / highest.fee) * 100 : 0;
  return { rows: sortedRows, cheapest, highest, difference, percent };
}

function formatCount(value: unknown): string {
  const numeric = toInteger(value);
  return numeric === null ? "n/a" : numeric.toLocaleString("en-US");
}

function formatMetric(value: unknown, digits = 4): string {
  const numeric = toNumber(value);
  return numeric === null ? "n/a" : numeric.toFixed(digits);
}

function formatNanoton(value: unknown): string {
  const numeric = toNumber(value);
  return numeric === null ? "n/a" : `${numeric.toLocaleString("en-US", { maximumFractionDigits: 0 })} nanoton`;
}

function formatTon(value: unknown): string {
  const numeric = toNumber(value);
  return numeric === null ? "n/a" : `${numeric.toFixed(9)} TON`;
}

function nanotonToTon(value: unknown): number | null {
  const numeric = toNumber(value);
  return numeric === null ? null : numeric / 1_000_000_000;
}

function compactTon(value: unknown): string {
  const numeric = nanotonToTon(value);
  return numeric === null ? "n/a" : `${numeric.toFixed(6)} TON`;
}

function asciiBar(value: number, maxValue: number, width = 12): string {
  if (maxValue <= 0) {
    return ".".repeat(width);
  }
  const filled = Math.max(1, Math.min(width, Math.round((value / maxValue) * width)));
  return `${"#".repeat(filled)}${".".repeat(width - filled)}`;
}

function percentFromR2(value: unknown): string {
  const numeric = toNumber(value);
  return numeric === null ? "n/a" : `${(numeric * 100).toFixed(1)}%`;
}

function parseTimestamp(value: unknown): Date | null {
  const text = stringValue(value);
  if (text === "n/a") {
    return null;
  }
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatAgeHours(value: unknown): string {
  const timestamp = parseTimestamp(value);
  if (!timestamp) {
    return "n/a";
  }
  const hours = Math.max(0, (Date.now() - timestamp.getTime()) / 3_600_000);
  return `${hours.toFixed(1)} hours`;
}

function freshnessStatus(generatedAt: unknown, forecastEnd: unknown): { label: string; warnings: string[] } {
  const warnings: string[] = [];
  const generated = parseTimestamp(generatedAt);
  const end = parseTimestamp(forecastEnd);
  const now = Date.now();

  if (!generated) {
    warnings.push("Forecast generated timestamp is missing.");
  } else {
    const ageHours = (now - generated.getTime()) / 3_600_000;
    if (ageHours > FORECAST_STALE_HOURS) {
      warnings.push(`Forecast is older than ${FORECAST_STALE_HOURS} hours. Treat it as stale until automation refreshes it.`);
    }
  }

  if (end && end.getTime() < now) {
    warnings.push("Forecast window has already ended. Treat this output as stale.");
  }

  return {
    label: warnings.length > 0 ? "STALE / check automation" : "Fresh enough for directional use",
    warnings,
  };
}

function formatTimestamp(value: unknown, timeContext: TimeContext = { timezone: "UTC", source: "fallback" }): string {
  const text = stringValue(value);
  if (text === "n/a") {
    return text;
  }
  const timestamp = parseTimestamp(value);
  if (!timestamp) {
    return text.endsWith("+00:00") ? `${text.slice(0, -6)}Z` : text;
  }
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timeContext.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZoneName: "short",
  })
    .format(timestamp)
    .replace(",", "");
}

function formatHour(value: unknown, timeContext: TimeContext): string {
  return formatTimestamp(value, timeContext);
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return String(value);
}

function chartDescription(file: string): string {
  const descriptions: Record<string, string> = {
    "hourly_fee_trend.svg": "Hourly average fee trend across the collected feature window.",
    "fee_distribution.svg": "Distribution of observed transaction fees.",
    "network_activity_trend.svg": "Sampled transaction and account activity by hour.",
    "model_r2_comparison.svg": "Chronological holdout R2 comparison by model.",
    "rolling_backtest_r2_comparison.svg": "Rolling backtest mean R2 comparison by model.",
    "model_mae_comparison.svg": "Chronological holdout MAE comparison by model.",
    "actual_vs_predicted.svg": "Holdout actual next-hour fees versus model predictions.",
    "forecast_next_24h.svg": "Recent actual fees with the generated 24-hour forecast.",
    "forecast_next_24h.png": "Telegram-ready next 24-hour forecast chart.",
  };
  return descriptions[file] ?? "Generated project chart.";
}

function jsonResponse(payload: JsonObject): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "content-type": "application/json" },
  });
}

function shortPath(path: string): string {
  const marker = "ton_fee_prediction/";
  const index = path.indexOf(marker);
  return index >= 0 ? path.slice(index + marker.length) : path;
}

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
  text?: string;
};
type TelegramUpdate = {
  message?: TelegramMessage;
};

export default async (req: Request, context: Context) => {
  if (req.method === "GET") {
    return jsonResponse({
      status: "ok",
      service: "TON fee prediction Telegram webhook",
      commands: [
        "/start",
        "/help",
        "/summary",
        "/forecast",
        "/besttime",
        "/model",
        "/compare",
        "/backtest",
        "/quality",
        "/charts",
      ],
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
    try {
      switch (command) {
        case "/start":
          return this.start();
        case "/help":
          return this.help();
        case "/summary":
          return await this.summary();
        case "/forecast":
          return await this.forecast();
        case "/besttime":
          return await this.besttime();
        case "/model":
          return await this.model();
        case "/compare":
          return await this.compare();
        case "/backtest":
          return await this.backtest();
        case "/quality":
          return await this.quality();
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
      "TON Fee Prediction Dashboard",
      "",
      "This project predicts the next-hour average TON transaction fee from recent TON on-chain transaction data collected through the TON Center API.",
      "",
      "The bot shows saved project outputs only. It does not retrain models inside Telegram handlers.",
      "",
      commandList(),
    ].join("\n");
  }

  help(): string {
    return [
      "TON Fee Prediction Dashboard",
      "",
      "This bot explains the TON transaction fee prediction project and shows the latest saved results.",
      "It is read-only: it reads existing CSV/JSON/SVG outputs and does not retrain models or modify data.",
      "",
      commandList(),
    ].join("\n");
  }

  async summary(): Promise<string> {
    const metadata = await this.metadata();
    const hourly = await readCsvOverview(this.path("hourly_features.csv"));
    const predictions = await readCsvOverview(this.path("predictions.csv"));
    const metrics = await readJsonOptional(this.path("models/model_metrics.json"));

    return [
      "Project Summary",
      "",
      "What it does: predicts the next-hour average TON transaction fee from hourly on-chain features.",
      `Raw rows: ${formatCount(metadata.final_rows)}`,
      `Hourly feature rows: ${formatCount(hourly.rows)}`,
      `Feature date range: ${formatTimestamp(hourly.first.hour)} to ${formatTimestamp(hourly.last.hour)}`,
      `Latest raw transaction timestamp: ${formatTimestamp(metadata.latest_iso_utc)}`,
      `Latest feature timestamp: ${formatTimestamp(hourly.last.hour)}`,
      `Best model: ${stringValue(metrics.best_model_name)}`,
      `Holdout R2: ${formatMetric(metrics.best_r2)}`,
      `Holdout MAE: ${formatNanoton(metrics.best_mae)}`,
      `Forecast rows: ${formatCount(predictions.rows)}`,
      `Forecast range: ${formatTimestamp(predictions.first.forecast_hour)} to ${formatTimestamp(predictions.last.forecast_hour)}`,
      `Forecast generated at: ${formatTimestamp(predictions.first.forecast_generated_at)}`,
      "",
      "Important limitation: some collection windows hit TON Center API page limits, so activity counts are sampled indicators rather than guaranteed full-chain volume.",
    ].join("\n");
  }

  async forecast(): Promise<string> {
    const rows = sortByNumber(await readCsvRows(this.path("predictions.csv")), "horizon_hours", false);
    if (rows.length === 0) {
      throw new DashboardError("predictions.csv has no forecast rows.");
    }

    const lines = [
      "Next 24-Hour Fee Forecast",
      "",
      `Generated at: ${formatTimestamp(rows[0].forecast_generated_at)}`,
      `Model: ${stringValue(rows[0].model_name)}`,
      "",
      "Each row is the predicted average transaction fee for that UTC hour.",
      "",
    ];

    for (const row of rows.slice(0, 24)) {
      const predictedNanoton = toNumber(row.predicted_avg_total_fee);
      const predictedTon = toNumber(row.predicted_avg_total_fee_ton) ?? nanotonToTon(predictedNanoton);
      lines.push(
        `h${String(toInteger(row.horizon_hours) ?? 0).padStart(2, "0")} ${formatHour(row.forecast_hour)} | ${formatNanoton(
          predictedNanoton,
        )} | ${formatTon(predictedTon)}`,
      );
    }

    lines.push(
      "",
      "Interpretation: use this as a directional guide. Actual TON fees can move quickly when network behavior changes.",
    );
    return lines.join("\n");
  }

  async besttime(): Promise<string> {
    const rows = await readCsvRows(this.path("predictions.csv"));
    const numericRows = rows
      .map((row) => ({ row, fee: toNumber(row.predicted_avg_total_fee) }))
      .filter((item): item is { row: CsvRow; fee: number } => item.fee !== null);

    if (numericRows.length === 0) {
      throw new DashboardError("predictions.csv does not contain numeric predicted_avg_total_fee values.");
    }

    const cheapest = numericRows.reduce((best, item) => (item.fee < best.fee ? item : best));
    const highest = numericRows.reduce((best, item) => (item.fee > best.fee ? item : best));
    const difference = highest.fee - cheapest.fee;
    const percent = highest.fee ? (difference / highest.fee) * 100 : 0;

    return [
      "Best Predicted Time Window",
      "",
      `Cheapest predicted hour: ${formatTimestamp(cheapest.row.forecast_hour)}`,
      `Predicted average fee: ${formatNanoton(cheapest.fee)} (${formatTon(nanotonToTon(cheapest.fee))})`,
      `Highest predicted hour in window: ${formatTimestamp(highest.row.forecast_hour)}`,
      `Difference vs highest predicted fee: ${formatNanoton(difference)} (${formatTon(nanotonToTon(difference))}, about ${percent.toFixed(
        1,
      )}% lower)`,
      "",
      "This is the model's estimated cheapest hour, but the model should be treated as a directional guide, not a guarantee. Actual network behavior can change quickly.",
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
      `Baseline linear R2: ${formatMetric(metrics.baseline_r2)}`,
      `R2 improvement vs baseline: ${formatMetric(metrics.r2_improvement)}`,
      "",
      `R2: the model explains about ${percentFromR2(r2)} of the variation in next-hour average fees. That is better than the baseline here, but still low, so fee movement remains noisy and difficult to predict.`,
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
      `Selected model: ${stringValue(rows[0].model_name)}. It is selected because it has the best chronological holdout R2 in the saved comparison while keeping MAE/RMSE slightly better than the baseline linear model.`,
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
        "Interpretation: rolling R2 is much lower than holdout R2. The model improves over baseline, but performance is not stable across all time periods.",
      );
    } else {
      lines.push(
        "Interpretation: compare rolling metrics with holdout metrics before relying on the forecast; higher consistency across folds means a more reliable signal.",
      );
    }
    return lines.join("\n");
  }

  async quality(): Promise<string> {
    const metadata = await this.metadata();
    const hourly = await readCsvOverview(this.path("hourly_features.csv"));

    return [
      "Data Quality And Limitations",
      "",
      `Raw rows from metadata: ${formatCount(metadata.final_rows)}`,
      `Hourly feature rows: ${formatCount(hourly.rows)}`,
      `Feature range: ${formatTimestamp(hourly.first.hour)} to ${formatTimestamp(hourly.last.hour)}`,
      `Latest raw transaction timestamp: ${formatTimestamp(metadata.latest_iso_utc)}`,
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
      "Current project charts are SVG files. This Netlify webhook lists them instead of sending files because Telegram does not reliably render SVG as chart previews without a conversion dependency.",
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
    "/start - Introduce the project and list commands",
    "/help - Show this help message",
    "/summary - Project status, data size, model, and forecast availability",
    "/forecast - Next 24-hour predicted average transaction fees",
    "/besttime - Predicted cheapest hour in the forecast window",
    "/model - Best model metrics and plain-language interpretation",
    "/compare - Top chronological holdout model results",
    "/backtest - Rolling backtest summary",
    "/quality - Data quality notes and limitations",
    "/charts - Available generated chart files and what they show",
  ].join("\n");
}

function commandName(text: string): string {
  return text.trim().split(/\s+/, 1)[0].toLowerCase().split("@", 1)[0];
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

function percentFromR2(value: unknown): string {
  const numeric = toNumber(value);
  return numeric === null ? "n/a" : `${(numeric * 100).toFixed(1)}%`;
}

function formatTimestamp(value: unknown): string {
  const text = stringValue(value);
  if (text === "n/a") {
    return text;
  }
  return text.endsWith("+00:00") ? `${text.slice(0, -6)}Z` : text;
}

function formatHour(value: unknown): string {
  const text = stringValue(value);
  if (text === "n/a") {
    return text;
  }
  const cleaned = text.replace("T", " ");
  if (cleaned.endsWith(":00Z")) {
    return `${cleaned.slice(0, -4)} UTC`;
  }
  return cleaned.endsWith("Z") ? `${cleaned.slice(0, -1)} UTC` : cleaned;
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

import { beforeEach, describe, expect, it, vi } from "vitest";
import { onRequestGet, onRequestPost } from "../../functions/telegram-webhook.js";

function isoHoursFromNow(hours: number): string {
  return new Date(Date.now() + hours * 3_600_000).toISOString().replace(".000", "");
}

const generatedAt = isoHoursFromNow(-1);
const predictionsCsv = [
  "forecast_generated_at,forecast_hour,horizon_hours,predicted_avg_total_fee,predicted_avg_total_fee_ton,model_name,model_trained_at_utc",
  `${generatedAt},${isoHoursFromNow(1)},1,1000000,0.001,best,${generatedAt}`,
  `${generatedAt},${isoHoursFromNow(2)},2,2000000,0.002,best,${generatedAt}`,
  `${generatedAt},${isoHoursFromNow(3)},3,1500000,0.0015,best,${generatedAt}`,
].join("\n");

const env = {
  TELEGRAM_BOT_TOKEN: "test-token",
  TELEGRAM_WEBHOOK_SECRET: "test-secret",
};

function operationalMetrics(status = "active") {
  return {
    generated_at_utc: generatedAt,
    status,
    reconciled_rows: status === "active" ? 12 : 0,
    pending_rows: status === "active" ? 3 : 24,
    overall: {
      n: status === "active" ? 12 : 0,
      mae: status === "active" ? 1000 : null,
      rmse: status === "active" ? 1200 : null,
      mape: status === "active" ? 10 : null,
      r2: null,
      directional_accuracy: status === "active" ? 0.75 : null,
      persistence_mae: status === "active" ? 1500 : null,
      skill_score: status === "active" ? 0.3333 : null,
    },
    by_horizon: {
      "1": {
        n: status === "active" ? 12 : 0,
        mae: status === "active" ? 1000 : null,
        rmse: status === "active" ? 1200 : null,
        mape: status === "active" ? 10 : null,
        r2: null,
        directional_accuracy: status === "active" ? 0.75 : null,
        persistence_mae: status === "active" ? 1500 : null,
        skill_score: status === "active" ? 0.3333 : null,
      },
    },
    by_capped: { clean: { n: 0 }, capped: { n: 0 } },
  };
}

function contextFor(text: string, chatId: number, secret = "test-secret") {
  const headers = new Headers({ "content-type": "application/json" });
  if (secret) {
    headers.set("x-telegram-bot-api-secret-token", secret);
  }
  return {
    request: new Request("https://example.com/telegram-webhook", {
      method: "POST",
      headers,
      body: JSON.stringify({ message: { chat: { id: chatId }, from: { language_code: "en" }, text } }),
    }),
    env,
  } as never;
}

function installFetchMock(sentTexts: string[], metrics = operationalMetrics()) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("api.telegram.org") && url.includes("sendMessage")) {
        const body = init?.body as URLSearchParams;
        sentTexts.push(body.get("text") ?? "");
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      if (url.includes("api.telegram.org") && url.includes("sendPhoto")) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      if (url.endsWith("/data/predictions.csv")) {
        return new Response(predictionsCsv, { status: 200 });
      }
      if (url.endsWith("/data/models/operational_metrics.json")) {
        return new Response(JSON.stringify(metrics), { status: 200 });
      }
      if (url.endsWith("/figures/forecast_next_24h.png")) {
        return new Response(new Blob(["png"], { type: "image/png" }), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    }),
  );
}

describe("Cloudflare Telegram webhook", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns status for GET", async () => {
    const response = await onRequestGet({ request: new Request("https://example.com/telegram-webhook"), env } as never);
    expect(response.status).toBe(200);
    expect(await response.json()).toHaveProperty("service");
  });

  it("rejects POST without secret header", async () => {
    installFetchMock([]);
    const response = await onRequestPost(contextFor("/forecast", 10, ""));
    expect(response.status).toBe(403);
  });

  it("handles /forecast with a valid secret", async () => {
    const sentTexts: string[] = [];
    installFetchMock(sentTexts);
    const response = await onRequestPost(contextFor("/forecast", 11));
    expect(response.status).toBe(200);
    expect(sentTexts.join("\n")).toContain("TON Fee Forecast");
  });

  it("uses the requested timezone for /forecast", async () => {
    const sentTexts: string[] = [];
    installFetchMock(sentTexts);
    const response = await onRequestPost(contextFor("/forecast Asia/Seoul", 12));
    expect(response.status).toBe(200);
    expect(sentTexts.join("\n")).toMatch(/Asia\/Seoul|KST/);
  });

  it("reports unknown commands", async () => {
    const sentTexts: string[] = [];
    installFetchMock(sentTexts);
    const response = await onRequestPost(contextFor("/unknown", 13));
    expect(response.status).toBe(200);
    expect(sentTexts.join("\n")).toContain("Unknown command");
  });

  it("handles /accuracy with live metrics", async () => {
    const sentTexts: string[] = [];
    installFetchMock(sentTexts);
    const response = await onRequestPost(contextFor("/accuracy", 15));
    expect(response.status).toBe(200);
    expect(sentTexts.join("\n")).toContain("Operational (live) Accuracy");
    expect(sentTexts.join("\n")).toContain("Status: active");
  });

  it("shows accumulating status for /accuracy", async () => {
    const sentTexts: string[] = [];
    installFetchMock(sentTexts, operationalMetrics("accumulating"));
    const response = await onRequestPost(contextFor("/accuracy", 16));
    expect(response.status).toBe(200);
    expect(sentTexts.join("\n")).toContain("아직 누적 중");
  });

  it("rate limits repeated chat ids", async () => {
    const sentTexts: string[] = [];
    installFetchMock(sentTexts);
    await onRequestPost(contextFor("/unknown", 14));
    const response = await onRequestPost(contextFor("/unknown", 14));
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ ignored: "rate_limited" });
  });
});

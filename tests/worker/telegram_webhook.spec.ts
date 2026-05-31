import { beforeEach, describe, expect, it, vi } from "vitest";
import { onRequestGet, onRequestPost } from "../../functions/telegram-webhook.js";

const predictionsCsv = [
  "forecast_generated_at,forecast_hour,horizon_hours,predicted_avg_total_fee,predicted_avg_total_fee_ton,model_name,model_trained_at_utc",
  "2026-05-31T05:00:00Z,2026-05-31T06:00:00Z,1,1000000,0.001,best,2026-05-31T04:00:00Z",
  "2026-05-31T05:00:00Z,2026-05-31T07:00:00Z,2,2000000,0.002,best,2026-05-31T04:00:00Z",
  "2026-05-31T05:00:00Z,2026-05-31T08:00:00Z,3,1500000,0.0015,best,2026-05-31T04:00:00Z",
].join("\n");

const env = {
  TELEGRAM_BOT_TOKEN: "test-token",
  TELEGRAM_WEBHOOK_SECRET: "test-secret",
};

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

function installFetchMock(sentTexts: string[]) {
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

  it("rate limits repeated chat ids", async () => {
    const sentTexts: string[] = [];
    installFetchMock(sentTexts);
    await onRequestPost(contextFor("/unknown", 14));
    const response = await onRequestPost(contextFor("/unknown", 14));
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ ignored: "rate_limited" });
  });
});

// Cloudflare Pages Function — relays app/index.html's AI-extraction calls to
// Bayer's AI Gateway (TrueFoundry) using Entra ID client-credentials (M2M).
// The browser never sees AZURE_CLIENT_SECRET; token acquisition is server-side.
//
// Required Cloudflare Pages secrets (Production environment — never commit):
//   AZURE_CLIENT_SECRET  Entra client secret for "Use Summary Table Extractor"
//   PILOT_GATE_SECRET    must equal PILOT_GATE_HEADER_VALUE in app/index.html
//
// Optional (defaults baked in for prod Entra resource + documented Gateway host):
//   AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_SCOPE, TFY_BASE_URL
//
// Env var changes only apply to deployments built after they were saved —
// trigger a fresh deployment any time these are added or changed.
//
// A kill switch, rate limiting, a daily cost budget, audit logging, and a
// content-safety flag are handled by _lib/governance.js (requires the
// AUDIT_LOG KV binding — see wrangler.toml).

import {
  checkKillSwitch,
  checkRateLimit,
  checkBudget,
  recordUsage,
  recordAudit,
  scanForInjectionPhrases,
  estimateCostUsd
} from "./_lib/governance.js";
import { getGatewayAccessToken, gatewayConfig } from "./_lib/entra.js";

const MAX_BODY_BYTES = 2 * 1024 * 1024;

export async function onRequestPost(context) {
  const { request, env } = context;
  const startedAt = Date.now();

  const gate = request.headers.get("x-ust-pilot");
  if (!env.PILOT_GATE_SECRET || gate !== env.PILOT_GATE_SECRET) {
    return new Response(JSON.stringify({ error: { message: "Unauthorized" } }), {
      status: 401,
      headers: { "content-type": "application/json" }
    });
  }

  const killSwitch = await checkKillSwitch(env);
  if (killSwitch.enabled) {
    await recordAudit(env, { source: "extract", status: "blocked_killswitch", durationMs: Date.now() - startedAt });
    return new Response(JSON.stringify({ error: { message: killSwitch.reason } }), {
      status: 503,
      headers: { "content-type": "application/json" }
    });
  }

  const rateLimit = await checkRateLimit(env, "extract");
  if (!rateLimit.allowed) {
    await recordAudit(env, { source: "extract", status: "blocked_rate_limit", durationMs: Date.now() - startedAt });
    return new Response(JSON.stringify({
      error: { message: `Rate limit exceeded (${rateLimit.limit}/min) — wait a moment and retry.` }
    }), {
      status: 429,
      headers: { "content-type": "application/json" }
    });
  }

  const budget = await checkBudget(env);
  if (!budget.allowed) {
    await recordAudit(env, { source: "extract", status: "blocked_budget", durationMs: Date.now() - startedAt });
    return new Response(JSON.stringify({
      error: { message: `Daily AI budget exceeded ($${budget.limitUsd}) — try again tomorrow, or ask whoever manages the pilot to raise DAILY_BUDGET_USD.` }
    }), {
      status: 429,
      headers: { "content-type": "application/json" }
    });
  }

  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > MAX_BODY_BYTES) {
    return new Response(JSON.stringify({ error: { message: "Request body too large" } }), {
      status: 413,
      headers: { "content-type": "application/json" }
    });
  }

  const bodyText = await request.text();
  if (bodyText.length > MAX_BODY_BYTES) {
    return new Response(JSON.stringify({ error: { message: "Request body too large" } }), {
      status: 413,
      headers: { "content-type": "application/json" }
    });
  }

  const flags = scanForInjectionPhrases(bodyText);

  // Best-effort — only used to price this call at the right model's rate;
  // a parse failure just falls back to estimateCostUsd's default (Sonnet).
  let model;
  try {
    model = JSON.parse(bodyText)?.model;
  } catch (_) {
    /* not our concern here — the upstream request below will fail loudly if bodyText isn't valid JSON */
  }

  let accessToken;
  try {
    accessToken = await getGatewayAccessToken(env);
  } catch (err) {
    await recordAudit(env, {
      source: "extract",
      status: "error",
      durationMs: Date.now() - startedAt,
      flags: flags.length ? flags : undefined
    });
    return new Response(JSON.stringify({ error: { message: err.message } }), {
      status: 502,
      headers: { "content-type": "application/json" }
    });
  }

  const { messagesUrl } = gatewayConfig(env);
  let upstreamResponse;
  try {
    upstreamResponse = await fetch(messagesUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "authorization": `Bearer ${accessToken}`,
        "anthropic-version": "2023-06-01"
      },
      body: bodyText
    });
  } catch (err) {
    await recordAudit(env, {
      source: "extract",
      status: "error",
      durationMs: Date.now() - startedAt,
      flags: flags.length ? flags : undefined
    });
    return new Response(JSON.stringify({ error: { message: `Could not reach AI Gateway: ${err.message}` } }), {
      status: 502,
      headers: { "content-type": "application/json" }
    });
  }

  const upstreamBody = await upstreamResponse.text();

  // Log usage/audit off a parsed clone of the same text we return below —
  // a parse or logging failure here must never change what the client gets.
  try {
    const parsed = JSON.parse(upstreamBody);
    const usageRaw = parsed.usage || {};
    // Anthropic uses input_tokens/output_tokens; OpenAI-style gateways may use
    // prompt_tokens/completion_tokens — accept either for budget tracking.
    const inputTokens = usageRaw.input_tokens ?? usageRaw.prompt_tokens ?? 0;
    const outputTokens = usageRaw.output_tokens ?? usageRaw.completion_tokens ?? 0;
    const estCostUsd = (inputTokens || outputTokens)
      ? estimateCostUsd({ inputTokens, outputTokens }, model)
      : 0;
    const usage = (inputTokens || outputTokens)
      ? { inputTokens, outputTokens, estCostUsd }
      : null;
    if (usage) await recordUsage(env, usage);
    await recordAudit(env, {
      source: "extract",
      status: upstreamResponse.ok ? "ok" : "error",
      durationMs: Date.now() - startedAt,
      model,
      inputTokens: usage?.inputTokens,
      outputTokens: usage?.outputTokens,
      estCostUsd: usage ? estCostUsd : undefined,
      flags: flags.length ? flags : undefined
    });
  } catch (err) {
    console.error(`extract.js: could not log usage/audit (response to client is unaffected): ${err.message}`);
  }

  return new Response(upstreamBody, {
    status: upstreamResponse.status,
    headers: { "content-type": "application/json" }
  });
}

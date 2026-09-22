// Cloudflare Pages Function — relays app/index.html's AI-extraction calls to
// Bayer's AI Gateway (TrueFoundry) using Entra ID client-credentials (M2M).
//
// Upstream Anthropic calls use stream:true. The SSE body is piped through to
// the browser so this Function does not buffer a multi-minute generation
// (which was causing Cloudflare/proxy 504s on large labels). Audit/usage is
// recorded best-effort via waitUntil on a tee'd copy of the stream.
//
// Required Cloudflare Pages secrets (Production environment — never commit):
//   AZURE_CLIENT_SECRET  Entra client secret for "Use Summary Table Extractor"
//   PILOT_GATE_SECRET    must equal PILOT_GATE_HEADER_VALUE in app/index.html

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
import { readMessagesStream, withStreamEnabled } from "./_lib/anthropic-stream.js";

const MAX_BODY_BYTES = 2 * 1024 * 1024;

export async function onRequestPost(context) {
  const { request, env, waitUntil } = context;
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

  let model;
  let upstreamBody;
  try {
    const enabled = withStreamEnabled(bodyText);
    model = enabled.parsed?.model;
    upstreamBody = enabled.upstreamBody;
  } catch (_) {
    return new Response(JSON.stringify({ error: { message: "Request body must be valid JSON" } }), {
      status: 400,
      headers: { "content-type": "application/json" }
    });
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
      body: upstreamBody
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

  if (!upstreamResponse.ok) {
    const errText = await upstreamResponse.text();
    try {
      await recordAudit(env, {
        source: "extract",
        status: "error",
        durationMs: Date.now() - startedAt,
        model,
        flags: flags.length ? flags : undefined
      });
    } catch (_) { /* ignore */ }
    return new Response(errText || JSON.stringify({ error: { message: `AI Gateway HTTP ${upstreamResponse.status}` } }), {
      status: upstreamResponse.status,
      headers: { "content-type": "application/json" }
    });
  }

  if (!upstreamResponse.body) {
    return new Response(JSON.stringify({ error: { message: "AI Gateway returned an empty body" } }), {
      status: 502,
      headers: { "content-type": "application/json" }
    });
  }

  const [toClient, toAudit] = upstreamResponse.body.tee();

  const auditTask = (async () => {
    try {
      const assembled = await readMessagesStream(new Response(toAudit));
      const usageRaw = assembled.usage || {};
      const inputTokens = usageRaw.input_tokens ?? 0;
      const outputTokens = usageRaw.output_tokens ?? 0;
      const estCostUsd = (inputTokens || outputTokens)
        ? estimateCostUsd({ inputTokens, outputTokens }, model)
        : 0;
      const usage = (inputTokens || outputTokens)
        ? { inputTokens, outputTokens, estCostUsd }
        : null;
      if (usage) await recordUsage(env, usage);
      await recordAudit(env, {
        source: "extract",
        status: "ok",
        durationMs: Date.now() - startedAt,
        model,
        inputTokens: usage?.inputTokens,
        outputTokens: usage?.outputTokens,
        estCostUsd: usage ? estCostUsd : undefined,
        flags: flags.length ? flags : undefined
      });
    } catch (err) {
      console.error(`extract.js: stream audit failed: ${err.message}`);
      try {
        await recordAudit(env, {
          source: "extract",
          status: "error",
          durationMs: Date.now() - startedAt,
          model,
          flags: flags.length ? flags : undefined
        });
      } catch (_) { /* ignore */ }
    }
  })();

  if (typeof waitUntil === "function") waitUntil(auditTask);

  return new Response(toClient, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache",
      "x-ust-stream": "1"
    }
  });
}

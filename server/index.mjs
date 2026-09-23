// Agentrix Node API — same-origin relay for app/index.html AI extraction.
// Ports Cloudflare Pages Functions (extract + qc-summary) without CF runtime.
// Zero npm dependencies: Node 20+ built-in http + fetch.
//
// Required env:
//   AZURE_CLIENT_SECRET  (or TFY_API_TOKEN fallback)
//   PILOT_GATE_SECRET    must match PILOT_GATE_HEADER_VALUE in app/index.html
// Optional: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_SCOPE, TFY_BASE_URL,
//   RATE_LIMIT_PER_MINUTE, DAILY_BUDGET_USD, AUDIT_TTL_SECONDS,
//   KILL_SWITCH_ENABLED, KILL_SWITCH_REASON, PORT (default 3000)

import http from "node:http";
import { createMemoryStore } from "./lib/memory-store.mjs";
import {
  checkKillSwitch,
  checkRateLimit,
  checkBudget,
  recordUsage,
  recordAudit,
  scanForInjectionPhrases,
  estimateCostUsd
} from "./lib/governance.mjs";
import { getGatewayAccessToken, gatewayConfig } from "./lib/entra.mjs";
import { readMessagesStream, withStreamEnabled } from "./lib/anthropic-stream.mjs";

const PORT = Number(process.env.PORT) || 3000;
const MAX_EXTRACT_BYTES = 2 * 1024 * 1024;
const MAX_QC_BYTES = 8 * 1024;
const KEEPALIVE_MS = 1500;

const env = {
  ...process.env,
  AUDIT_LOG: createMemoryStore()
};

function json(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(payload)
  });
  res.end(payload);
}

function unauthorized(res) {
  json(res, 401, { error: { message: "Unauthorized" } });
}

function checkPilotGate(req) {
  const gate = req.headers["x-ust-pilot"];
  return Boolean(env.PILOT_GATE_SECRET && gate === env.PILOT_GATE_SECRET);
}

async function readBody(req, maxBytes) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > maxBytes) {
      const err = new Error("Request body too large");
      err.statusCode = 413;
      throw err;
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

async function handleFeatures(_req, res) {
  json(res, 200, {
    aiExtract: true,
    backgroundJobs: false,
    runtime: "agentrix"
  });
}

async function handleQcSummary(req, res) {
  if (!checkPilotGate(req)) return unauthorized(res);

  let bodyText;
  try {
    bodyText = await readBody(req, MAX_QC_BYTES);
  } catch (err) {
    return json(res, err.statusCode || 400, { error: { message: err.message } });
  }

  let body;
  try {
    body = JSON.parse(bodyText);
  } catch {
    return json(res, 400, { error: { message: "Body must be JSON" } });
  }

  const { fileName, qcOverall, remediationCycles } = body || {};
  if (typeof fileName !== "string" || !fileName) {
    return json(res, 400, { error: { message: "fileName is required" } });
  }
  if (typeof qcOverall !== "string" || !qcOverall) {
    return json(res, 400, { error: { message: "qcOverall is required" } });
  }

  await recordAudit(env, {
    source: "extract",
    status: "qc_summary",
    fileName,
    qcOverall,
    remediationCycles: Number.isInteger(remediationCycles) ? remediationCycles : 0
  });

  return json(res, 200, { ok: true });
}

async function handleExtract(req, res) {
  const startedAt = Date.now();
  if (!checkPilotGate(req)) return unauthorized(res);

  const killSwitch = await checkKillSwitch(env);
  if (killSwitch.enabled) {
    await recordAudit(env, { source: "extract", status: "blocked_killswitch", durationMs: Date.now() - startedAt });
    return json(res, 503, { error: { message: killSwitch.reason } });
  }

  const rateLimit = await checkRateLimit(env, "extract");
  if (!rateLimit.allowed) {
    await recordAudit(env, { source: "extract", status: "blocked_rate_limit", durationMs: Date.now() - startedAt });
    return json(res, 429, {
      error: { message: `Rate limit exceeded (${rateLimit.limit}/min) — wait a moment and retry.` }
    });
  }

  const budget = await checkBudget(env);
  if (!budget.allowed) {
    await recordAudit(env, { source: "extract", status: "blocked_budget", durationMs: Date.now() - startedAt });
    return json(res, 429, {
      error: {
        message: `Daily AI budget exceeded ($${budget.limitUsd}) — try again tomorrow, or ask whoever manages the pilot to raise DAILY_BUDGET_USD.`
      }
    });
  }

  let bodyText;
  try {
    bodyText = await readBody(req, MAX_EXTRACT_BYTES);
  } catch (err) {
    return json(res, err.statusCode || 400, { error: { message: err.message } });
  }

  const flags = scanForInjectionPhrases(bodyText);

  let model;
  let upstreamBody;
  try {
    const enabled = withStreamEnabled(bodyText);
    model = enabled.parsed?.model;
    upstreamBody = enabled.upstreamBody;
  } catch {
    return json(res, 400, { error: { message: "Request body must be valid JSON" } });
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
    return json(res, 502, { error: { message: err.message } });
  }

  const { messagesUrl } = gatewayConfig(env);
  let upstreamResponse;
  try {
    upstreamResponse = await fetch(messagesUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${accessToken}`,
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
    return json(res, 502, { error: { message: `Could not reach AI Gateway: ${err.message}` } });
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
    } catch { /* ignore */ }
    res.writeHead(upstreamResponse.status, { "content-type": "application/json" });
    res.end(errText || JSON.stringify({ error: { message: `AI Gateway HTTP ${upstreamResponse.status}` } }));
    return;
  }

  if (!upstreamResponse.body) {
    return json(res, 502, { error: { message: "AI Gateway returned an empty body" } });
  }

  res.writeHead(200, {
    "content-type": "text/event-stream; charset=utf-8",
    "cache-control": "no-cache",
    connection: "keep-alive",
    "x-ust-stream": "1",
    "x-ust-result": "1"
  });

  const writeLine = (line) => {
    if (!res.writableEnded) res.write(line);
  };

  const keepalive = setInterval(() => {
    try { writeLine(": keepalive\n\n"); } catch { /* client gone */ }
  }, KEEPALIVE_MS);

  try {
    writeLine(": upstream-open\n\n");
    const assembled = await readMessagesStream(upstreamResponse);

    const usageRaw = assembled.usage || {};
    const inputTokens = usageRaw.input_tokens ?? 0;
    const outputTokens = usageRaw.output_tokens ?? 0;
    const estCostUsd = (inputTokens || outputTokens)
      ? estimateCostUsd({ inputTokens, outputTokens }, model)
      : 0;
    if (inputTokens || outputTokens) {
      await recordUsage(env, { inputTokens, outputTokens, estCostUsd });
    }
    await recordAudit(env, {
      source: "extract",
      status: "ok",
      durationMs: Date.now() - startedAt,
      model,
      inputTokens: inputTokens || undefined,
      outputTokens: outputTokens || undefined,
      estCostUsd: (inputTokens || outputTokens) ? estCostUsd : undefined,
      flags: flags.length ? flags : undefined
    });

    writeLine(`data: ${JSON.stringify({ type: "ust_result", message: assembled })}\n\n`);
  } catch (err) {
    console.error(`extract: assemble failed: ${err.message}`);
    try {
      await recordAudit(env, {
        source: "extract",
        status: "error",
        durationMs: Date.now() - startedAt,
        model,
        flags: flags.length ? flags : undefined
      });
    } catch { /* ignore */ }
    try {
      writeLine(`data: ${JSON.stringify({
        type: "ust_error",
        error: { message: err.message || "AI Gateway stream failed" }
      })}\n\n`);
    } catch { /* ignore */ }
  } finally {
    clearInterval(keepalive);
    if (!res.writableEnded) res.end();
  }
}

function handleJobs(_req, res) {
  json(res, 501, {
    error: {
      message:
        "Background jobs are not available on this Agentrix deployment yet. Use interactive Run Extraction with Extract with AI checked."
    }
  });
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (req.method === "GET" && (path === "/health" || path === "/api/health")) {
      return json(res, 200, { ok: true, runtime: "agentrix" });
    }

    if (req.method === "GET" && path === "/api/features") {
      return handleFeatures(req, res);
    }

    if (req.method === "POST" && path === "/api/extract") {
      return await handleExtract(req, res);
    }

    if (req.method === "POST" && path === "/api/qc-summary") {
      return await handleQcSummary(req, res);
    }

    if (path === "/api/jobs" || path.startsWith("/api/jobs/")) {
      return handleJobs(req, res);
    }

    json(res, 404, { error: { message: "Not found" } });
  } catch (err) {
    console.error(`server error: ${err.message}`);
    if (!res.headersSent) {
      json(res, 500, { error: { message: "Internal server error" } });
    } else if (!res.writableEnded) {
      res.end();
    }
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`UST Agentrix API listening on 127.0.0.1:${PORT}`);
});

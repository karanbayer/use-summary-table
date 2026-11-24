// Agentrix Node server — static UI (app/) + AI relay (/api/extract) + soft-async
// /api/jobs* (in-process queue; needs Knative minScale: 1).
// Ports Cloudflare Pages Functions without CF runtime.
// Zero npm dependencies: Node 20+ built-in http + fetch.
//
// Knative/Agentrix sets PORT (usually 8080). This process MUST listen on that
// port and serve both the UI and the API — a separate nginx on 8080 conflicts
// when PORT is injected, which produced GET / → {"error":{"message":"Not found"}}.
//
// Required env:
//   AZURE_CLIENT_SECRET  (or TFY_API_TOKEN fallback)
//   PILOT_GATE_SECRET    must match PILOT_GATE_HEADER_VALUE in app/index.html
// Optional: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_SCOPE, TFY_BASE_URL,
//   RATE_LIMIT_PER_MINUTE, DAILY_BUDGET_USD, AUDIT_TTL_SECONDS,
//   KILL_SWITCH_ENABLED, KILL_SWITCH_REASON, PORT (default 8080),
//   STATIC_ROOT (default /app/public)

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
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
import { initSoftJobs, handleSoftJobs } from "./lib/soft-jobs.mjs";

const PORT = Number(process.env.PORT) || 8080;
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STATIC_ROOT = process.env.STATIC_ROOT
  || (fs.existsSync("/app/public") ? "/app/public" : path.resolve(__dirname, "../app"));
const MAX_EXTRACT_BYTES = 2 * 1024 * 1024;
const MAX_QC_BYTES = 8 * 1024;
const KEEPALIVE_MS = 1500;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".wasm": "application/wasm",
  ".map": "application/json",
  ".txt": "text/plain; charset=utf-8",
  ".pdf": "application/pdf"
};

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
    // Soft async: in-process queue + memory store. Needs Knative minScale: 1.
    backgroundJobs: true,
    backgroundJobsMode: "soft-async",
    softAsyncBuild: "2026-09-25a",
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

function handleMcp(_req, res) {
  // Agentrix advertises /mcp; this app is a browser UI, not an MCP server.
  json(res, 200, {
    ok: false,
    mcp: false,
    message:
      "This deployment is a web UI (Use Summary Tables Extractor), not an MCP server. Open / in a browser.",
    ui: "/",
    health: "/health",
    extract: "POST /api/extract"
  });
}

function safeJoin(root, reqPath) {
  const decoded = decodeURIComponent(reqPath.split("?")[0]);
  const cleaned = path.normalize(decoded).replace(/^(\.\.[/\\])+/, "");
  const full = path.join(root, cleaned);
  if (!full.startsWith(root)) return null;
  return full;
}

function serveStatic(req, res, urlPath) {
  let rel = urlPath === "/" ? "/index.html" : urlPath;
  let filePath = safeJoin(STATIC_ROOT, rel);
  if (!filePath) {
    json(res, 400, { error: { message: "Bad path" } });
    return;
  }

  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) {
      // SPA-style fallback for unknown paths that aren't under /api
      const indexPath = path.join(STATIC_ROOT, "index.html");
      fs.readFile(indexPath, (indexErr, data) => {
        if (indexErr) {
          json(res, 404, { error: { message: "Not found" } });
          return;
        }
        res.writeHead(200, {
          "content-type": "text/html; charset=utf-8",
          "cache-control": "no-cache",
          "content-length": data.length
        });
        res.end(data);
      });
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const type = MIME[ext] || "application/octet-stream";
    const cache = ext === ".html" ? "no-cache" : "public, max-age=3600";
    res.writeHead(200, {
      "content-type": type,
      "cache-control": cache,
      "content-length": stat.size
    });
    fs.createReadStream(filePath).pipe(res);
  });
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
    const reqPath = url.pathname.replace(/\/+$/, "") || "/";

    if (req.method === "GET" && (reqPath === "/health" || reqPath === "/api/health")) {
      return json(res, 200, { ok: true, runtime: "agentrix", version: process.env.AGENT_VERSION || null });
    }

    if (req.method === "GET" && (reqPath === "/mcp" || reqPath === "/mcp/")) {
      return handleMcp(req, res);
    }

    if (req.method === "GET" && reqPath === "/api/features") {
      return handleFeatures(req, res);
    }

    if (req.method === "POST" && reqPath === "/api/extract") {
      return await handleExtract(req, res);
    }

    if (req.method === "POST" && reqPath === "/api/qc-summary") {
      return await handleQcSummary(req, res);
    }

    if (reqPath === "/api/jobs" || reqPath.startsWith("/api/jobs/")) {
      return await handleSoftJobs(req, res, reqPath);
    }

    if (req.method === "GET" || req.method === "HEAD") {
      return serveStatic(req, res, url.pathname || "/");
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

initSoftJobs(env.AUDIT_LOG);

server.listen(PORT, "0.0.0.0", () => {
  console.log(`UST Agentrix listening on 0.0.0.0:${PORT} (static: ${STATIC_ROOT})`);
  console.log("soft-async jobs enabled — set Knative minScale: 1 so the pod stays warm");
});

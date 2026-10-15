// Agentrix soft-async jobs — same client contract as Cloudflare /api/jobs*
// (submit per file, poll status, cancel, retry) but with an in-process queue
// and in-memory KV stand-in.
//
// Requires Knative/Agentrix minScale: 1 so the pod is not scaled to zero while
// jobs run. Pod restart / redeploy drops all in-flight and queued work.
// When the platform offers SQS/Redis, swap JOBS + enqueue behind this API.

import {
  checkKillSwitch,
  checkRateLimit,
  checkBudget,
  recordUsage,
  recordAudit,
  scanForInjectionPhrases
} from "./governance.mjs";
import { createMemoryStore } from "./memory-store.mjs";
import {
  extractWithLLM,
  JOB_TTL_SECONDS,
  JobCancelledError,
  assertNotCancelled
} from "./pipeline.mjs";

const MAX_BODY_BYTES = 2 * 1024 * 1024;

/** @type {ReturnType<typeof createMemoryStore>} */
let JOBS = createMemoryStore();

/** @type {Array<{ jobId: string, fileIndex: number }>} */
const pending = [];
let workerRunning = false;

function isCancelledError(err) {
  return err instanceof JobCancelledError || err?.name === "JobCancelledError";
}

async function writeFileResult(env, jobId, fileIndex, patch) {
  const key = `job:${jobId}:file:${fileIndex}`;
  const existingText = await env.JOBS.get(key);
  const existing = existingText ? JSON.parse(existingText) : {};
  await env.JOBS.put(
    key,
    JSON.stringify({ ...existing, ...patch }),
    { expirationTtl: JOB_TTL_SECONDS }
  );
}

async function processMessage(env, jobId, fileIndex) {
  const inputText = await env.JOBS.get(`job:${jobId}:input:${fileIndex}`);
  if (!inputText) {
    console.error(`job:${jobId}:input:${fileIndex} missing — cannot process`);
    await writeFileResult(env, jobId, fileIndex, {
      status: "error",
      error: "Job input was not found (process may have restarted)."
    });
    return;
  }

  const { fileName, pageMarkedText, selectedAi } = JSON.parse(inputText);
  const doc = { fileName, selectedAi: selectedAi || null };

  try {
    await assertNotCancelled(env, jobId);
  } catch (err) {
    if (isCancelledError(err)) {
      console.log(`${fileName} (job ${jobId}, file ${fileIndex}): cancelled before start`);
      await recordAudit(env, { source: "job", jobId, fileIndex, status: "cancelled" });
      await writeFileResult(env, jobId, fileIndex, {
        fileName,
        status: "cancelled",
        error: "Cancelled by user"
      });
      return;
    }
    throw err;
  }

  const killSwitch = await checkKillSwitch(env);
  if (killSwitch.enabled) {
    await recordAudit(env, { source: "job", jobId, fileIndex, status: "blocked_killswitch" });
    await writeFileResult(env, jobId, fileIndex, { fileName, status: "error", error: killSwitch.reason });
    return;
  }

  const budget = await checkBudget(env);
  if (!budget.allowed) {
    const message = `Daily AI budget exceeded ($${budget.limitUsd}) — try again tomorrow.`;
    await recordAudit(env, { source: "job", jobId, fileIndex, status: "blocked_budget" });
    await writeFileResult(env, jobId, fileIndex, { fileName, status: "error", error: message });
    return;
  }

  const startedAt = Date.now();
  try {
    await writeFileResult(env, jobId, fileIndex, { fileName, status: "processing" });
    const { rows, qcReport, usage, remediationCycles } = await extractWithLLM(
      env, jobId, fileIndex, doc, pageMarkedText
    );
    await assertNotCancelled(env, jobId);
    await recordUsage(env, usage);
    await recordAudit(env, {
      source: "job",
      jobId,
      fileIndex,
      status: "ok",
      durationMs: Date.now() - startedAt,
      inputTokens: usage.inputTokens,
      outputTokens: usage.outputTokens,
      estCostUsd: usage.estCostUsd,
      remediationCycles,
      qcOverall: qcReport.overall
    });
    await writeFileResult(env, jobId, fileIndex, { fileName, status: "done", rows, qcReport });
  } catch (err) {
    if (isCancelledError(err)) {
      console.log(`${fileName} (job ${jobId}, file ${fileIndex}): cancelled mid-run`);
      await recordAudit(env, {
        source: "job",
        jobId,
        fileIndex,
        status: "cancelled",
        durationMs: Date.now() - startedAt
      });
      await writeFileResult(env, jobId, fileIndex, {
        fileName,
        status: "cancelled",
        error: "Cancelled by user"
      });
      return;
    }
    console.error(`${fileName} (job ${jobId}, file ${fileIndex}) failed: ${err.message}`);
    await recordAudit(env, {
      source: "job",
      jobId,
      fileIndex,
      status: "error",
      durationMs: Date.now() - startedAt
    });
    await writeFileResult(env, jobId, fileIndex, {
      fileName,
      status: "error",
      error: err.message
    });
  }
}

function enqueue(jobId, fileIndex) {
  pending.push({ jobId, fileIndex });
  kickWorker();
}

function kickWorker() {
  if (workerRunning) return;
  workerRunning = true;
  setImmediate(runWorkerLoop);
}

async function runWorkerLoop() {
  const env = softJobsEnv();
  try {
    while (pending.length) {
      const { jobId, fileIndex } = pending.shift();
      try {
        await processMessage(env, jobId, fileIndex);
      } catch (err) {
        console.error(`soft-jobs unexpected failure job ${jobId} file ${fileIndex}: ${err.message}`);
      }
    }
  } finally {
    workerRunning = false;
    if (pending.length) kickWorker();
  }
}

/** Shared env for handlers + worker (AUDIT_LOG from server, JOBS in-memory). */
let sharedAuditLog = null;

export function initSoftJobs(auditLog) {
  sharedAuditLog = auditLog;
  JOBS = createMemoryStore();
  console.log("soft-jobs: in-process queue ready (set Agentrix minScale: 1)");
}

function softJobsEnv() {
  return {
    ...process.env,
    AUDIT_LOG: sharedAuditLog,
    JOBS
  };
}

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
  return Boolean(process.env.PILOT_GATE_SECRET && gate === process.env.PILOT_GATE_SECRET);
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

async function handleCreateJob(req, res) {
  const env = softJobsEnv();
  if (!checkPilotGate(req)) return unauthorized(res);

  const killSwitch = await checkKillSwitch(env);
  if (killSwitch.enabled) {
    await recordAudit(env, { source: "job", status: "blocked_killswitch" });
    return json(res, 503, { error: { message: killSwitch.reason } });
  }

  const rateLimit = await checkRateLimit(env, "jobs");
  if (!rateLimit.allowed) {
    await recordAudit(env, { source: "job", status: "blocked_rate_limit" });
    return json(res, 429, {
      error: { message: `Rate limit exceeded (${rateLimit.limit}/min) — wait a moment and retry.` }
    });
  }

  const budget = await checkBudget(env);
  if (!budget.allowed) {
    await recordAudit(env, { source: "job", status: "blocked_budget" });
    return json(res, 429, {
      error: {
        message: `Daily AI budget exceeded ($${budget.limitUsd}) — try again tomorrow, or ask whoever manages the pilot to raise DAILY_BUDGET_USD.`
      }
    });
  }

  let bodyText;
  try {
    bodyText = await readBody(req, MAX_BODY_BYTES);
  } catch (err) {
    return json(res, err.statusCode || 400, { error: { message: err.message } });
  }

  let body;
  try {
    body = JSON.parse(bodyText);
  } catch {
    return json(res, 400, { error: { message: "Body must be JSON" } });
  }

  const { jobId, fileIndex, totalFiles, fileName, pageMarkedText, selectedAi, createdAt } = body;

  if (typeof jobId !== "string" || !jobId) {
    return json(res, 400, { error: { message: "jobId is required" } });
  }
  if (!Number.isInteger(fileIndex) || fileIndex < 0) {
    return json(res, 400, { error: { message: "fileIndex must be a non-negative integer" } });
  }
  if (!Number.isInteger(totalFiles) || totalFiles < 1) {
    return json(res, 400, { error: { message: "totalFiles must be a positive integer" } });
  }
  if (typeof fileName !== "string" || !fileName) {
    return json(res, 400, { error: { message: "fileName is required" } });
  }
  if (typeof pageMarkedText !== "string" || !pageMarkedText) {
    return json(res, 400, { error: { message: "pageMarkedText is required" } });
  }

  try {
    await env.JOBS.put(
      `job:${jobId}:meta`,
      JSON.stringify({ jobId, createdAt: createdAt || new Date().toISOString(), totalFiles }),
      { expirationTtl: JOB_TTL_SECONDS }
    );
    await env.JOBS.put(
      `job:${jobId}:input:${fileIndex}`,
      JSON.stringify({ fileName, pageMarkedText, selectedAi: selectedAi || null }),
      { expirationTtl: JOB_TTL_SECONDS }
    );
    await env.JOBS.put(
      `job:${jobId}:file:${fileIndex}`,
      JSON.stringify({ fileName, status: "queued" }),
      { expirationTtl: JOB_TTL_SECONDS }
    );

    enqueue(jobId, fileIndex);

    const flags = scanForInjectionPhrases(pageMarkedText);
    await recordAudit(env, {
      source: "job",
      jobId,
      fileIndex,
      status: "queued",
      flags: flags.length ? flags : undefined
    });
  } catch (err) {
    return json(res, 502, { error: { message: `Could not create job file entry: ${err.message}` } });
  }

  return json(res, 202, { ok: true, jobId, fileIndex });
}

async function handleGetJob(req, res, jobId) {
  const env = softJobsEnv();
  if (!checkPilotGate(req)) return unauthorized(res);

  const metaText = await env.JOBS.get(`job:${jobId}:meta`);
  if (!metaText) {
    return json(res, 404, {
      error: { message: "Job not found (it may have expired, or the pod restarted)." }
    });
  }

  const meta = JSON.parse(metaText);
  const files = [];
  for (let fileIndex = 0; fileIndex < meta.totalFiles; fileIndex++) {
    const fileText = await env.JOBS.get(`job:${jobId}:file:${fileIndex}`);
    files.push(fileText ? { fileIndex, ...JSON.parse(fileText) } : { fileIndex, status: "queued" });
  }

  const settled = (s) => s === "done" || s === "error" || s === "cancelled";
  const allSettled = files.every(f => settled(f.status));
  const anyError = files.some(f => f.status === "error");
  const anyCancelled = meta.cancelled || files.some(f => f.status === "cancelled");
  const status = !allSettled
    ? (meta.cancelled ? "cancelling" : "processing")
    : (anyCancelled ? "cancelled" : (anyError ? "done_with_errors" : "done"));

  return json(res, 200, {
    jobId,
    createdAt: meta.createdAt,
    totalFiles: meta.totalFiles,
    cancelled: !!meta.cancelled,
    cancelledAt: meta.cancelledAt || null,
    status,
    files,
    softAsync: true
  });
}

async function handleCancelJob(req, res, jobId) {
  const env = softJobsEnv();
  if (!checkPilotGate(req)) return unauthorized(res);

  const metaKey = `job:${jobId}:meta`;
  const metaText = await env.JOBS.get(metaKey);
  if (!metaText) {
    return json(res, 404, {
      error: { message: "Job not found (it may have expired, or the pod restarted)." }
    });
  }

  const meta = JSON.parse(metaText);
  if (meta.cancelled) {
    return json(res, 200, { ok: true, jobId, alreadyCancelled: true, cancelledFiles: 0 });
  }

  let hasActive = false;
  const fileSnapshots = [];
  for (let fileIndex = 0; fileIndex < meta.totalFiles; fileIndex++) {
    const fileText = await env.JOBS.get(`job:${jobId}:file:${fileIndex}`);
    const file = fileText ? JSON.parse(fileText) : { status: "queued" };
    fileSnapshots.push({ fileIndex, file });
    if (file.status === "queued" || file.status === "processing") hasActive = true;
  }

  if (!hasActive) {
    return json(res, 200, { ok: true, jobId, alreadySettled: true, cancelledFiles: 0 });
  }

  const cancelledAt = new Date().toISOString();
  let cancelledFiles = 0;

  await env.JOBS.put(
    metaKey,
    JSON.stringify({ ...meta, cancelled: true, cancelledAt }),
    { expirationTtl: JOB_TTL_SECONDS }
  );

  for (const { fileIndex, file } of fileSnapshots) {
    if (file.status === "queued") {
      // Drop from pending queue if still waiting.
      for (let i = pending.length - 1; i >= 0; i--) {
        if (pending[i].jobId === jobId && pending[i].fileIndex === fileIndex) {
          pending.splice(i, 1);
        }
      }
      await env.JOBS.put(
        `job:${jobId}:file:${fileIndex}`,
        JSON.stringify({
          fileName: file.fileName,
          status: "cancelled",
          error: "Cancelled by user"
        }),
        { expirationTtl: JOB_TTL_SECONDS }
      );
      cancelledFiles++;
    }
  }

  return json(res, 200, { ok: true, jobId, cancelledFiles });
}

async function handleRetryJob(req, res, jobId) {
  const env = softJobsEnv();
  if (!checkPilotGate(req)) return unauthorized(res);

  let body;
  try {
    body = JSON.parse(await readBody(req, 64 * 1024));
  } catch {
    return json(res, 400, { error: { message: "Body must be JSON" } });
  }

  const { fileIndex } = body;
  if (!Number.isInteger(fileIndex) || fileIndex < 0) {
    return json(res, 400, { error: { message: "fileIndex must be a non-negative integer" } });
  }

  const metaText = await env.JOBS.get(`job:${jobId}:meta`);
  if (metaText) {
    const meta = JSON.parse(metaText);
    if (meta.cancelled) {
      return json(res, 409, {
        error: { message: "This job was cancelled — start a new background run instead of retrying." }
      });
    }
  }

  const fileKey = `job:${jobId}:file:${fileIndex}`;
  const inputKey = `job:${jobId}:input:${fileIndex}`;
  const fileText = await env.JOBS.get(fileKey);
  if (!fileText) {
    return json(res, 404, { error: { message: "File record not found (pod may have restarted)." } });
  }

  const file = JSON.parse(fileText);
  if (file.status !== "error") {
    return json(res, 409, {
      error: { message: `Only a file with status "error" can be retried (current status: "${file.status}").` }
    });
  }

  const inputText = await env.JOBS.get(inputKey);
  if (!inputText) {
    return json(res, 404, { error: { message: "Job input was not found — cannot retry." } });
  }

  await env.JOBS.put(
    fileKey,
    JSON.stringify({ fileName: file.fileName, status: "queued" }),
    { expirationTtl: JOB_TTL_SECONDS }
  );
  enqueue(jobId, fileIndex);
  return json(res, 202, { ok: true, jobId, fileIndex });
}

/**
 * Route /api/jobs and /api/jobs/:id[/cancel|/retry] for the Agentrix server.
 */
export async function handleSoftJobs(req, res, reqPath) {
  if (req.method === "POST" && reqPath === "/api/jobs") {
    return handleCreateJob(req, res);
  }

  const m = reqPath.match(/^\/api\/jobs\/([^/]+)(?:\/(cancel|retry))?$/);
  if (!m) {
    return json(res, 404, { error: { message: "Not found" } });
  }

  const jobId = decodeURIComponent(m[1]);
  const action = m[2] || null;

  if (req.method === "GET" && !action) {
    return handleGetJob(req, res, jobId);
  }
  if (req.method === "POST" && action === "cancel") {
    return handleCancelJob(req, res, jobId);
  }
  if (req.method === "POST" && action === "retry") {
    return handleRetryJob(req, res, jobId);
  }

  return json(res, 405, { error: { message: "Method not allowed" } });
}

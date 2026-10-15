// Standalone Cloudflare Worker — consumes the "use-summary-jobs" queue
// (producer: functions/api/jobs.js in the main Pages project) and runs the
// AI extraction pipeline (pipeline.js) server-side, so a colleague can close
// their browser tab and come back to finished results.
//
// Each queue message is just a pointer {jobId, fileIndex} — the actual
// pageMarkedText lives in KV (job:<jobId>:input:<fileIndex>), written by
// jobs.js before it enqueued. See functions/api/jobs.js for the full KV
// schema shared between both sides.
//
// max_batch_size=1 (worker/wrangler.toml) means this handler only ever sees
// one message per batch — no need to fan out within a single queue() call.
//
// A kill-switch check, daily cost-budget precheck, and per-file audit
// logging run here (see governance.js) — the interactive /api/extract path
// checks and logs its own calls; this is the equivalent for the background
// path, using the SAME AUDIT_LOG namespace so the two share one cumulative
// daily total and one kill-switch flag.
//
// Cancellation: POST /api/jobs/<id>/cancel sets meta.cancelled. Queued files
// are marked cancelled immediately; this Worker checks assertNotCancelled
// before starting and between pipeline stages so mid-run work stops after
// the current Gateway call finishes.

import {
  extractWithLLM,
  JOB_TTL_SECONDS,
  JobCancelledError,
  NoUsesOnLabelError,
  SliceYield,
  clearProgress,
  assertNotCancelled
} from "./pipeline.js";
import { checkKillSwitch, checkBudget, recordUsage, recordAudit } from "./governance.js";

// A delivery count past this means a slice keeps being killed before it can save
// and re-queue — give up with a visible error instead of leaving "processing".
// Matches max_retries in wrangler.toml.
const MAX_DELIVERIES = 8;
// Upper bound on 10-minute slices per file (~5 hours) — a 178-page label needs ~8.
const MAX_SLICES = 30;
const sliceCountKey = (jobId, fileIndex) => `job:${jobId}:slices:${fileIndex}`;

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
    console.error(`job:${jobId}:input:${fileIndex} missing from KV — cannot process (expired, or never written).`);
    await writeFileResult(env, jobId, fileIndex, {
      status: "error",
      error: "Job input was not found (it may have expired)."
    });
    return;
  }

  const { fileName, pageMarkedText, selectedAi } = JSON.parse(inputText);
  const doc = { fileName, selectedAi: selectedAi || null };

  // Job cancelled while this message was still queued — skip without calling
  // the Gateway (cancel API already marks queued files; this covers races).
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

  // Re-checked here (not just at jobs.js submission time) because a queued
  // file can sit for a while before this Worker picks it up — an incident
  // noticed after submission but before processing should still stop it.
  const killSwitch = await checkKillSwitch(env);
  if (killSwitch.enabled) {
    console.error(`${fileName} (job ${jobId}, file ${fileIndex}): kill switch enabled — ${killSwitch.reason}`);
    await recordAudit(env, { source: "job", jobId, fileIndex, status: "blocked_killswitch" });
    await writeFileResult(env, jobId, fileIndex, { fileName, status: "error", error: killSwitch.reason });
    return;
  }

  // Belt-and-suspenders vs. the precheck jobs.js already ran at submission
  // time — this Worker runs as an independent process, and is also the side
  // that knows the most up-to-date cumulative spend (it's the one writing
  // it, via recordUsage below).
  const budget = await checkBudget(env);
  if (!budget.allowed) {
    const message = `Daily AI budget exceeded ($${budget.limitUsd}) — try again tomorrow.`;
    console.error(`${fileName} (job ${jobId}, file ${fileIndex}): ${message}`);
    await recordAudit(env, { source: "job", jobId, fileIndex, status: "blocked_budget" });
    await writeFileResult(env, jobId, fileIndex, { fileName, status: "error", error: message });
    return;
  }

  const startedAt = Date.now();
  try {
    await writeFileResult(env, jobId, fileIndex, { fileName, status: "processing" });
    const { rows, qcReport, usage, remediationCycles } = await extractWithLLM(env, jobId, fileIndex, doc, pageMarkedText);
    // Final check — cancel may have landed during the last Gateway call.
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
    await clearProgress(env, jobId, fileIndex);
  } catch (err) {
    if (err instanceof SliceYield || err?.name === "SliceYield") {
      const slices = (Number(await env.JOBS.get(sliceCountKey(jobId, fileIndex))) || 0) + 1;
      if (slices > MAX_SLICES) {
        await writeFileResult(env, jobId, fileIndex, {
          fileName,
          status: "error",
          error: `Stopped after ${MAX_SLICES} ten-minute slices without finishing.`
        });
        await clearProgress(env, jobId, fileIndex);
        return;
      }
      await env.JOBS.put(sliceCountKey(jobId, fileIndex), String(slices), { expirationTtl: JOB_TTL_SECONDS });
      console.log(`${fileName} (job ${jobId}, file ${fileIndex}): slice ${slices} — ${err.message}`);
      await env.JOBS_QUEUE.send({ jobId, fileIndex });
      return;
    }
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
    if (err instanceof NoUsesOnLabelError || err?.name === "NoUsesOnLabelError") {
      console.log(`${fileName} (job ${jobId}, file ${fileIndex}): ${err.message}`);
      if (err.usage) await recordUsage(env, err.usage);
      await recordAudit(env, {
        source: "job",
        jobId,
        fileIndex,
        status: "ok",
        durationMs: Date.now() - startedAt,
        inputTokens: err.usage?.inputTokens,
        outputTokens: err.usage?.outputTokens,
        estCostUsd: err.usage?.estCostUsd,
        qcOverall: "Clean"
      });
      await writeFileResult(env, jobId, fileIndex, {
        fileName,
        status: "done",
        rows: [],
        noUses: true,
        qcReport: { overall: "Clean", defects: [], note: err.message }
      });
      await clearProgress(env, jobId, fileIndex);
      return;
    }
    console.error(`${fileName} (job ${jobId}, file ${fileIndex}) failed: ${err.message}`);
    await recordAudit(env, { source: "job", jobId, fileIndex, status: "error", durationMs: Date.now() - startedAt });
    await writeFileResult(env, jobId, fileIndex, { fileName, status: "error", error: err.message });
    await clearProgress(env, jobId, fileIndex);
  }
}

export default {
  async queue(batch, env, ctx) {
    for (const message of batch.messages) {
      const { jobId, fileIndex } = message.body;
      if ((message.attempts || 1) > MAX_DELIVERIES) {
        console.error(`job ${jobId} file ${fileIndex}: ${message.attempts} deliveries — marking failed`);
        await writeFileResult(env, jobId, fileIndex, {
          status: "error",
          error: `Stopped after ${MAX_DELIVERIES} attempts: each run ran out of time before it could save progress.`
        });
        await clearProgress(env, jobId, fileIndex);
        message.ack();
        continue;
      }
      try {
        await processMessage(env, jobId, fileIndex);
      } catch (err) {
        // processMessage already writes an "error" status for pipeline
        // failures — this catch is only for something unexpected escaping
        // that (e.g. a KV outage). Ack anyway: retrying against the shared
        // mGA token on an unknown failure mode isn't safe to do
        // automatically, mirroring the client's own no-silent-retry stance.
        console.error(`unexpected failure processing job ${jobId} file ${fileIndex}: ${err.message}`);
      }
      // Always ack — a failed doc should surface as status:"error" for the
      // user to see and re-submit, not trigger Cloudflare's automatic
      // redelivery against the shared, rate-limited mGA token.
      message.ack();
    }
  }
};

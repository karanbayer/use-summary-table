// Cloudflare Pages Function — cancel a background job mid-flight.
// Sets job:<jobId>:meta.cancelled so the Worker skips remaining work, and
// marks every file still queued as status:"cancelled". Files already mid-
// Gateway-call finish that one call, then the Worker stops before the next
// stage (see worker/src/index.js + pipeline.js assertNotCancelled).
//
// Used by the Cancel button on the ?job=<jobId> status view and job history.

const JOB_TTL_SECONDS = 7 * 24 * 60 * 60;

export async function onRequestPost(context) {
  const { request, env, params } = context;

  const gate = request.headers.get("x-ust-pilot");
  if (!env.PILOT_GATE_SECRET || gate !== env.PILOT_GATE_SECRET) {
    return new Response(JSON.stringify({ error: { message: "Unauthorized" } }), {
      status: 401,
      headers: { "content-type": "application/json" }
    });
  }

  const jobId = params.id;
  if (typeof jobId !== "string" || !jobId) {
    return new Response(JSON.stringify({ error: { message: "Job id is required" } }), {
      status: 400,
      headers: { "content-type": "application/json" }
    });
  }

  const metaKey = `job:${jobId}:meta`;
  const metaText = await env.JOBS.get(metaKey);
  if (!metaText) {
    return new Response(JSON.stringify({ error: { message: "Job not found (it may have expired, or never existed)" } }), {
      status: 404,
      headers: { "content-type": "application/json" }
    });
  }

  const meta = JSON.parse(metaText);
  if (meta.cancelled) {
    return new Response(JSON.stringify({
      ok: true,
      jobId,
      alreadyCancelled: true,
      cancelledFiles: 0
    }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
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
    return new Response(JSON.stringify({
      ok: true,
      jobId,
      alreadySettled: true,
      cancelledFiles: 0
    }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  }

  const cancelledAt = new Date().toISOString();
  let cancelledFiles = 0;

  try {
    await env.JOBS.put(
      metaKey,
      JSON.stringify({ ...meta, cancelled: true, cancelledAt }),
      { expirationTtl: JOB_TTL_SECONDS }
    );

    for (const { fileIndex, file } of fileSnapshots) {
      // Leave done/error alone. Queued → cancelled now. Processing stays
      // "processing" until the Worker sees meta.cancelled and writes cancelled
      // (avoids racing a final "done" write).
      if (file.status === "queued") {
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
  } catch (err) {
    return new Response(JSON.stringify({ error: { message: `Could not cancel job: ${err.message}` } }), {
      status: 502,
      headers: { "content-type": "application/json" }
    });
  }

  return new Response(JSON.stringify({
    ok: true,
    jobId,
    cancelledAt,
    cancelledFiles
  }), {
    status: 200,
    headers: { "content-type": "application/json" }
  });
}

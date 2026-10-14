#!/usr/bin/env python3
"""Overnight live scale run against Cloudflare background jobs (no browser).

Extracts page-marked text locally (pypdf), POSTs to /api/jobs, polls until
settled, then advances Wave A → B → C. Writes progress under samples/scale/_report/.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from pypdf import PdfReader
except ImportError:
    print("Install pypdf: python3 -m pip install pypdf", file=sys.stderr)
    sys.exit(1)

# Override for local Node soft-async overnight: BASE_URL=http://127.0.0.1:8080
BASE_URL = (os.environ.get("BASE_URL") or "https://use-summary-table.pages.dev").rstrip("/")
PILOT_HEADER = "ust-pilot-2026"
POLL_SECONDS = 45
SUBMIT_GAP_SECONDS = 2  # stay under RATE_LIMIT_PER_MINUTE=20
MAX_BODY_BYTES = 2 * 1024 * 1024

ROOT = Path(__file__).resolve().parents[1]
SCALE_DIR = ROOT / "samples" / "scale"
REPORT_DIR = SCALE_DIR / "_report"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"[{utc_now()}] {msg}"
    print(line, flush=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORT_DIR / "live-run.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def http_json(method: str, path: str, body: dict | None = None, timeout: int = 120) -> tuple[int, dict]:
    data = None
    # Cloudflare Error 1010 bans bare Python-urllib UA — send a browser signature.
    headers = {
        "x-ust-pilot": PILOT_HEADER,
        "accept": "application/json, text/plain, */*",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "origin": BASE_URL,
        "referer": f"{BASE_URL}/",
    }
    if body is not None:
        raw = json.dumps(body).encode("utf-8")
        if len(raw) > MAX_BODY_BYTES:
            raise ValueError(f"body {len(raw)} bytes exceeds {MAX_BODY_BYTES}")
        data = raw
        headers["content-type"] = "application/json"
    req = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, (json.loads(text) if text else {})
    except HTTPError as err:
        text = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError:
            parsed = {"error": {"message": text[:500]}}
        return err.code, parsed


def page_marked_text(pdf_path: Path) -> tuple[str, int]:
    reader = PdfReader(str(pdf_path))
    parts = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        parts.append(f"--- PAGE {i} ---\n{text}")
    return "\n\n".join(parts), len(reader.pages)


def wave_lists() -> dict[str, list[str]]:
    report_path = REPORT_DIR / "scale-report.json"
    if report_path.exists():
        files = sorted(
            json.loads(report_path.read_text(encoding="utf-8"))["files"],
            key=lambda m: (m["pages"], m["text_chars"], m["file_name"]),
        )
        names = [m["file_name"] for m in files]
    else:
        names = sorted(p.name for p in SCALE_DIR.glob("*.pdf"))
    return {
        "A": names[:5],
        "B": names[5:15],
        "C": names[15:],
    }


def submit_wave(wave_name: str, file_names: list[str]) -> dict:
    job_id = str(uuid.uuid4())
    created_at = utc_now()
    total = len(file_names)
    log(f"WAVE {wave_name}: submitting {total} file(s) as job {job_id}")
    results = []
    for idx, name in enumerate(file_names):
        path = SCALE_DIR / name
        if not path.exists():
            results.append({"fileIndex": idx, "fileName": name, "submit": "missing"})
            log(f"  ✖ missing {name}")
            continue
        text, pages = page_marked_text(path)
        if not text.strip() or len(text.strip()) < 40:
            results.append({"fileIndex": idx, "fileName": name, "submit": "empty_text", "pages": pages})
            log(f"  ✖ empty text {name} ({pages}p) — skipping submit")
            continue
        body = {
            "jobId": job_id,
            "fileIndex": idx,
            "totalFiles": total,
            "fileName": name,
            "pageMarkedText": text,
            "selectedAi": "claude-sonnet",
            "createdAt": created_at,
        }
        try:
            status, resp = http_json("POST", "/api/jobs", body)
            ok = status in (200, 202) and resp.get("ok")
            results.append(
                {
                    "fileIndex": idx,
                    "fileName": name,
                    "pages": pages,
                    "chars": len(text),
                    "submit": "ok" if ok else "error",
                    "http": status,
                    "resp": resp,
                }
            )
            mark = "✔" if ok else "✖"
            log(f"  {mark} [{idx+1}/{total}] {name} ({pages}p, {len(text)} chars) HTTP {status}")
            if not ok:
                log(f"      {resp}")
        except Exception as exc:  # noqa: BLE001
            results.append({"fileIndex": idx, "fileName": name, "submit": "exception", "error": str(exc)})
            log(f"  ✖ [{idx+1}/{total}] {name}: {exc}")
        time.sleep(SUBMIT_GAP_SECONDS)

    state = {
        "wave": wave_name,
        "jobId": job_id,
        "createdAt": created_at,
        "baseUrl": BASE_URL,
        "watchUrl": f"{BASE_URL}/?job={job_id}",
        "files": file_names,
        "submissions": results,
        "startedPollAt": utc_now(),
    }
    (REPORT_DIR / f"live-wave-{wave_name}.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def summarize_job(job: dict) -> str:
    files = job.get("files") or []
    counts: dict[str, int] = {}
    for f in files:
        counts[f.get("status") or "?"] = counts.get(f.get("status") or "?", 0) + 1
    parts = [f"{k}={v}" for k, v in sorted(counts.items())]
    return f"status={job.get('status')} " + " ".join(parts)


def poll_until_done(wave_name: str, job_id: str, expected_files: int) -> dict:
    log(f"WAVE {wave_name}: polling job {job_id} (every {POLL_SECONDS}s)")
    last_sig = ""
    while True:
        status, job = http_json("GET", f"/api/jobs/{job_id}")
        if status != 200:
            log(f"  poll HTTP {status}: {job}")
            time.sleep(POLL_SECONDS)
            continue
        sig = summarize_job(job)
        if sig != last_sig:
            log(f"  {sig}")
            last_sig = sig
            (REPORT_DIR / f"live-wave-{wave_name}-status.json").write_text(
                json.dumps(job, indent=2), encoding="utf-8"
            )
        if job.get("status") in ("done", "done_with_errors", "cancelled"):
            # Compact result (drop huge row payloads into separate summary)
            compact_files = []
            for f in job.get("files") or []:
                rows = f.get("rows") or []
                compact_files.append(
                    {
                        "fileIndex": f.get("fileIndex"),
                        "fileName": f.get("fileName"),
                        "status": f.get("status"),
                        "stage": f.get("stage"),
                        "error": f.get("error"),
                        "rowCount": len(rows) if isinstance(rows, list) else None,
                        "qcSeverity": (f.get("qcReport") or {}).get("severity")
                        if isinstance(f.get("qcReport"), dict)
                        else None,
                    }
                )
            summary = {
                "wave": wave_name,
                "jobId": job_id,
                "finishedAt": utc_now(),
                "jobStatus": job.get("status"),
                "watchUrl": f"{BASE_URL}/?job={job_id}",
                "files": compact_files,
                "done": sum(1 for x in compact_files if x["status"] == "done"),
                "error": sum(1 for x in compact_files if x["status"] == "error"),
                "cancelled": sum(1 for x in compact_files if x["status"] == "cancelled"),
                "queued_or_other": sum(
                    1 for x in compact_files if x["status"] not in ("done", "error", "cancelled")
                ),
            }
            (REPORT_DIR / f"live-wave-{wave_name}-summary.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            log(
                f"WAVE {wave_name} FINISHED: {summary['jobStatus']} "
                f"done={summary['done']} error={summary['error']} "
                f"cancelled={summary['cancelled']} → {summary['watchUrl']}"
            )
            return summary
        time.sleep(POLL_SECONDS)


def wave_ok_enough(summary: dict) -> bool:
    """Advance if at least one file succeeded; stop only on total failure."""
    return summary.get("done", 0) > 0


def retry_errors(wave_name: str, job_id: str, max_rounds: int = 2) -> None:
    """Re-queue errored files a few times (Gateway blips) without laptop polling forever."""
    for round_i in range(1, max_rounds + 1):
        status, job = http_json("GET", f"/api/jobs/{job_id}")
        if status != 200:
            log(f"WAVE {wave_name}: retry probe HTTP {status}")
            return
        errored = [f for f in (job.get("files") or []) if f.get("status") == "error"]
        if not errored:
            return
        log(f"WAVE {wave_name}: retry round {round_i}/{max_rounds} for {len(errored)} error(s)")
        for f in errored:
            idx = f.get("fileIndex")
            st, resp = http_json("POST", f"/api/jobs/{job_id}/retry", {"fileIndex": idx})
            log(f"  retry fileIndex={idx} {f.get('fileName')}: HTTP {st} {resp}")
            time.sleep(SUBMIT_GAP_SECONDS)
        # give the worker time before next round
        time.sleep(max(POLL_SECONDS, 60))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Live scale run against Cloudflare jobs")
    parser.add_argument(
        "--mode",
        choices=("submit-all", "full", "poll"),
        default="submit-all",
        help="submit-all: queue A+B+C then exit (laptop can sleep). "
        "full: submit+poll each wave. poll: poll existing live-wave-*.json jobs.",
    )
    parser.add_argument("--retry-rounds", type=int, default=2)
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    waves = wave_lists()
    plan = {
        "startedAt": utc_now(),
        "baseUrl": BASE_URL,
        "mode": args.mode,
        "waves": {k: v for k, v in waves.items()},
        "note": "Live run via Cloudflare Worker + AI Gateway. "
        "submit-all queues everything so the laptop can power off.",
    }
    (REPORT_DIR / "live-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    log(f"Live scale run mode={args.mode} — {sum(len(v) for v in waves.values())} PDFs")
    log(f"Progress: {REPORT_DIR}/live-run.log")

    st, body = http_json("GET", "/api/jobs/00000000-0000-0000-0000-000000000000")
    if st not in (401, 404):
        log(f"Unexpected jobs probe HTTP {st}: {body}")
    else:
        log(f"Jobs API reachable (probe HTTP {st})")

    if args.mode == "poll":
        summaries = []
        for name in ("A", "B", "C"):
            path = REPORT_DIR / f"live-wave-{name}.json"
            if not path.exists():
                continue
            state = json.loads(path.read_text(encoding="utf-8"))
            summary = poll_until_done(name, state["jobId"], len(state.get("files") or []))
            retry_errors(name, state["jobId"], args.retry_rounds)
            # re-poll after retries
            summary = poll_until_done(name, state["jobId"], len(state.get("files") or []))
            summaries.append(summary)
        final = {
            "finishedAt": utc_now(),
            "waves": summaries,
            "totalDone": sum(s.get("done", 0) for s in summaries),
            "totalError": sum(s.get("error", 0) for s in summaries),
        }
        (REPORT_DIR / "live-final-summary.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
        log(f"POLL DONE — done={final['totalDone']} error={final['totalError']}")
        return 0 if final["totalDone"] > 0 else 1

    # submit-all or full
    job_refs = []
    for name in ("A", "B", "C"):
        files = waves[name]
        if not files:
            log(f"WAVE {name}: empty — skip")
            continue
        state = submit_wave(name, files)
        submitted_ok = sum(1 for s in state["submissions"] if s.get("submit") == "ok")
        job_refs.append(
            {
                "wave": name,
                "jobId": state["jobId"],
                "watchUrl": state["watchUrl"],
                "submittedOk": submitted_ok,
                "total": len(files),
            }
        )
        if submitted_ok == 0:
            log(f"WAVE {name}: nothing queued")
            if args.mode == "full":
                break
            continue
        if args.mode == "full":
            summary = poll_until_done(name, state["jobId"], len(files))
            retry_errors(name, state["jobId"], args.retry_rounds)
            summary = poll_until_done(name, state["jobId"], len(files))
            if not wave_ok_enough(summary):
                log(f"WAVE {name}: zero successes — stopping before next wave")
                break

    morning = {
        "queuedAt": utc_now(),
        "mode": args.mode,
        "jobs": job_refs,
        "morningInstructions": [
            "Open each watchUrl below in a browser (or run: python3 scripts/scale_run_live.py --mode poll)",
            "Read samples/scale/_report/live-final-summary.json after polling",
            "Offline sizing notes: samples/scale/_report/scale-report.md",
        ],
    }
    (REPORT_DIR / "MORNING.md").write_text(
        "\n".join(
            [
                "# Morning — scale run status",
                "",
                f"Queued at: {morning['queuedAt']}",
                "",
                "## Job links (Cloudflare keeps running after laptop sleep)",
                "",
                *[
                    f"- **Wave {j['wave']}**: {j['watchUrl']}  \n  submitted {j['submittedOk']}/{j['total']} · job `{j['jobId']}`"
                    for j in job_refs
                ],
                "",
                "## Commands",
                "",
                "```bash",
                "python3 scripts/scale_run_live.py --mode poll",
                "```",
                "",
                "Worker processes **one file at a time** (`max_concurrency=1`). "
                "Full pack may take ~6+ hours. Jobs TTL is 7 days.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (REPORT_DIR / "live-queued.json").write_text(json.dumps(morning, indent=2), encoding="utf-8")

    if args.mode == "submit-all":
        log("ALL WAVES QUEUED — laptop can sleep now. Cloudflare Worker continues.")
        for j in job_refs:
            log(f"  Wave {j['wave']}: {j['watchUrl']}")
        log(f"Morning cheat-sheet: {REPORT_DIR / 'MORNING.md'}")
        return 0 if any(j["submittedOk"] > 0 for j in job_refs) else 1

    # full mode already polled per wave
    log("FULL mode finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

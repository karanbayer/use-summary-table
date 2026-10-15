#!/usr/bin/env python3
"""Size + batch-count scale test against Cloudflare background jobs.

  submit <name> <N>   queue N labels (all 29 sorted by size, repeated to reach N)
  snapshot            fetch every submitted job, record status/rows/stage + first-seen-done time
  report              summarise reliability, time and row counts by size tier and batch

State lives in samples/scale/_report/scaletest/. Reuses scale_run_live.py's
HTTP + text-extraction helpers so it hits the same /api/jobs path the UI uses.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scale_run_live as live  # noqa: E402

OUT = live.REPORT_DIR / "scaletest"
STATE = OUT / "state.json"


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"batches": {}}


def save_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def corpus() -> list[tuple[str, int]]:
    items = []
    for p in sorted(live.SCALE_DIR.glob("*.pdf")):
        try:
            items.append((p.name, len(live.PdfReader(str(p)).pages)))
        except Exception:  # noqa: BLE001
            continue
    return sorted(items, key=lambda x: (x[1], x[0]))


def submit(name: str, n: int, only: list[str] | None = None) -> None:
    """only: "<file-prefix>[=<active ingredient>]" entries; the active is what the app
    would send after the user picks one on a multi-ingredient label."""
    state = load_state()
    if name in state["batches"]:
        sys.exit(f"batch {name} already submitted")
    files = corpus()
    chosen = {}
    if only:
        picks = []
        for spec in only:
            prefix, _, ai = spec.partition("=")
            match = next((f for f in files if f[0].startswith(prefix)), None)
            if not match:
                sys.exit(f"no file starts with {prefix!r}")
            picks.append(match)
            chosen[match[0]] = ai or None
        n = len(picks)
    else:
        picks = [files[i % len(files)] for i in range(n)]
    job_id = str(uuid.uuid4())
    created = live.utc_now()
    subs = []
    for idx, (fname, pages) in enumerate(picks):
        text, _ = live.page_marked_text(live.SCALE_DIR / fname)
        body = {"jobId": job_id, "fileIndex": idx, "totalFiles": n, "fileName": fname,
                "pageMarkedText": text, "selectedAi": chosen.get(fname), "createdAt": created}
        st, resp = live.http_json("POST", "/api/jobs", body)
        ok = st in (200, 202) and resp.get("ok")
        subs.append({"fileIndex": idx, "fileName": fname, "pages": pages, "ok": bool(ok), "http": st})
        print(f"  {'✔' if ok else '✖'} [{idx+1}/{n}] {fname} ({pages}p) HTTP {st}", flush=True)
        time.sleep(live.SUBMIT_GAP_SECONDS)
    state["batches"][name] = {"jobId": job_id, "submittedAt": created, "n": n, "files": subs, "seen": {}}
    save_state(state)
    print(f"batch {name}: job {job_id} — {sum(s['ok'] for s in subs)}/{n} queued")
    print(f"watch: {live.BASE_URL}/?job={job_id}")


def snapshot() -> None:
    state = load_state()
    now = live.utc_now()
    for name, b in state["batches"].items():
        st, job = live.http_json("GET", f"/api/jobs/{b['jobId']}")
        if st != 200:
            print(f"{name}: HTTP {st}")
            continue
        (OUT / f"job-{name}.json").write_text(json.dumps(job))
        counts = {}
        for f in job.get("files", []):
            s = f.get("status", "?")
            counts[s] = counts.get(s, 0) + 1
            key = str(f.get("fileIndex"))
            seen = b["seen"].setdefault(key, {})
            if s == "processing" and "startedAt" not in seen:
                seen["startedAt"] = now
            if s in ("done", "error", "cancelled") and "finishedAt" not in seen:
                seen["finishedAt"] = now
                seen["status"] = s
        b["lastCounts"] = counts
        print(f"{name}: {counts}")
    save_state(state)


def _secs(a: str, b: str) -> float:
    from datetime import datetime
    f = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.strptime(b, f) - datetime.strptime(a, f)).total_seconds()


def tier(pages: int) -> str:
    return "small <20p" if pages < 20 else ("medium 20-39p" if pages < 40 else ("large 40-99p" if pages < 100 else "mega 100p+"))


def report() -> None:
    state = load_state()
    lines = ["# Scale test report", ""]
    for name, b in state["batches"].items():
        path = OUT / f"job-{name}.json"
        if not path.exists():
            continue
        job = json.loads(path.read_text())
        pages_by_idx = {s["fileIndex"]: s["pages"] for s in b["files"]}
        rows = []
        for f in job.get("files", []):
            idx = f.get("fileIndex")
            seen = b["seen"].get(str(idx), {})
            dur = _secs(seen["startedAt"], seen["finishedAt"]) if "startedAt" in seen and "finishedAt" in seen else None
            rows.append({"idx": idx, "name": f.get("fileName"), "pages": pages_by_idx.get(idx, 0),
                         "status": f.get("status"), "rows": len(f.get("rows") or []),
                         "noUses": bool(f.get("noUses")), "qc": (f.get("qcReport") or {}).get("overall"),
                         "error": (f.get("error") or "")[:120], "minutes": round(dur / 60, 1) if dur else None})
        settled = [r for r in rows if r["status"] in ("done", "error", "cancelled")]
        done = [r for r in rows if r["status"] == "done"]
        span = None
        fins = [s["finishedAt"] for s in b["seen"].values() if "finishedAt" in s]
        if fins:
            span = round(_secs(b["submittedAt"], max(fins)) / 3600, 2)
        lines += [f"## Batch {name} — {b['n']} labels", "",
                  f"- settled {len(settled)}/{len(rows)}, done {len(done)}, "
                  f"error {sum(r['status']=='error' for r in rows)}, "
                  f"budget-blocked {sum('budget' in r['error'].lower() for r in rows)}",
                  f"- wall clock to last settled file: {span} h" if span else "- wall clock: n/a", ""]
        by_tier: dict[str, list] = {}
        for r in rows:
            by_tier.setdefault(tier(r["pages"]), []).append(r)
        lines += ["| Tier | Files | Done | Error | Avg rows | Avg min/label | QC High/Critical |", "|---|---|---|---|---|---|---|"]
        for t in ("small <20p", "medium 20-39p", "large 40-99p", "mega 100p+"):
            rs = by_tier.get(t, [])
            if not rs:
                continue
            d = [r for r in rs if r["status"] == "done"]
            mins = [r["minutes"] for r in rs if r["minutes"]]
            lines.append(f"| {t} | {len(rs)} | {len(d)} | {sum(r['status']=='error' for r in rs)} | "
                         f"{round(sum(r['rows'] for r in d)/len(d),1) if d else '-'} | "
                         f"{round(sum(mins)/len(mins),1) if mins else '-'} | "
                         f"{sum(r['qc'] in ('High','Critical') for r in d)} |")
        lines += ["", "| # | Pages | Status | Rows | QC | Min | Label / error |", "|---|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: r["idx"]):
            label = r["name"] + (f" — {r['error']}" if r["status"] == "error" else "") + (" (no uses)" if r["noUses"] else "")
            lines.append(f"| {r['idx']} | {r['pages']} | {r['status']} | {r['rows']} | {r['qc'] or '-'} | {r['minutes'] or '-'} | {label} |")
        lines.append("")
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "submit":
        submit(sys.argv[2], int(sys.argv[3]))
    elif cmd == "submit-files":
        submit(sys.argv[2], 0, sys.argv[3:])
    elif cmd == "snapshot":
        snapshot()
    elif cmd == "report":
        report()
    else:
        sys.exit(__doc__)

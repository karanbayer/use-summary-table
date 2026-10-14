#!/usr/bin/env python3
"""Scale + accuracy report from Cloudflare background jobs (+ offline sizing).

Accuracy without a golden table per label uses *proxies* that work on any label:
  - reliability: done vs error, error class
  - QC: Clean/High/Unavailable
  - rate_gap: Evidence/Additional Info has fl oz|qt|/A or lb AE, but App Rate is NS
  - ns_rate_share: fraction of rate cells that are NS
  - golden_hit_rate: only when samples/expected has a match (e.g. Sivanto 400 SL)

Stratifies by pages, wave, tier (small/large/mega) so you can see how accuracy
and reliability change with scale — not only wall-clock/$ .
"""

from __future__ import annotations

import json
import re
import statistics
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://use-summary-table.pages.dev"
PILOT = "ust-pilot-2026"
ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "samples" / "scale" / "_report"
SCALE = ROOT / "samples" / "scale"

RATE_COLS = [
    "App Rate (lb ai/A)",
    "A.I. Max Single Rate/App. (lb a.i./A)",
    "A.I. Max Total Rate/C.C. (lb a.i./A)",
    "A.I. Max Total Rate/Yr. (lb a.i./A)",
]
PRODUCT_UNIT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|fluid\s+ounces?|quarts?|qt)\b[^.]{0,40}?"
    r"(?:per\s+acre|/\s*A\b)",
    re.I,
)
AE_LB_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\s+(?:glyphosate\s+)?"
    r"(?:acid\s+)?equivalent\b",
    re.I,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get_job(job_id: str) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}/api/jobs/{job_id}",
        headers={
            "x-ust-pilot": PILOT,
            "accept": "application/json",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "referer": f"{BASE_URL}/",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())


def classify_error(err: str) -> str:
    e = (err or "").lower()
    if "403" in e or "aws credentials" in e or "bedrock" in e:
        return "gateway_auth_403"
    if "input was not found" in e or "expired" in e:
        return "kv_input_missing"
    if "no rows" in e or "produced no rows" in e:
        return "empty_extract"
    if "budget" in e:
        return "budget"
    if "rate limit" in e:
        return "rate_limit"
    if "stream" in e:
        return "stream_drop"
    if err:
        return "other_error"
    return "none"


def tier_for_pages(pages: int) -> str:
    if pages >= 100:
        return "mega"
    if pages >= 20:
        return "large"
    return "small"


def is_ns(v) -> bool:
    s = str(v or "").strip()
    return (not s) or s.upper() in ("NS", "NA", "NOT_SPECIFIED")


def rate_gap_score(rows: list[dict]) -> dict:
    """Proxy accuracy: product/AE units in text but App Rate still NS."""
    if not rows:
        return {"rows": 0, "gap_rows": 0, "gap_rate": None, "ns_rate_cells": 0, "rate_cells": 0}
    gap = 0
    ns_cells = 0
    rate_cells = 0
    for r in rows:
        blob = " ".join(
            str(r.get(k) or "")
            for k in ("Additional Information", "Evidence", "App Rate (lb ai/A)", "__source")
        )
        app = r.get("App Rate (lb ai/A)")
        has_units = bool(PRODUCT_UNIT_RE.search(blob) or AE_LB_RE.search(blob))
        if has_units and is_ns(app):
            gap += 1
        for col in RATE_COLS:
            rate_cells += 1
            if is_ns(r.get(col)):
                ns_cells += 1
    return {
        "rows": len(rows),
        "gap_rows": gap,
        "gap_rate": round(gap / len(rows), 3) if rows else None,
        "ns_rate_cells": ns_cells,
        "rate_cells": rate_cells,
        "ns_rate_share": round(ns_cells / rate_cells, 3) if rate_cells else None,
    }


def pages_from_offline(file_name: str) -> int | None:
    offline = REPORT / "scale-report.json"
    if not offline.exists():
        return None
    for f in json.loads(offline.read_text()).get("files") or []:
        if f.get("file_name") == file_name:
            return f.get("pages")
    return None


def analyze_file(wave: str, f: dict, offline_pages: int | None) -> dict:
    status = f.get("status") or "?"
    err = f.get("error") or ""
    rows = f.get("rows") if isinstance(f.get("rows"), list) else []
    qc = (f.get("qcReport") or {}) if isinstance(f.get("qcReport"), dict) else {}
    pages = offline_pages
    gaps = rate_gap_score(rows) if status == "done" else rate_gap_score([])
    return {
        "wave": wave,
        "fileName": f.get("fileName"),
        "status": status,
        "error_class": classify_error(err),
        "error": err[:200] if err else None,
        "pages": pages,
        "tier": tier_for_pages(pages or 0) if pages is not None else "unknown",
        "row_count": len(rows) if rows else 0,
        "qc_overall": qc.get("overall"),
        "qc_defects": len(qc.get("defects") or []),
        **gaps,
        # Accuracy placeholder until golden compare exists for this file
        "golden_accuracy": None,
        "accuracy_notes": (
            "no_rows"
            if status != "done"
            else (
                "proxy_only — no golden for this file; use gap_rate + qc_overall"
            )
        ),
    }


def stratify(files: list[dict], key: str) -> dict:
    buckets: dict[str, list] = defaultdict(list)
    for f in files:
        buckets[str(f.get(key) or "unknown")].append(f)
    out = {}
    for k, items in sorted(buckets.items(), key=lambda x: x[0]):
        done = [i for i in items if i["status"] == "done"]
        gaps = [i["gap_rate"] for i in done if i.get("gap_rate") is not None]
        ns = [i["ns_rate_share"] for i in done if i.get("ns_rate_share") is not None]
        out[k] = {
            "n": len(items),
            "done": len(done),
            "error": sum(1 for i in items if i["status"] == "error"),
            "success_rate": round(len(done) / len(items), 3) if items else 0,
            "avg_rows_when_done": round(statistics.mean(i["row_count"] for i in done), 1) if done else None,
            "avg_rate_gap_when_done": round(statistics.mean(gaps), 3) if gaps else None,
            "avg_ns_rate_share_when_done": round(statistics.mean(ns), 3) if ns else None,
            "qc_unavailable": sum(1 for i in done if i.get("qc_overall") == "Unavailable"),
            "error_classes": dict(
                sorted(
                    {
                        c: sum(1 for i in items if i["error_class"] == c)
                        for c in {i["error_class"] for i in items}
                    }.items(),
                    key=lambda x: -x[1],
                )
            ),
        }
    return out


def main() -> int:
    REPORT.mkdir(parents=True, exist_ok=True)
    files_out = []
    job_meta = {}
    for wave in ("A", "B", "C"):
        submit = REPORT / f"live-wave-{wave}.json"
        if not submit.exists():
            continue
        meta = json.loads(submit.read_text())
        job = http_get_job(meta["jobId"])
        (REPORT / f"live-wave-{wave}-status.json").write_text(json.dumps(job, indent=2))
        job_meta[wave] = {
            "jobId": job.get("jobId"),
            "status": job.get("status"),
            "watchUrl": f"{BASE_URL}/?job={job.get('jobId')}",
        }
        for f in job.get("files") or []:
            pages = pages_from_offline(f.get("fileName") or "")
            files_out.append(analyze_file(wave, f, pages))

    by_tier = stratify(files_out, "tier")
    by_wave = stratify(files_out, "wave")
    by_error = {}
    for f in files_out:
        by_error[f["error_class"]] = by_error.get(f["error_class"], 0) + 1

    # Page-bin stratification for scale curves
    def page_bin(p):
        if p is None:
            return "unknown"
        if p < 10:
            return "01-09p"
        if p < 20:
            return "10-19p"
        if p < 40:
            return "20-39p"
        if p < 100:
            return "40-99p"
        return "100p+"

    for f in files_out:
        f["page_bin"] = page_bin(f.get("pages"))
    by_pages = stratify(files_out, "page_bin")

    n = len(files_out)
    n_done = sum(1 for f in files_out if f["status"] == "done")
    report = {
        "generated_at": utc_now(),
        "jobs": job_meta,
        "summary": {
            "files": n,
            "done": n_done,
            "error": sum(1 for f in files_out if f["status"] == "error"),
            "processing": sum(1 for f in files_out if f["status"] == "processing"),
            "queued": sum(1 for f in files_out if f["status"] == "queued"),
            "success_rate": round(n_done / n, 3) if n else 0,
            "error_classes": by_error,
        },
        "accuracy_method": {
            "golden": "Cell/row match vs samples/expected/* when available (Sivanto 400 SL).",
            "proxies_any_label": [
                "success_rate (reliability)",
                "qc_overall (Clean/High/Unavailable)",
                "gap_rate: share of done rows where Evidence has fl oz/qt/AE but App Rate is NS",
                "ns_rate_share: share of rate-schema cells that are NS",
            ],
            "how_to_learn_unknown_labels": [
                "Do not hard-code product names. Flag rate_gap whenever product units appear beside NS lb ai/A.",
                "Always resolve concentration from ingredients (any wording) then convert arithmetic.",
                "QC must emit High RATE-UNIT-GAP when Evidence has product units and App Rate is NS.",
                "Add goldens only for a calibration subset; use proxies for the rest of the pack.",
            ],
            "scale_factors_tracked": [
                "page_bin / tier (small/large/mega)",
                "wave size / position in overnight queue",
                "error_class (auth vs empty extract vs stream)",
                "qc availability",
            ],
        },
        "by_wave": by_wave,
        "by_tier": by_tier,
        "by_page_bin": by_pages,
        "files": files_out,
        "verdict": None,
    }

    # Honest verdict for current run
    auth = by_error.get("gateway_auth_403", 0)
    empty = by_error.get("empty_extract", 0)
    if n_done == 0 and auth >= n * 0.5:
        report["verdict"] = (
            "FAILED — AI Gateway/Bedrock 403 (credentials) blocked most files. "
            "Accuracy vs scale cannot be measured until auth is fixed and jobs are retried."
        )
    elif n_done == 0:
        report["verdict"] = (
            "FAILED — no successful extracts. See error_classes. Retry after fixing root cause."
        )
    else:
        report["verdict"] = (
            f"PARTIAL — {n_done}/{n} done. Use by_page_bin / by_tier for reliability curves; "
            "gap_rate for rate-column accuracy proxy; add goldens for true accuracy."
        )

    json_path = REPORT / "scale-accuracy.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Scale + accuracy report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Jobs",
        "",
    ]
    for w, j in job_meta.items():
        lines.append(f"- Wave {w}: `{j['status']}` — {j['watchUrl']}")

    s = report["summary"]
    lines += [
        "",
        "## Reliability summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Files | {s['files']} |",
        f"| Done | {s['done']} |",
        f"| Error | {s['error']} |",
        f"| Processing / queued | {s['processing']} / {s['queued']} |",
        f"| Success rate | {s['success_rate']} |",
        "",
        "### Error classes",
        "",
    ]
    for k, v in sorted(by_error.items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`: {v}")

    lines += [
        "",
        "## Accuracy method (works on labels you have never seen)",
        "",
        "1. **Reliability** — did the file finish (`done`) with rows?",
        "2. **QC status** — Clean / High / Unavailable (Unavailable ≠ regulatory-final).",
        "3. **Rate-gap proxy** — Evidence mentions fl oz/qt/AE but `App Rate (lb ai/A)` is NS "
        "(under-extraction, not hallucination). No golden required.",
        "4. **Golden accuracy** — only for files with `samples/expected/*` (e.g. Sivanto 400 SL).",
        "",
        "Unknown future labels: do **not** special-case product names. "
        "Detect unit/rate mismatches mechanically, convert when concentration is on the label, "
        "and let QC raise `RATE-UNIT-GAP` when NS remains beside product units.",
        "",
        "## How metrics change with scale",
        "",
        "### By page bin",
        "",
        "| Pages | N | Success | Avg rows (done) | Avg rate-gap | Avg NS-rate share |",
        "|---|---|---|---|---|---|",
    ]
    for k, v in by_pages.items():
        lines.append(
            f"| {k} | {v['n']} | {v['success_rate']} | {v['avg_rows_when_done']} | "
            f"{v['avg_rate_gap_when_done']} | {v['avg_ns_rate_share_when_done']} |"
        )

    lines += [
        "",
        "### By tier",
        "",
        "| Tier | N | Success | Error classes |",
        "|---|---|---|---|",
    ]
    for k, v in by_tier.items():
        lines.append(f"| {k} | {v['n']} | {v['success_rate']} | `{v['error_classes']}` |")

    lines += [
        "",
        "### By wave",
        "",
        "| Wave | N | Success | Done rows avg |",
        "|---|---|---|---|",
    ]
    for k, v in by_wave.items():
        lines.append(f"| {k} | {v['n']} | {v['success_rate']} | {v['avg_rows_when_done']} |")

    lines += [
        "",
        "## Parameters that influence accuracy / reliability",
        "",
        "| Parameter | Effect |",
        "|---|---|",
        "| **Pages / mega tier** | More chunks → more Gateway calls → more stream/auth exposure; higher rate-gap risk if front-matter concentration is missed |",
        "| **Gateway auth health** | 403 Bedrock/credentials → success_rate collapses (this run) |",
        "| **Queue concurrency** | c=1 slower but more stable; c>1 can amplify 403/429 |",
        "| **Wave position / time** | Later files may hit budget/rate-limit or expired KV input |",
        "| **QC path** | Unavailable means rows exist but not regulatory-final |",
        "| **Unit conversion coverage** | Labels stating fl oz + lb/gal must convert; AE pounds on label must be preferred over NS |",
        "",
        "## Per-file detail",
        "",
        "| Wave | Tier | Pages | Status | Rows | QC | Rate-gap | Error class | File |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for f in sorted(files_out, key=lambda x: (x["wave"], x.get("pages") or 0)):
        lines.append(
            f"| {f['wave']} | {f['tier']} | {f.get('pages')} | {f['status']} | {f['row_count']} | "
            f"{f.get('qc_overall')} | {f.get('gap_rate')} | {f['error_class']} | {f['fileName']} |"
        )

    lines += [
        "",
        "## Next steps",
        "",
        "1. Fix Worker → AI Gateway Bedrock credentials (403) — without this, scale accuracy is undefined.",
        "2. Re-queue: `python3 scripts/scale_run_live.py --mode submit-all`",
        "3. Re-run this report: `python3 scripts/scale_accuracy_report.py`",
        "4. Add goldens for 3–5 calibration labels to convert proxy → true accuracy.",
        "",
        f"JSON: `{json_path.relative_to(ROOT)}`",
        "",
    ]

    md_path = REPORT / "scale-accuracy.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Refresh MORNING pointer
    morning = REPORT / "MORNING.md"
    note = (
        f"\n\n---\n\n## Accuracy / scale snapshot ({report['generated_at']})\n\n"
        f"{report['verdict']}\n\n"
        f"See `scale-accuracy.md` for curves by pages/tier/wave and the accuracy method "
        f"(golden + rate-gap proxy for unknown labels).\n"
    )
    if morning.exists():
        text = morning.read_text(encoding="utf-8")
        if "## Accuracy / scale snapshot" in text:
            text = text.split("## Accuracy / scale snapshot")[0].rstrip() + note
        else:
            text = text.rstrip() + note
        morning.write_text(text, encoding="utf-8")

    print(md_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

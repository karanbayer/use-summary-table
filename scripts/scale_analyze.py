#!/usr/bin/env python3
"""Offline scale model for Use Summary Tables extraction (no AI Gateway).

Mirrors worker/src/pipeline.js chunking + call structure so we can size
batches, concurrency, wall-clock, and daily budget without burning tokens.
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("Install pypdf: python3 -m pip install pypdf", file=sys.stderr)
    sys.exit(1)

# --- pipeline constants (keep in sync with worker/src/pipeline.js) ---
EXTRACT_CHUNK_CHARS_LARGE = 35_000
EXTRACT_FRONT_MATTER_MAX_PAGES = 8
DETAIL_SKELETON_BATCH = 6
FORCE_TWO_PASS_MIN_PAGES = 20
QC_MAX_ATTEMPTS = 3  # worst case; model assumes 1 success
QC_MAX_CHARS = 150_000
QC_MAX_CHARS_LARGE = 80_000
WORKER_MAX_CONCURRENCY = 1  # worker/wrangler.toml
RATE_LIMIT_PER_MINUTE = 20
DAILY_BUDGET_USD = 100.0

# System knowledge ~56k chars ≈ 14k tokens (measured from knowledge-compiled.json)
SYSTEM_CHARS = 56_464
CHARS_PER_TOKEN = 4.0

# Sonnet pricing from worker governance.js
SONNET_IN_PER_MTOK = 3.0
SONNET_OUT_PER_MTOK = 15.0

# Calibrated mid-point latencies (seconds) from prior master-label runs
SEC_PASS1 = 75.0
SEC_PASS2 = 55.0
SEC_QC = 90.0
# Output token guesses when we don't know skeleton count yet
OUT_TOK_PASS1 = 2_500
OUT_TOK_PASS2 = 4_000
OUT_TOK_QC = 3_000

# Heuristic: expected use-rows from crop/use signal density in active chunks
ROWS_PER_ACTIVE_CHUNK_LO = 4
ROWS_PER_ACTIVE_CHUNK_HI = 18
ROWS_PER_ACTIVE_CHUNK_MID = 10


@dataclass
class FileModel:
    file_name: str
    pdf_bytes: int
    pages: int
    text_chars: int
    extract_ms: float
    mode: str  # single | two_pass
    chunks_total: int
    chunks_active: int
    chunks_barren: int
    est_rows_mid: int
    est_pass1_calls: int
    est_pass2_calls: int
    est_qc_calls: int
    est_gateway_calls: int
    est_input_tokens: int
    est_output_tokens: int
    est_cost_usd: float
    est_seconds_serial: float
    chunk_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def score_crop_use(text: str) -> int:
    if not text or len(text) < 80:
        return 0
    score = 0
    if re.search(r"\bTYPES?\s+OF\s+APPLICATIONS?\b", text, re.I):
        score += 2
    if re.search(r"\bUSE\s+INSTRUCTIONS\s*:", text, re.I):
        score += 2
    if re.search(r"\bMAXIMUM\s+(APPLICATION\s+)?RATES?\b", text, re.I):
        score += 2
    if re.search(
        r"\b(lb\.?\s*a\.?i\.?\.?\s*/\s*A|fl\.?\s*oz\.?\s*/\s*A|fluid\s+ounces?\s+per\s+acre)\b",
        text,
        re.I,
    ):
        score += 2
    if re.search(r"\bPHI\b|\bpreharvest\s+interval\b", text, re.I) and re.search(
        r"\b(day|days)\b", text, re.I
    ):
        score += 1
    if re.search(r"\bCROP\s+GROUP\b|\bCG\s*\d+", text, re.I):
        score += 1
    if re.search(
        r"\b(Citrus|Cotton|Soybean|Corn|Wheat|Alfalfa|Tree\s+Nuts|Pome\s+Fruit|"
        r"Stone\s+Fruit|Rice|Sorghum|Canola|Peanut|Sugarbeet|Potato|Vegetable|Berry|Grape)\b",
        text,
        re.I,
    ):
        score += 1
    if re.search(r"\bPERSONAL\s+PROTECTIVE\s+EQUIPMENT\b|\bENGINEERING\s+CONTROLS\b", text, re.I) and score < 3:
        return 0
    return score


def find_directions_start(pages: list[dict]) -> int:
    for i, p in enumerate(pages):
        if re.search(
            r"DIRECTIONS\s+FOR\s+USE|SPECIFIC\s+CROP\s+DIRECTIONS|SPECIFIC\s+USE\s+DIRECTIONS",
            p["text"],
            re.I,
        ):
            return i
    return 0


def find_crop_use_body_start(pages: list[dict]) -> int:
    dir_idx = find_directions_start(pages)
    for i in range(dir_idx, len(pages)):
        if score_crop_use(pages[i]["text"]) >= 3:
            return i
    return dir_idx


def wrap_chunk_body(front_matter: str, body_label: str, body_text: str) -> str:
    return "\n".join(
        [
            front_matter,
            "",
            f"--- CHUNK BODY ({body_label}) ---",
            "Scope: extract ONLY uses evidenced in CHUNK BODY.",
            "Front-matter = product identity — not a source of extra crops.",
            "",
            body_text,
        ]
    )


def extract_chunk_body(chunk_text: str) -> str:
    m = re.search(r"---\s*CHUNK BODY[^\n]*\n([\s\S]*)", chunk_text, re.I)
    return m.group(1) if m else chunk_text


def chunk_body_looks_barren(chunk_text: str) -> bool:
    body = extract_chunk_body(chunk_text)
    if not body.strip():
        return True
    if score_crop_use(body) >= 3:
        return False
    return not any(score_crop_use(block) >= 3 for block in re.split(r"---\s*PAGE\s+\d+\s*---", body, flags=re.I))


def build_page_window_chunks(pages: list[dict], front_matter: str, budget: int) -> list[dict]:
    body_start = find_crop_use_body_start(pages)
    front_end = min(
        len(pages),
        max(EXTRACT_FRONT_MATTER_MAX_PAGES, find_directions_start(pages) + 1, body_start),
    )
    body_pages = pages[front_end:]
    if not body_pages:
        text = "\n\n".join(f"--- PAGE {p['page']} ---\n{p['text']}" for p in pages)
        return [{"id": "full", "text": text}]
    chunks: list[dict] = []
    buf: list[dict] = []
    buf_len = len(front_matter)

    def flush() -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        body = "\n\n".join(f"--- PAGE {p['page']} ---\n{p['text']}" for p in buf)
        label = f"pages {buf[0]['page']}–{buf[-1]['page']}"
        chunks.append({"id": label, "text": wrap_chunk_body(front_matter, label, body)})
        buf = []
        buf_len = len(front_matter)

    for p in body_pages:
        block = f"--- PAGE {p['page']} ---\n{p['text']}"
        if buf and buf_len + len(block) > budget:
            flush()
        buf.append(p)
        buf_len += len(block)
    flush()
    return chunks


def build_extraction_chunks(page_marked: str, pages: list[dict]) -> tuple[str, list[dict]]:
    if not pages:
        return "single", [{"id": "full", "text": page_marked}]
    front_count = min(EXTRACT_FRONT_MATTER_MAX_PAGES, len(pages))
    front_matter = "\n\n".join(
        f"--- PAGE {p['page']} ---\n{p['text']}" for p in pages[:front_count]
    )
    if len(pages) < FORCE_TWO_PASS_MIN_PAGES and len(page_marked) <= EXTRACT_CHUNK_CHARS_LARGE:
        return "single", [{"id": "full", "text": page_marked}]
    return "two_pass", build_page_window_chunks(pages, front_matter, EXTRACT_CHUNK_CHARS_LARGE)


def pdf_to_pages(path: Path) -> tuple[list[dict], float]:
    t0 = time.perf_counter()
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            text = ""
            pages.append({"page": i, "text": text, "error": str(exc)})
            continue
        pages.append({"page": i, "text": text})
    return pages, (time.perf_counter() - t0) * 1000


def tokens(chars: int) -> int:
    return max(1, int(chars / CHARS_PER_TOKEN))


def cost_usd(in_tok: int, out_tok: int) -> float:
    return (in_tok / 1e6) * SONNET_IN_PER_MTOK + (out_tok / 1e6) * SONNET_OUT_PER_MTOK


def model_file(path: Path) -> FileModel:
    pages, extract_ms = pdf_to_pages(path)
    page_marked = "\n\n".join(f"--- PAGE {p['page']} ---\n{p['text']}" for p in pages)
    mode, chunks = build_extraction_chunks(page_marked, pages)

    active = []
    barren = []
    for ch in chunks:
        if mode == "two_pass" and len(chunks) > 1 and chunk_body_looks_barren(ch["text"]):
            barren.append(ch)
        else:
            active.append(ch)

    # Single-chunk path still does two-pass when large; for tiny single docs
    # worker still uses two-pass extractChunkTwoPass for large labels, and
    # one-shot path for small — approximate: single mode = 1 pass1 + 1 pass2 batch + QC
    if mode == "single":
        pass1 = 1
        # assume ~mid rows → one detail batch unless text looks dense
        density = score_crop_use(page_marked)
        est_rows = max(2, min(40, 2 + density * 2 + len(pages) // 3))
        pass2 = max(1, math.ceil(est_rows / DETAIL_SKELETON_BATCH))
    else:
        pass1 = len(active)
        est_rows = ROWS_PER_ACTIVE_CHUNK_MID * len(active)
        # barren-only edge case
        if not active:
            pass1 = 0
            est_rows = 0
            pass2 = 0
        else:
            pass2 = max(1, math.ceil(est_rows / DETAIL_SKELETON_BATCH))

    qc_calls = 1 if (active or mode == "single") else 0
    gateway_calls = pass1 + pass2 + qc_calls

    # Input tokens ≈ system + chunk text per call (QC may truncate)
    in_tok = 0
    for ch in active if active else chunks[:1]:
        chunk_tok = tokens(SYSTEM_CHARS + len(ch["text"]))
        in_tok += chunk_tok  # pass1
    # pass2 re-sends same chunk text per batch
    if active:
        avg_chunk = sum(len(c["text"]) for c in active) / len(active)
        in_tok += pass2 * tokens(SYSTEM_CHARS + int(avg_chunk) + 2_000)
    elif mode == "single":
        in_tok += pass2 * tokens(SYSTEM_CHARS + len(page_marked) + 2_000)

    qc_src = page_marked
    qc_cap = QC_MAX_CHARS_LARGE if len(pages) >= FORCE_TWO_PASS_MIN_PAGES else QC_MAX_CHARS
    qc_chars = min(len(qc_src), qc_cap)
    if qc_calls:
        in_tok += tokens(SYSTEM_CHARS + qc_chars + est_rows * 200)

    out_tok = pass1 * OUT_TOK_PASS1 + pass2 * OUT_TOK_PASS2 + qc_calls * OUT_TOK_QC
    seconds = pass1 * SEC_PASS1 + pass2 * SEC_PASS2 + qc_calls * SEC_QC

    notes = []
    empty_pages = sum(1 for p in pages if not (p["text"] or "").strip())
    if empty_pages:
        notes.append(f"{empty_pages}/{len(pages)} pages had no extractable text (may need OCR)")
    if mode == "two_pass" and barren:
        notes.append(f"{len(barren)} barren chunk(s) skipped")
    if len(page_marked) > 200_000:
        notes.append("very large label — QC truncation likely")

    return FileModel(
        file_name=path.name,
        pdf_bytes=path.stat().st_size,
        pages=len(pages),
        text_chars=len(page_marked),
        extract_ms=round(extract_ms, 1),
        mode=mode,
        chunks_total=len(chunks),
        chunks_active=len(active) if mode == "two_pass" else 1,
        chunks_barren=len(barren),
        est_rows_mid=est_rows,
        est_pass1_calls=pass1,
        est_pass2_calls=pass2,
        est_qc_calls=qc_calls,
        est_gateway_calls=gateway_calls,
        est_input_tokens=in_tok,
        est_output_tokens=out_tok,
        est_cost_usd=round(cost_usd(in_tok, out_tok), 4),
        est_seconds_serial=round(seconds, 1),
        chunk_ids=[c["id"] for c in chunks],
        notes=notes,
    )


def wall_clock(total_serial_s: float, concurrency: int, total_calls: int) -> dict:
    # Effective concurrency capped by worker + rate limit
    # Each call ~ mid of pass times; rate limit is per minute on submit side,
    # but Gateway calls during processing are sequential per file with max_concurrency.
    effective = max(1, concurrency)
    # Rate limit rarely binds once queued (20/min submissions); processing is the bottleneck.
    wall = total_serial_s / effective
    # Optional: if concurrency high, rate-limit Gateway to ~RATE_LIMIT_PER_MINUTE calls
    min_by_rate = (total_calls / RATE_LIMIT_PER_MINUTE) * 60.0
    return {
        "concurrency": effective,
        "wall_seconds": round(max(wall, min_by_rate if effective > 1 else wall), 1),
        "wall_hours": round(max(wall, min_by_rate if effective > 1 else wall) / 3600, 2),
        "rate_limit_floor_seconds": round(min_by_rate, 1),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    scale_dir = root / "samples" / "scale"
    out_dir = scale_dir / "_report"
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(scale_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {scale_dir}", file=sys.stderr)
        return 1

    print(f"Analyzing {len(pdfs)} PDFs (offline, no AI Gateway)…")
    models = [model_file(p) for p in pdfs]

    total_cost = sum(m.est_cost_usd for m in models)
    total_calls = sum(m.est_gateway_calls for m in models)
    total_serial = sum(m.est_seconds_serial for m in models)
    total_pages = sum(m.pages for m in models)
    total_chars = sum(m.text_chars for m in models)
    two_pass = [m for m in models if m.mode == "two_pass"]
    single = [m for m in models if m.mode == "single"]
    ocr_risk = [m for m in models if any("OCR" in n for n in m.notes)]

    scenarios = {
        "current_worker_c1": wall_clock(total_serial, 1, total_calls),
        "hypothetical_c2": wall_clock(total_serial, 2, total_calls),
        "hypothetical_c3": wall_clock(total_serial, 3, total_calls),
        "hypothetical_c5": wall_clock(total_serial, 5, total_calls),
    }

    # How many labels fit in $100 / day at this cost mix
    avg_cost = total_cost / len(models) if models else 0
    labels_per_budget = int(DAILY_BUDGET_USD // avg_cost) if avg_cost else 0
    # Wave sizes for practical runs under budget + overnight windows
    waves = []
    for n in (5, 10, 15, 20, 29):
        if n > len(models):
            continue
        subset = models[:n]  # alphabetical — also report by size tiers
        cost = sum(m.est_cost_usd for m in subset)
        serial = sum(m.est_seconds_serial for m in subset)
        calls = sum(m.est_gateway_calls for m in subset)
        waves.append(
            {
                "n": n,
                "est_cost_usd": round(cost, 2),
                "est_gateway_calls": calls,
                "wall_c1_hours": round(serial / 3600, 2),
                "wall_c2_hours": round(wall_clock(serial, 2, calls)["wall_hours"], 2),
                "fits_daily_budget": cost <= DAILY_BUDGET_USD,
            }
        )

    # Size tiers for smarter batching
    by_pages = sorted(models, key=lambda m: m.pages)
    tiers = {
        "small_lt20p": [m.file_name for m in by_pages if m.pages < 20],
        "medium_20_40p": [m.file_name for m in by_pages if 20 <= m.pages < 40],
        "large_40p_plus": [m.file_name for m in by_pages if m.pages >= 40],
    }

    # Recommended knobs
    recommendations = [
        {
            "param": "worker max_concurrency",
            "current": WORKER_MAX_CONCURRENCY,
            "recommend": 2 if total_cost <= DAILY_BUDGET_USD * 0.8 else 1,
            "why": "c=1 is safest for Gateway stability; c=2 halves wall time if Gateway holds. Do not jump to 5 until a 5-label pilot succeeds at c=2.",
        },
        {
            "param": "batch wave size",
            "current": "all-at-once",
            "recommend": 10 if labels_per_budget >= 10 else max(5, labels_per_budget // 2 or 5),
            "why": f"Avg ~${avg_cost:.2f}/label → ~{labels_per_budget} labels/day under ${DAILY_BUDGET_USD:.0f}. Wave so a failure doesn't burn the whole day.",
        },
        {
            "param": "DETAIL_SKELETON_BATCH",
            "current": DETAIL_SKELETON_BATCH,
            "recommend": 6,
            "why": "Keep 6 — larger batches risk max_tokens truncation; smaller increases Pass-2 call count linearly.",
        },
        {
            "param": "EXTRACT_CHUNK_CHARS_LARGE",
            "current": EXTRACT_CHUNK_CHARS_LARGE,
            "recommend": EXTRACT_CHUNK_CHARS_LARGE,
            "why": "35k is the stability tradeoff already chosen for master labels; raising it increases Pass-1 failure rate more than it saves calls.",
        },
        {
            "param": "submit strategy",
            "current": "mixed sizes together",
            "recommend": "small→medium→large waves",
            "why": "Small labels finish fast and validate the pipe; park 40p+ masters in a separate overnight wave.",
        },
        {
            "param": "DAILY_BUDGET_USD",
            "current": DAILY_BUDGET_USD,
            "recommend": max(DAILY_BUDGET_USD, math.ceil(total_cost * 1.25)),
            "why": f"Full 29-label pack estimates ${total_cost:.2f}; need headroom for QC retries/remediation.",
        },
    ]

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "offline_scale_model_no_gateway",
        "assumptions": {
            "sec_pass1": SEC_PASS1,
            "sec_pass2": SEC_PASS2,
            "sec_qc": SEC_QC,
            "rows_per_active_chunk_mid": ROWS_PER_ACTIVE_CHUNK_MID,
            "system_chars": SYSTEM_CHARS,
            "pricing": "sonnet $3/$15 per MTok",
            "note": "Costs/times are mid estimates. Real Gateway runs ±40% depending on skeleton counts and stream health.",
        },
        "corpus": {
            "files": len(models),
            "total_pages": total_pages,
            "total_text_chars": total_chars,
            "total_pdf_mb": round(sum(m.pdf_bytes for m in models) / 1e6, 2),
            "single_pass_files": len(single),
            "two_pass_files": len(two_pass),
            "ocr_risk_files": len(ocr_risk),
            "pdf_text_extract_ms_total": round(sum(m.extract_ms for m in models), 1),
            "pdf_text_extract_ms_p50": round(statistics.median(m.extract_ms for m in models), 1),
        },
        "totals": {
            "est_gateway_calls": total_calls,
            "est_input_tokens": sum(m.est_input_tokens for m in models),
            "est_output_tokens": sum(m.est_output_tokens for m in models),
            "est_cost_usd": round(total_cost, 2),
            "est_rows_mid": sum(m.est_rows_mid for m in models),
            "est_serial_hours": round(total_serial / 3600, 2),
            "avg_cost_per_label_usd": round(avg_cost, 2),
            "labels_per_day_at_budget": labels_per_budget,
            "budget_usd": DAILY_BUDGET_USD,
            "full_pack_fits_daily_budget": total_cost <= DAILY_BUDGET_USD,
        },
        "wall_clock_scenarios": scenarios,
        "wave_sizing": waves,
        "tiers": {k: {"count": len(v), "files": v} for k, v in tiers.items()},
        "recommendations": recommendations,
        "files": [asdict(m) for m in sorted(models, key=lambda x: -x.est_cost_usd)],
    }

    json_path = out_dir / "scale-report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human-readable summary
    lines = [
        "# Scale analysis (offline — no AI Gateway)",
        "",
        f"Corpus: **{len(models)} PDFs**, {total_pages} pages, {report['corpus']['total_pdf_mb']} MB.",
        f"PDF text extract (local): **{report['corpus']['pdf_text_extract_ms_total']:.0f} ms** total "
        f"(p50 {report['corpus']['pdf_text_extract_ms_p50']:.0f} ms/file).",
        "",
        "## Headline estimates",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Est. Gateway calls | {total_calls} |",
        f"| Est. cost (Sonnet mid) | ${total_cost:.2f} |",
        f"| Avg $/label | ${avg_cost:.2f} |",
        f"| Labels/day @ ${DAILY_BUDGET_USD:.0f} budget | ~{labels_per_budget} |",
        f"| Wall clock @ concurrency=1 (current Worker) | {scenarios['current_worker_c1']['wall_hours']} h |",
        f"| Wall clock @ concurrency=2 | {scenarios['hypothetical_c2']['wall_hours']} h |",
        f"| Wall clock @ concurrency=3 | {scenarios['hypothetical_c3']['wall_hours']} h |",
        f"| Two-pass (master) files | {len(two_pass)} |",
        f"| Single-chunk files | {len(single)} |",
        f"| OCR-risk files | {len(ocr_risk)} |",
        "",
        "## Wave sizing",
        "",
        "| N labels | Est. $ | Calls | Hours c=1 | Hours c=2 | Fits $100? |",
        "|---|---|---|---|---|---|",
    ]
    for w in waves:
        lines.append(
            f"| {w['n']} | ${w['est_cost_usd']:.2f} | {w['est_gateway_calls']} | "
            f"{w['wall_c1_hours']} | {w['wall_c2_hours']} | {'yes' if w['fits_daily_budget'] else 'NO'} |"
        )

    lines += [
        "",
        "## Recommended scaling parameters",
        "",
    ]
    for r in recommendations:
        lines.append(f"- **{r['param']}**: `{r['current']}` → **`{r['recommend']}`** — {r['why']}")

    lines += [
        "",
        "## Tiers",
        "",
        f"- Small (<20p): {len(tiers['small_lt20p'])}",
        f"- Medium (20–39p): {len(tiers['medium_20_40p'])}",
        f"- Large (40p+): {len(tiers['large_40p_plus'])}",
        "",
        "## Top 10 cost drivers",
        "",
        "| File | Pages | Mode | Chunks (active/barren) | Est. calls | Est. $ | Est. min |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in sorted(models, key=lambda x: -x.est_cost_usd)[:10]:
        lines.append(
            f"| {m.file_name} | {m.pages} | {m.mode} | {m.chunks_active}/{m.chunks_barren} | "
            f"{m.est_gateway_calls} | ${m.est_cost_usd:.2f} | {m.est_seconds_serial/60:.0f} |"
        )

    if ocr_risk:
        lines += ["", "## OCR risk", ""]
        for m in ocr_risk:
            lines.append(f"- {m.file_name}: {', '.join(m.notes)}")

    lines += [
        "",
        "## Practical run plan (fastest path to real numbers)",
        "",
        "1. Wave A (validate): 5 smallest labels, Worker c=1 — confirm queue + QC.",
        "2. Wave B (scale): next 10 medium — measure real $/label and min/label.",
        "3. Wave C (stress): large/master labels overnight, still c=1 unless Wave B was clean at c=2.",
        "4. Recalibrate this model from Wave A/B actuals (replace SEC_* and row heuristics).",
        "",
        f"Full JSON: `{json_path.relative_to(root)}`",
        "",
    ]

    md_path = out_dir / "scale-report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Compact CSV for spreadsheets
    csv_path = out_dir / "scale-files.csv"
    cols = [
        "file_name",
        "pages",
        "text_chars",
        "mode",
        "chunks_total",
        "chunks_active",
        "chunks_barren",
        "est_rows_mid",
        "est_gateway_calls",
        "est_cost_usd",
        "est_seconds_serial",
    ]
    with csv_path.open("w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for m in sorted(models, key=lambda x: x.file_name):
            row = [str(getattr(m, c)) for c in cols]
            f.write(",".join(row) + "\n")

    print(md_path.read_text(encoding="utf-8"))
    print(f"\nWrote:\n  {md_path}\n  {json_path}\n  {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate the 30-minute stakeholder presentation deck."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

OUT = Path(__file__).with_name("Use-Summary-Tables-Stakeholder-30min.pptx")

NAVY = RGBColor(16, 39, 67)
BLUE = RGBColor(0, 102, 178)
TEAL = RGBColor(0, 146, 145)
GREEN = RGBColor(38, 139, 95)
AMBER = RGBColor(221, 142, 35)
RED = RGBColor(190, 63, 63)
INK = RGBColor(40, 50, 62)
MUTED = RGBColor(91, 105, 120)
PALE = RGBColor(244, 247, 250)
PALE_BLUE = RGBColor(230, 241, 250)
PALE_TEAL = RGBColor(226, 246, 244)
PALE_AMBER = RGBColor(253, 244, 225)
PALE_RED = RGBColor(253, 237, 237)
PALE_GREEN = RGBColor(235, 247, 239)
WHITE = RGBColor(255, 255, 255)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]


def set_bg(slide, color=WHITE):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def rect(slide, x, y, w, h, fill, line=None, radius=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    s = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = line or fill
    if radius:
        s.adjustments[0] = 0.08
    return s


def text(slide, value, x, y, w, h, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT, font="Aptos", valign=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = value
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def bullets(slide, items, x, y, w, h, size=16, color=INK, gap=8):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.04)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.level = 0
        p.font.name = "Aptos"
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.space_after = Pt(gap)
        p.bullet = True
    return box


def title(slide, kicker, heading, subtitle=None):
    text(slide, kicker.upper(), 0.65, 0.32, 12, 0.25, 11, BLUE, True)
    text(slide, heading, 0.65, 0.62, 12, 0.55, 28, NAVY, True)
    if subtitle:
        text(slide, subtitle, 0.68, 1.22, 11.8, 0.35, 14, MUTED)
    rect(slide, 0.65, 1.68, 1.0, 0.05, TEAL)


def footer(slide, number, total=16):
    text(slide, "Use Summary Tables Extractor  ·  Stakeholder presentation", 0.65, 7.15, 9.5, 0.2, 9, MUTED)
    text(slide, f"{number} / {total}", 11.6, 7.14, 1.0, 0.2, 9, MUTED, False, PP_ALIGN.RIGHT)


def add_slide(kicker, heading, subtitle=None, bg=WHITE):
    slide = prs.slides.add_slide(blank)
    set_bg(slide, bg)
    title(slide, kicker, heading, subtitle)
    footer(slide, len(prs.slides))
    return slide


def card(slide, x, y, w, h, heading, body, color=BLUE, fill=PALE):
    rect(slide, x, y, w, h, fill, fill, True)
    rect(slide, x, y, 0.08, h, color, color)
    text(slide, heading, x + 0.22, y + 0.16, w - 0.38, 0.32, 15, NAVY, True)
    text(slide, body, x + 0.22, y + 0.52, w - 0.4, h - 0.68, 13, INK)


def node(slide, x, y, w, h, label, fill=PALE_BLUE, color=NAVY):
    rect(slide, x, y, w, h, fill, fill, True)
    text(slide, label, x + 0.06, y + 0.08, w - 0.12, h - 0.16, 12, color, True, PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)


def arrow(slide, x1, y1, x2, y2, color=BLUE):
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    line.line.color.rgb = color
    line.line.width = Pt(1.6)
    line.line.end_arrowhead = True
    return line


# ---------------------------------------------------------------------------
# 1 · Title
# ---------------------------------------------------------------------------
slide = prs.slides.add_slide(blank)
set_bg(slide, NAVY)
rect(slide, 0, 0, 0.18, 7.5, TEAL)
text(slide, "STAKEHOLDER PRESENTATION  ·  30 MINUTES", 0.7, 1.15, 11, 0.3, 12, RGBColor(152, 218, 216), True)
text(slide, "Use Summary Tables\nExtractor", 0.7, 1.7, 10, 1.6, 40, WHITE, True)
text(slide, "From pesticide-label PDF → EPA-ready Use Summary Table,\nin minutes — with human review built in.", 0.72, 3.55, 10.5, 0.8, 20, RGBColor(220, 232, 241))
text(slide, "Karandeep Singh  ·  Bayer Life Sciences Regulatory  ·  BEAT04090032", 0.72, 5.55, 10, 0.3, 14, RGBColor(188, 207, 222))
text(slide, "Production AI agent  ·  Governed  ·  Traceable  ·  Human-in-the-loop", 0.72, 6.15, 10, 0.3, 13, RGBColor(160, 184, 201))
footer(slide, 1)

# ---------------------------------------------------------------------------
# 2 · Agenda
# ---------------------------------------------------------------------------
slide = add_slide("01 / Agenda", "How we will spend 30 minutes")
agenda = [
    ("05 min", "Why this matters", "The problem and the cost of the status quo"),
    ("07 min", "What we built", "Solution, user journey, and what the table looks like"),
    ("07 min", "How it works", "Architecture, AI control loop, deployment & credits"),
    ("05 min", "Value & proof", "Cost then vs now, accuracy, business impact"),
    ("06 min", "Demo / discussion", "Live path + decisions we need from stakeholders"),
]
for i, (t, h, b) in enumerate(agenda):
    y = 2.0 + i * 0.85
    rect(slide, 0.8, y, 1.35, 0.62, TEAL if i % 2 == 0 else BLUE, None, True)
    text(slide, t, 0.8, y + 0.16, 1.35, 0.35, 14, WHITE, True, PP_ALIGN.CENTER)
    text(slide, h, 2.4, y + 0.05, 4.0, 0.3, 18, NAVY, True)
    text(slide, b, 2.4, y + 0.35, 9.5, 0.3, 14, MUTED)

# ---------------------------------------------------------------------------
# 3 · Why
# ---------------------------------------------------------------------------
slide = add_slide("02 / Why this exists", "EPA submissions need a structured Use Summary Table",
                  "That information lives in long pesticide-label PDFs — not in a form regulators can reuse.")
card(slide, 0.75, 2.05, 3.8, 3.5,
     "What EPA needs",
     "A 28-column Use Summary Table: every crop / use site, application method, rates (lb ai/A), maxima per cycle and year, REI, PHI, PPE, and restrictions.",
     BLUE, PALE_BLUE)
card(slide, 4.8, 2.05, 3.8, 3.5,
     "Where the data lives today",
     "Scattered across narrative sections, rate tables, footnotes, appendices, and safety text — often over 100+ pages per label.",
     AMBER, PALE_AMBER)
card(slide, 8.85, 2.05, 3.8, 3.5,
     "Who feels the pain",
     "Regulatory managers who build the table by hand before submission. Field and agronomy staff who need the same facts in one place.",
     TEAL, PALE_TEAL)

# ---------------------------------------------------------------------------
# 4 · Current situation / problem
# ---------------------------------------------------------------------------
slide = add_slide("03 / Current situation", "Manual extraction is the bottleneck",
                  "Before this system, building the table meant reading the whole label and typing every use.")
card(slide, 0.75, 2.05, 3.8, 2.9, "Slow",
     "Regulatory managers spent 100+ hours building EPA Use Summary Tables by hand from pesticide-label PDFs.",
     RED, PALE_RED)
card(slide, 4.8, 2.05, 3.8, 2.9, "Error-prone",
     "Easy to miss footnotes, appendices, conditional rates, or crop-specific restrictions. Different analysts can interpret the same label differently.",
     AMBER, PALE_AMBER)
card(slide, 8.85, 2.05, 3.8, 2.9, "Hard to reuse",
     "Knowledge stays locked in documents and spreadsheets. Every new submission often starts from scratch.",
     BLUE, PALE_BLUE)
text(slide, "Business consequence: slower submissions, rework, and limited confidence in downstream regulatory data.",
     0.9, 5.4, 11.5, 0.5, 18, NAVY, True, PP_ALIGN.CENTER)

# ---------------------------------------------------------------------------
# 5 · Solution
# ---------------------------------------------------------------------------
slide = add_slide("04 / The solution", "An AI agent that drafts the table — people still decide",
                  "One label in. One reviewable, EPA-aligned table out. Nothing ships without human sign-off.")
nodes = [
    ("Pesticide\nlabel PDF", PALE_BLUE, NAVY),
    ("AI extraction\n+ independent QC", PALE_TEAL, TEAL),
    ("28-column\nschema table", PALE_AMBER, AMBER),
    ("Human review\n& edit", PALE_GREEN, GREEN),
    ("Excel\nexport", PALE_BLUE, BLUE),
]
for i, (label, fill, color) in enumerate(nodes):
    x = 0.7 + i * 2.5
    node(slide, x, 2.3, 2.15, 1.15, label, fill, color)
    if i < 4:
        arrow(slide, x + 2.15, 2.88, x + 2.4, 2.88)
card(slide, 0.75, 4.0, 3.8, 1.85, "What changed",
     "Managers spot-check an AI draft in minutes instead of building the table from a blank sheet.",
     TEAL, PALE_TEAL)
card(slide, 4.8, 4.0, 3.8, 1.85, "What did not change",
     "A human still owns the final table. The tool never submits to EPA or writes external systems.",
     BLUE, PALE_BLUE)
card(slide, 8.85, 4.0, 3.8, 1.85, "Design principle",
     "Useful because it is inspectable — every cell can be traced to source page and label text.",
     GREEN, PALE_GREEN)

# ---------------------------------------------------------------------------
# 6 · User journey / process
# ---------------------------------------------------------------------------
slide = add_slide("05 / The process", "Built around how regulatory reviewers actually work")
steps = [
    ("1", "Upload", "One or more\nlabel PDFs"),
    ("2", "Extract", "AI drafts rows\n(+ QC loop)"),
    ("3", "Inspect", "Search, filter,\nexpand evidence"),
    ("4", "Correct", "Edit cells;\nedits are marked"),
    ("5", "Export", "Excel workbook\nready for review"),
]
for i, (num, head, body) in enumerate(steps):
    x = 0.85 + i * 2.45
    rect(slide, x + 0.35, 2.15, 0.9, 0.7, TEAL, TEAL, True)
    text(slide, num, x + 0.35, 2.28, 0.9, 0.4, 22, WHITE, True, PP_ALIGN.CENTER)
    text(slide, head, x, 3.1, 1.7, 0.35, 16, NAVY, True, PP_ALIGN.CENTER)
    text(slide, body, x - 0.1, 3.5, 1.9, 0.7, 13, MUTED, False, PP_ALIGN.CENTER)
    if i < 4:
        arrow(slide, x + 1.55, 2.5, x + 2.2, 2.5)
text(slide, "The model proposes. The application validates. The analyst decides.",
     1.0, 4.7, 11.3, 0.4, 20, NAVY, True, PP_ALIGN.CENTER)
bullets(slide, [
    "Confidence badges and coverage warnings point reviewers to risk first",
    "Row expansion shows page number + original label wording for every value",
    "NS = label silent · NA = field does not apply — the tool does not invent values",
], 1.2, 5.3, 10.8, 1.4, 14, INK, 6)

# ---------------------------------------------------------------------------
# 7 · Output / schema
# ---------------------------------------------------------------------------
slide = add_slide("06 / What it produces", "A schema-compliant Use Summary Table — not a free-form summary",
                  "One row = one use + one use site + one set of application instructions.")
groups = [
    ("Product", "Reg. #, form,\nPBN / ABN", BLUE, PALE_BLUE),
    ("Site", "Use / crop,\nuse site", TEAL, PALE_TEAL),
    ("Application", "Target, type,\nequipment, timing", AMBER, PALE_AMBER),
    ("Rates", "lb ai/A, maxima,\nMRI, REI, PHI, PPE", GREEN, PALE_GREEN),
    ("Restrictions", "Geographic, drift,\nsoil, and more", RED, PALE_RED),
]
for i, (h, b, c, f) in enumerate(groups):
    x = 0.7 + i * 2.5
    rect(slide, x, 2.1, 2.3, 2.35, f, f, True)
    text(slide, h, x + 0.1, 2.3, 2.1, 0.4, 16, c, True, PP_ALIGN.CENTER)
    text(slide, b, x + 0.1, 2.85, 2.1, 1.3, 14, INK, False, PP_ALIGN.CENTER)
rect(slide, 0.75, 4.75, 11.8, 1.55, PALE, PALE, True)
text(slide, "Proven on a representative label", 1.0, 4.95, 11.3, 0.3, 14, TEAL, True)
text(slide, "149 pages → 155 rows × 28 columns  ·  ~88% field-level accuracy vs an expert table  ·  source text kept on every cell",
     1.0, 5.4, 11.3, 0.55, 18, NAVY, True)

# ---------------------------------------------------------------------------
# 8 · Architecture overview
# ---------------------------------------------------------------------------
slide = add_slide("07 / Architecture", "Document reading, model reasoning, validation, and human approval — separated on purpose")
# Top flow
flow = [
    ("Browser UI", "Upload · review\n· edit · export"),
    ("API / relay", "Pilot gate ·\ngovernance"),
    ("AI Gateway", "Entra M2M ·\nteam budget"),
    ("Claude models", "Sonnet extract/QC\nOpus remediate"),
    ("Human + Excel", "Spot-check ·\ndownload"),
]
for i, (h, b) in enumerate(flow):
    x = 0.55 + i * 2.55
    node(slide, x, 2.05, 2.25, 1.25, f"{h}\n{b}", PALE_BLUE if i % 2 == 0 else PALE_TEAL, NAVY if i % 2 == 0 else TEAL)
    if i < 4:
        arrow(slide, x + 2.25, 2.67, x + 2.45, 2.67)
card(slide, 0.75, 3.7, 3.8, 2.4, "Two extraction modes",
     "AI-assisted (default): governed model path for hard labels.\nDeterministic (offline): regex/heuristic fallback when credits or gateway are unavailable.",
     BLUE, PALE_BLUE)
card(slide, 4.8, 3.7, 3.8, 2.4, "Background jobs",
     "Soft-async queue on Agentrix so long labels can run after the tab closes. Requires minScale = 1 so the pod is not scaled to zero mid-job.",
     TEAL, PALE_TEAL)
card(slide, 8.85, 3.7, 3.8, 2.4, "What stays local",
     "PDF text/OCR in the browser. Review UI and Excel export never need the model. Label text is treated as data, not instructions.",
     GREEN, PALE_GREEN)

# ---------------------------------------------------------------------------
# 9 · AI control loop
# ---------------------------------------------------------------------------
slide = add_slide("08 / AI control loop", "The model is one stage inside a bounded workflow — not a black box")
stages = [
    ("1", "Extract", "Sonnet drafts\nstructured rows", BLUE, PALE_BLUE),
    ("2", "Independent QC", "Fresh conversation\nchecks the draft", TEAL, PALE_TEAL),
    ("3", "Remediate", "Opus only if\nHigh / Critical", AMBER, PALE_AMBER),
    ("4", "Validate", "Schema · pages ·\nevidence checks", GREEN, PALE_GREEN),
    ("5", "Human", "Review · edit ·\nexport", NAVY, PALE),
]
for i, (num, h, b, c, f) in enumerate(stages):
    x = 0.55 + i * 2.55
    rect(slide, x, 2.05, 2.3, 2.5, f, f, True)
    rect(slide, x + 0.75, 2.25, 0.8, 0.45, c, c, True)
    text(slide, num, x + 0.75, 2.3, 0.8, 0.35, 16, WHITE, True, PP_ALIGN.CENTER)
    text(slide, h, x + 0.1, 2.9, 2.1, 0.4, 15, NAVY, True, PP_ALIGN.CENTER)
    text(slide, b, x + 0.1, 3.4, 2.1, 0.9, 13, MUTED, False, PP_ALIGN.CENTER)
    if i < 4:
        arrow(slide, x + 2.3, 3.2, x + 2.5, 3.2, c)
text(slide, "Remediation is capped (≤2 cycles). Serious defects stay visible for the reviewer — we never hide uncertainty behind a clean-looking table.",
     0.9, 5.0, 11.5, 0.7, 16, NAVY, True, PP_ALIGN.CENTER)
text(slide, "Models via Bayer AI Gateway: anthropic/claude-sonnet-5  ·  anthropic/claude-opus-5 (escalation only)",
     0.9, 5.9, 11.5, 0.35, 13, MUTED, False, PP_ALIGN.CENTER)

# ---------------------------------------------------------------------------
# 10 · Deployment & credits
# ---------------------------------------------------------------------------
slide = add_slide("09 / Deployment & credits", "Where it runs today, and which budget it spends")
card(slide, 0.7, 2.0, 6.0, 4.3, "Runtime (Agentrix / container)",
     "Single Docker image: nginx UI + Node relay on $PORT.\n\n· Auth to models: Entra app → Bayer AI Gateway\n· Endpoints: /api/extract, /api/qc-summary, /api/jobs*\n· Soft-async jobs in-process (keep minScale = 1)\n· Health: GET /health → ok / runtime agentrix\n· Pilot gate secret on AI paths\n\nAlso available: Cloudflare Pages pilot (Pages Functions + KV audit).",
     BLUE, PALE_BLUE)
card(slide, 7.0, 2.0, 5.5, 4.3, "Credits & controls",
     "Spends Bayer AI Gateway credits (team/application attribution — target state).\n\n· Daily budget guard (configurable; default $100 on Agentrix / $15 pilot)\n· Rate limit (default 20 req/min)\n· Kill switch (instant, no redeploy)\n· Metadata-only audit trail (no raw label text)\n· Cost estimate logged per call\n\nFallback: deterministic mode uses zero model credits.",
     TEAL, PALE_TEAL)

# ---------------------------------------------------------------------------
# 11 · Cost & value
# ---------------------------------------------------------------------------
slide = add_slide("10 / Cost & value", "Then vs now — the economics stakeholders care about")
# Before / After columns
rect(slide, 0.7, 2.0, 5.8, 4.3, PALE_RED, PALE_RED, True)
text(slide, "BEFORE", 0.95, 2.2, 5.3, 0.35, 14, RED, True)
text(slide, "Manual table build", 0.95, 2.55, 5.3, 0.4, 22, NAVY, True)
bullets(slide, [
    "100+ hours of hand work per table",
    "Managers write every row from the PDF",
    "High risk of missed uses / footnotes",
    "Submission waits on transcription",
    "Cost = scarce expert time",
], 1.05, 3.2, 5.2, 2.8, 15, INK, 8)

rect(slide, 6.85, 2.0, 5.8, 4.3, PALE_GREEN, PALE_GREEN, True)
text(slide, "NOW", 7.1, 2.2, 5.3, 0.35, 14, GREEN, True)
text(slide, "AI draft + spot-check", 7.1, 2.55, 5.3, 0.4, 22, NAVY, True)
bullets(slide, [
    "Draft in a few minutes",
    "Managers review & correct",
    "Source trail on every cell",
    "Faster path to EPA submission",
    "~$0.50–$0.75 model cost per label",
], 7.2, 3.2, 5.2, 2.8, 15, INK, 8)

# ---------------------------------------------------------------------------
# 12 · Value detail / unit economics
# ---------------------------------------------------------------------------
slide = add_slide("11 / Unit economics", "Predictable per-label spend — not open-ended model usage",
                  "Internal estimates for a typical clean run; hard labels may escalate to Opus remediation.")
metrics = [
    ("~$0.50–0.75", "Typical cost\nper label", TEAL),
    ("Minutes", "Draft + human\nspot-check", BLUE),
    ("88%", "Field-level accuracy\nvs expert table", GREEN),
    ("$100 / day", "Agentrix daily\nbudget default", AMBER),
]
for i, (num, label, color) in enumerate(metrics):
    x = 0.75 + i * 3.15
    rect(slide, x, 2.1, 2.95, 2.0, PALE, PALE, True)
    text(slide, num, x + 0.1, 2.35, 2.75, 0.55, 22, color, True, PP_ALIGN.CENTER)
    text(slide, label, x + 0.1, 3.1, 2.75, 0.75, 13, MUTED, False, PP_ALIGN.CENTER)

bullets(slide, [
    "Clean path: Sonnet extraction + independent Sonnet QC (most labels)",
    "Hard path: escalate to Opus only when QC is High/Critical — capped cycles",
    "Value = expert hours returned + fewer missed uses + reusable structured data for the portfolio",
], 1.0, 4.5, 11.3, 1.8, 15, INK, 8)

# ---------------------------------------------------------------------------
# 13 · Governance
# ---------------------------------------------------------------------------
slide = add_slide("12 / Trust & governance", "Safe enough to run in regulated work")
controls = [
    ("Human sign-off", "Nothing exported as “final” without review", GREEN),
    ("Source on every cell", "Page + evidence for challenge and audit", BLUE),
    ("Kill switch", "Stop AI paths instantly — no redeploy", RED),
    ("Spend cap", "Daily budget blocks new model work", AMBER),
    ("Rate limits", "Stops runaway loops / accidental hammering", TEAL),
    ("Audit trail", "Metadata only — never raw label text", NAVY),
]
for i, (h, b, c) in enumerate(controls):
    x = 0.7 + (i % 3) * 4.15
    y = 2.0 + (i // 3) * 2.15
    card(slide, x, y, 3.95, 1.9, h, b, c, PALE)

# ---------------------------------------------------------------------------
# 14 · Demo script (optional live)
# ---------------------------------------------------------------------------
slide = add_slide("13 / Live demo path", "A focused walkthrough (~6–7 minutes)")
demo = [
    ("0:00", "Frame", "One label in → reviewable EPA table out"),
    ("0:30", "Upload", "Drop a sample label; start AI extraction"),
    ("2:00", "Results", "Show rows, rates, restrictions, confidence"),
    ("3:30", "Trace", "Expand a cell: page + source wording"),
    ("4:30", "Correct", "Edit a value; show edited marker"),
    ("5:30", "Export", "Download Excel; open a sheet"),
    ("6:30", "Close", "Cost, guardrails, deployment ask"),
]
for i, (t, h, b) in enumerate(demo):
    y = 1.95 + i * 0.65
    text(slide, t, 0.9, y, 0.8, 0.3, 13, TEAL, True)
    text(slide, h, 1.9, y, 1.8, 0.3, 15, NAVY, True)
    text(slide, b, 4.0, y, 8.3, 0.3, 14, INK)
    if i < 6:
        rect(slide, 1.9, y + 0.4, 10.3, 0.012, RGBColor(221, 229, 236))
text(slide, "Fallback: switch off AI and use deterministic mode if the gateway or budget is unavailable.",
     0.9, 6.55, 11.5, 0.3, 13, RED, True)

# ---------------------------------------------------------------------------
# 15 · Ask / next steps
# ---------------------------------------------------------------------------
slide = add_slide("14 / What we need from you", "Decisions that unlock the next phase")
asks = [
    ("01", "Adoption", "Which teams pilot next, and who owns day-to-day review sign-off?"),
    ("02", "Budget", "Confirm AI Gateway team/application budget and daily spend envelope."),
    ("03", "Runtime", "Confirm Agentrix as the governed home (minScale=1 for background jobs)."),
    ("04", "Acceptance", "Agree accuracy / review bar for “good enough to use in submission prep.”"),
    ("05", "Scale path", "Priority: more labels, more countries, or sister workflows (e.g. ARS tox)?"),
]
for i, (num, h, b) in enumerate(asks):
    y = 1.95 + i * 0.85
    text(slide, num, 0.9, y, 0.7, 0.35, 16, TEAL, True)
    text(slide, h, 1.8, y, 2.4, 0.35, 17, NAVY, True)
    text(slide, b, 4.4, y, 8.2, 0.45, 16, INK)

# ---------------------------------------------------------------------------
# 16 · Close
# ---------------------------------------------------------------------------
slide = prs.slides.add_slide(blank)
set_bg(slide, NAVY)
rect(slide, 0, 0, 0.18, 7.5, TEAL)
text(slide, "THANK YOU", 0.7, 1.6, 12, 0.35, 14, RGBColor(152, 218, 216), True, PP_ALIGN.CENTER)
text(slide, "Questions & discussion", 0.7, 2.3, 12, 0.7, 36, WHITE, True, PP_ALIGN.CENTER)
text(slide, "Use Summary Tables Extractor", 0.7, 3.4, 12, 0.4, 20, RGBColor(220, 232, 241), False, PP_ALIGN.CENTER)
text(slide, "100+ hours → minutes  ·  ~$0.50–0.75 / label  ·  human review always on",
     1.2, 4.2, 10.8, 0.45, 16, RGBColor(188, 207, 222), False, PP_ALIGN.CENTER)
text(slide, "Karandeep Singh  ·  BEAT04090032  ·  Agentrix + Bayer AI Gateway",
     0.7, 6.3, 12, 0.3, 13, RGBColor(160, 184, 201), False, PP_ALIGN.CENTER)
footer(slide, 16)

prs.save(OUT)
print(OUT)

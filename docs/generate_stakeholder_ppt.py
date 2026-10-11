from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

OUT = Path(__file__).with_name("Use-Summary-Tables-Stakeholder-Briefing.pptx")

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


def bullets(slide, items, x, y, w, h, size=17, color=INK, gap=6):
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
    text(slide, kicker.upper(), 0.65, 0.35, 12, 0.25, 10, BLUE, True)
    text(slide, heading, 0.65, 0.7, 12, 0.65, 28, NAVY, True)
    if subtitle:
        text(slide, subtitle, 0.68, 1.39, 11.8, 0.38, 13, MUTED)
    rect(slide, 0.65, 1.92, 1.0, 0.05, TEAL)


def footer(slide, number):
    text(slide, "Use Summary Tables Extractor  |  Stakeholder briefing", 0.65, 7.18, 8.5, 0.18, 8, MUTED)
    text(slide, str(number), 12.2, 7.16, 0.45, 0.2, 9, MUTED, False, PP_ALIGN.RIGHT)


def add_slide(kicker, heading, subtitle=None, bg=WHITE):
    slide = prs.slides.add_slide(blank)
    set_bg(slide, bg)
    title(slide, kicker, heading, subtitle)
    footer(slide, len(prs.slides))
    return slide


def card(slide, x, y, w, h, heading, body, color=BLUE, fill=PALE):
    rect(slide, x, y, w, h, fill, fill, True)
    rect(slide, x, y, 0.08, h, color, color, True)
    text(slide, heading, x + 0.22, y + 0.18, w - 0.38, 0.3, 15, NAVY, True)
    text(slide, body, x + 0.22, y + 0.58, w - 0.4, h - 0.7, 12, INK)


def node(slide, x, y, w, h, label, fill=PALE_BLUE, color=NAVY):
    rect(slide, x, y, w, h, fill, fill, True)
    text(slide, label, x + 0.08, y + 0.08, w - 0.16, h - 0.16, 12, color, True, PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)


def arrow(slide, x1, y1, x2, y2, color=BLUE):
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    line.line.color.rgb = color
    line.line.width = Pt(1.6)
    line.line.end_arrowhead = True
    return line


def line_only(slide, x1, y1, x2, y2, color=BLUE):
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    line.line.color.rgb = color
    line.line.width = Pt(1.6)
    return line


# 1
slide = prs.slides.add_slide(blank)
set_bg(slide, NAVY)
rect(slide, 0.7, 0.75, 0.12, 5.85, TEAL)
text(slide, "STAKEHOLDER BRIEFING", 1.1, 1.02, 8, 0.3, 12, RGBColor(152, 218, 216), True)
text(slide, "Use Summary\nTables Extractor", 1.08, 1.48, 8.5, 1.55, 38, WHITE, True)
text(slide, "From pesticide label PDF to a reviewable, traceable Use Summary Table", 1.12, 3.35, 8.8, 0.6, 20, RGBColor(220, 232, 241))
text(slide, "Human-in-the-loop  |  BEAT04090032  |  QA target: Agentrix + AI Gateway", 1.12, 5.62, 9.5, 0.35, 13, RGBColor(188, 207, 222))
rect(slide, 10.2, 1.35, 2.25, 4.75, RGB_TEAL if False else TEAL, TEAL, True)
text(slide, "PDF", 10.52, 1.85, 1.6, 0.45, 25, WHITE, True, PP_ALIGN.CENTER)
arrow(slide, 11.35, 2.42, 11.35, 2.75, WHITE)
text(slide, "STRUCTURED\nTABLE", 10.42, 2.85, 1.8, 0.75, 20, WHITE, True, PP_ALIGN.CENTER)
arrow(slide, 11.35, 3.72, 11.35, 4.05, WHITE)
text(slide, "HUMAN\nREVIEW", 10.42, 4.15, 1.8, 0.75, 20, WHITE, True, PP_ALIGN.CENTER)
text(slide, "Karandeep Singh  |  13 September 2026", 1.12, 6.72, 8, 0.25, 9, RGBColor(160, 184, 201))

# 2
slide = add_slide("01 / Why this exists", "The problem is fragmented regulatory information")
card(slide, 0.75, 2.35, 3.75, 2.65, "Manual extraction", "45–90 minutes per label. Analysts search tables, footnotes, restrictions, and safety sections by hand.", RED, RGBColor(253, 237, 237))
card(slide, 4.8, 2.35, 3.75, 2.65, "Where errors hide", "Missed uses, merged application methods, lost conditional rates, wrong restriction scope, and weak traceability.", AMBER, PALE_AMBER)
card(slide, 8.85, 2.35, 3.75, 2.65, "Business impact", "Rework, inconsistent analyst decisions, slower EPA preparation, and limited confidence in downstream data.", BLUE, PALE_BLUE)
text(slide, "The product goal", 0.82, 5.55, 2.0, 0.3, 14, TEAL, True)
text(slide, "Make the first draft faster without turning regulatory interpretation into an opaque, unsupervised model decision.", 2.55, 5.5, 9.6, 0.45, 20, NAVY, True)

# 3
slide = add_slide("02 / What it does", "One document in. One reviewable table out.")
node(slide, 0.8, 2.25, 2.15, 1.05, "Pesticide\nlabel PDF", PALE_BLUE)
node(slide, 3.45, 2.25, 2.15, 1.05, "Page-preserving\ntext + OCR", PALE_TEAL, TEAL)
node(slide, 6.1, 2.25, 2.15, 1.05, "Structured\n28-column rows", PALE_AMBER, AMBER)
node(slide, 8.75, 2.25, 2.15, 1.05, "Evidence, page,\nconfidence", RGBColor(238, 234, 249), NAVY)
node(slide, 11.4, 2.25, 1.15, 1.05, "Excel", PALE_TEAL, GREEN)
for x in [2.95, 5.6, 8.25, 10.9]: arrow(slide, x, 2.78, x + 0.4, 2.78)
card(slide, 1.05, 4.35, 3.45, 1.35, "Schema discipline", "Every field is filled with a label value, NS, or NA.", BLUE, PALE_BLUE)
card(slide, 4.95, 4.35, 3.45, 1.35, "Human decision", "Reviewers inspect evidence, edit cells, and approve the final artifact.", TEAL, PALE_TEAL)
card(slide, 8.85, 4.35, 3.45, 1.35, "No autonomous submission", "The tool creates a workbook; it does not submit to EPA or write external systems.", GREEN, RGBColor(235, 247, 239))

# 4
slide = add_slide("03 / User journey", "The workflow is designed around analyst review")
steps = [("1", "Upload", "Select one or more labels"), ("2", "Extract", "Parse text and identify uses"), ("3", "Inspect", "Search, filter, sort, expand"), ("4", "Correct", "Edit cells with visible markers"), ("5", "Export", "Download the formatted workbook")]
for i, (num, head, body) in enumerate(steps):
    x = 0.8 + i * 2.48
    rect(slide, x, 2.35, 1.0, 0.72, TEAL, TEAL, True)
    text(slide, num, x, 2.46, 1.0, 0.35, 20, WHITE, True, PP_ALIGN.CENTER)
    text(slide, head, x - 0.25, 3.35, 1.5, 0.3, 15, NAVY, True, PP_ALIGN.CENTER)
    text(slide, body, x - 0.45, 3.78, 1.9, 0.72, 12, MUTED, False, PP_ALIGN.CENTER)
    if i < 4: arrow(slide, x + 1.18, 2.72, x + 2.15, 2.72, BLUE)
text(slide, "The model proposes. The application validates. The analyst decides.", 1.15, 5.55, 11.0, 0.5, 23, NAVY, True, PP_ALIGN.CENTER)

# 5
slide = add_slide("04 / Architecture", "Two execution paths, one controlled product")
text(slide, "Interactive path", 0.9, 2.15, 2.2, 0.3, 15, BLUE, True)
for x, label in [(0.85, "Browser"), (3.0, "Pages\nFunction"), (5.15, "mGA /\nAI Gateway"), (7.3, "Claude"), (9.45, "Rows + QC")]: node(slide, x, 2.65, 1.65, 0.78, label)
for x in [2.5, 4.65, 6.8, 8.95]: arrow(slide, x, 3.04, x + 0.45, 3.04)
text(slide, "Background path", 0.9, 4.15, 2.2, 0.3, 15, TEAL, True)
for x, label in [(0.85, "Browser"), (3.0, "Jobs API"), (5.15, "KV + Queue"), (7.3, "Worker"), (9.45, "Status +\nRows")]: node(slide, x, 4.65, 1.65, 0.78, label, PALE_TEAL, TEAL)
for x in [2.5, 4.65, 6.8, 8.95]: arrow(slide, x, 5.04, x + 0.45, 5.04, TEAL)
text(slide, "Interactive extraction returns in the browser. Background jobs persist status so a user can leave and return.", 0.95, 6.15, 11.4, 0.4, 14, MUTED, False, PP_ALIGN.CENTER)

# 6
slide = add_slide("05 / AI control loop", "The model is one stage inside a bounded workflow")
node(slide, 0.85, 2.45, 2.0, 0.95, "Stage 1\nExtraction", PALE_BLUE)
node(slide, 3.35, 2.45, 2.0, 0.95, "Stage 2\nIndependent QC", PALE_TEAL, TEAL)
node(slide, 5.85, 2.45, 2.0, 0.95, "Decision\nCritical / High?", PALE_AMBER, AMBER)
node(slide, 8.35, 2.45, 2.0, 0.95, "Stage 3\nRemediation", RGBColor(253, 235, 235), RED)
node(slide, 10.85, 2.45, 1.7, 0.95, "Runtime\nvalidation", PALE_TEAL, GREEN)
for x in [2.85, 5.35, 7.85, 10.35]: arrow(slide, x, 2.92, x + 0.45, 2.92)
# Rectangular feedback loop: down from Stage 3, left under the row, up into Decision
arrow(slide, 9.35, 3.42, 9.35, 4.75, RED)
line_only(slide, 9.35, 4.75, 6.85, 4.75, RED)
arrow(slide, 6.85, 4.75, 6.85, 3.42, RED)
text(slide, "At most 2 cycles", 7.05, 4.85, 2.1, 0.25, 11, RED, True)
text(slide, "Only serious findings enter remediation; normal rows go straight to validation.", 1.3, 5.55, 10.8, 0.45, 18, NAVY, True, PP_ALIGN.CENTER)
text(slide, "Sonnet for extraction/QC  |  Opus escalation for hard corrections", 2.0, 6.2, 9.2, 0.3, 13, MUTED, False, PP_ALIGN.CENTER)

# 7
slide = add_slide("06 / End-to-end architecture", "From uploaded label to reviewed workbook", "The application separates document reading, model reasoning, validation, and human approval.")

flow = [
    ("User uploads\nPDF", 0.75, 2.15, 1.35, PALE_BLUE, NAVY),
    ("Browser app", 2.55, 2.15, 1.35, PALE_BLUE, NAVY),
    ("PDF.js extracts\npage text", 4.35, 2.15, 1.55, PALE_TEAL, TEAL),
    ("Text layer\navailable?", 6.35, 2.15, 1.55, PALE_AMBER, AMBER),
    ("Page-marked\ntext", 8.35, 2.15, 1.45, PALE_TEAL, TEAL),
    ("Extraction\nmode", 10.25, 2.15, 1.35, PALE_AMBER, AMBER),
]
for label, x, y, w, fill, color in flow:
    node(slide, x, y, w, 0.78, label, fill, color)
for x in [2.1, 3.9, 5.95, 7.95, 9.9]:
    arrow(slide, x, 2.54, x + 0.38, 2.54)
text(slide, "No", 7.02, 3.02, 0.35, 0.2, 10, MUTED, True, PP_ALIGN.CENTER)
arrow(slide, 7.12, 2.95, 7.12, 3.55, MUTED)
node(slide, 6.15, 3.72, 1.95, 0.7, "Tesseract OCR\nfallback", PALE_TEAL, TEAL)
arrow(slide, 8.1, 4.07, 8.95, 3.15, TEAL)
text(slide, "Yes", 7.55, 2.98, 0.38, 0.2, 10, GREEN, True, PP_ALIGN.CENTER)

node(slide, 9.5, 3.72, 1.6, 0.7, "Deterministic\nparser", PALE_BLUE, BLUE)
node(slide, 11.3, 3.72, 1.5, 0.7, "Runtime\nQC", PALE_TEAL, GREEN)
arrow(slide, 10.925, 2.93, 10.3, 3.62, AMBER)
arrow(slide, 11.1, 4.07, 11.3, 4.07, BLUE)

node(slide, 7.8, 4.95, 1.65, 0.7, "Governance\nchecks", PALE_AMBER, AMBER)
node(slide, 9.65, 4.95, 1.65, 0.7, "mGA / future\nAI Gateway", PALE_BLUE, BLUE)
node(slide, 11.55, 4.95, 1.35, 0.7, "Claude", PALE_TEAL, TEAL)
arrow(slide, 9.075, 2.93, 8.625, 4.85, BLUE)
arrow(slide, 9.45, 5.3, 9.65, 5.3, BLUE)
arrow(slide, 11.3, 5.3, 11.55, 5.3, BLUE)

node(slide, 7.8, 6.0, 1.5, 0.62, "Structured\nextraction", PALE_BLUE, NAVY)
node(slide, 9.6, 6.0, 1.5, 0.62, "Independent\nQC", PALE_TEAL, TEAL)
node(slide, 11.4, 6.0, 1.3, 0.62, "Review", PALE_AMBER, AMBER)
arrow(slide, 12.225, 5.65, 8.55, 5.98, TEAL)
arrow(slide, 9.3, 6.3, 9.6, 6.3, TEAL)
arrow(slide, 11.1, 6.3, 11.4, 6.3, TEAL)

# 8
slide = add_slide("06 / Why the controls matter", "Accuracy is not a single model score")
card(slide, 0.85, 2.2, 2.75, 3.1, "Completeness", "Every use, crop, application method, and page reference must be accounted for.", BLUE, PALE_BLUE)
card(slide, 3.8, 2.2, 2.75, 3.1, "Field fidelity", "Conditional PHIs, rates, restrictions, REI, and product-wide wording must survive extraction.", TEAL, PALE_TEAL)
card(slide, 6.75, 2.2, 2.75, 3.1, "Scope control", "A crop-specific or method-specific restriction must not leak onto unrelated rows.", AMBER, PALE_AMBER)
card(slide, 9.7, 2.2, 2.75, 3.1, "Provenance", "Evidence and page citations let an analyst challenge a value instead of trusting a score.", GREEN, RGBColor(235, 247, 239))
text(slide, "The output is useful because it is inspectable, not because it is unquestionable.", 1.0, 6.05, 11.3, 0.4, 21, NAVY, True, PP_ALIGN.CENTER)

# 8
slide = add_slide("07 / Failure handling", "Failures become visible states, not silent guesses")
failures = [("No text layer", "OCR fallback or explicit warning", TEAL), ("Gateway error", "Surface error; do not silently substitute output", RED), ("Budget / rate limit", "Reject before new model work", AMBER), ("Malformed output", "Require structured tool result", BLUE), ("Serious QC defect", "Bounded remediation, then human review", GREEN)]
for i, (h, b, c) in enumerate(failures):
    y = 2.05 + i * 0.84
    rect(slide, 1.0, y, 2.65, 0.58, c, c, True)
    text(slide, h, 1.1, y + 0.15, 2.45, 0.25, 13, WHITE, True, PP_ALIGN.CENTER)
    arrow(slide, 3.8, y + 0.29, 4.55, y + 0.29, MUTED)
    text(slide, b, 4.85, y + 0.11, 7.2, 0.35, 15, INK)
text(slide, "Design principle: never hide uncertainty behind a clean-looking table.", 1.0, 6.45, 11.3, 0.35, 18, NAVY, True, PP_ALIGN.CENTER)

# 9
slide = add_slide("08 / Security and governance", "Controls are layered around the model call")
controls = [("Identity", "Bayer IAM/MFA for users; Entra M2M identity for AI Gateway", BLUE), ("Secrets", "Server-side managed secrets; no model credential in the browser", TEAL), ("Safety", "Label text treated as data; injection phrases flagged for review", AMBER), ("Operations", "Kill switch, rate limits, budget guard, metadata-only audit", RED), ("Human control", "Review, edit, approval, and export remain explicit", GREEN)]
for i, (h, b, c) in enumerate(controls):
    x = 0.85 + (i % 3) * 4.1
    y = 2.15 + (i // 3) * 1.75
    card(slide, x, y, 3.55, 1.25, h, b, c, PALE)
text(slide, "All governance controls run server-side before any model call is made.", 1.0, 6.2, 11.3, 0.35, 16, NAVY, True, PP_ALIGN.CENTER)

# 10
slide = add_slide("09 / Scale and efficiency", "Bound the expensive parts deliberately")
card(slide, 0.85, 2.15, 3.55, 2.55, "Bounded concurrency", "Up to three documents in parallel; stages within one document remain sequential because each depends on the prior result.", BLUE, PALE_BLUE)
card(slide, 4.9, 2.15, 3.55, 2.55, "Selective escalation", "Sonnet handles normal extraction/QC. Opus is used only when QC reports Critical or High findings.", TEAL, PALE_TEAL)
card(slide, 8.95, 2.15, 3.55, 2.55, "Bounded retries", "Transient failures retry within limits. Remediation stops after two cycles rather than multiplying cost indefinitely.", AMBER, PALE_AMBER)
text(slide, "Known constraint", 0.95, 5.35, 1.8, 0.3, 14, RED, True)
text(slide, "Large labels are currently sent as one full-document context. Chunking or retrieval is a future optimization, not a hidden behavior.", 2.65, 5.3, 9.5, 0.45, 18, NAVY, True)

# 10b
slide = add_slide("09b / Token cost per document", "Predictable per-label spend, not open-ended model usage",
                  "Numbers below are for a typical 10-page label (≈5,000 doc tokens). Larger labels scale with doc length.")

# Stage cards
stage_fill = [PALE_BLUE, PALE_TEAL, RGBColor(253, 235, 235)]
stage_color = [BLUE, TEAL, RED]
stages = [
    ("Stage 1  ·  Extraction", "Model: Sonnet 5\nInput: ~21,000 tokens\n(system 14.5K + tools 1.8K + doc 5K)\nOutput: 2,000–4,000 tokens\n(extracted rows JSON)"),
    ("Stage 2  ·  Independent QC", "Model: Sonnet 5  ·  fresh conversation\nInput: ~22,500 tokens\n(system + doc from cache + rows JSON)\nOutput: 500–1,000 tokens\n(QC report)"),
    ("Stage 3  ·  Remediation", "Model: Opus 5  ·  only if QC = High/Critical\nInput: adds 40,000–80,000 tokens\n(growing conversation context)\nOutput: adds 8,000–20,000 tokens\nUp to 4 Opus calls (2 cycles × correct+recheck)"),
]
for i, (h, b) in enumerate(stages):
    card(slide, 0.85 + i * 4.18, 2.15, 3.75, 2.95, h, b, stage_color[i], stage_fill[i])

# Pricing row
rect(slide, 0.85, 5.42, 11.6, 0.62, PALE, PALE, True)
text(slide, "Pricing (internal estimate):", 1.1, 5.51, 2.5, 0.35, 13, NAVY, True)
text(slide, "Sonnet 5   $3 / $15 per MTok (in/out)", 3.8, 5.51, 3.5, 0.35, 13, TEAL)
text(slide, "Opus 5   $15 / $75 per MTok (in/out)", 7.5, 5.51, 3.5, 0.35, 13, RED)
text(slide, "Clean label (2 Sonnet calls): ~$0.08–$0.12  ·  With remediation (+Opus): ~$1.60–$2.15  ·  Daily budget default: $100 / day", 0.85, 6.25, 11.6, 0.35, 13, MUTED, False, PP_ALIGN.CENTER)

# 11
slide = add_slide("10 / Deployment target", "From Cloudflare pilot to governed Bayer runtime")
text(slide, "TODAY", 0.95, 2.0, 2.1, 0.3, 14, MUTED, True, PP_ALIGN.CENTER)
text(slide, "TARGET", 9.15, 2.0, 2.1, 0.3, 14, BLUE, True, PP_ALIGN.CENTER)
rect(slide, 0.75, 2.5, 4.65, 2.8, PALE, PALE, True)
text(slide, "Cloudflare pilot", 1.05, 2.82, 3.9, 0.35, 20, NAVY, True, PP_ALIGN.CENTER)
bullets(slide, ["Pages + Functions + Worker", "KV + Queue job state", "Personal/shared mGA pilot credential", "Shared pilot gate", "Working prototype"], 1.15, 3.45, 3.8, 1.45, 13)
rect(slide, 7.95, 2.5, 4.65, 2.8, PALE_BLUE, PALE_BLUE, True)
text(slide, "Agentrix + AI Gateway", 8.25, 2.82, 4.0, 0.35, 20, NAVY, True, PP_ALIGN.CENTER)
bullets(slide, ["Agentrix/AWS-hosted container", "Bayer IAM/MFA user access", "Entra M2M identity", "AI Gateway team/application budget", "OpenTelemetry traces"], 8.35, 3.45, 3.8, 1.45, 13)
arrow(slide, 5.65, 3.9, 7.6, 3.9, BLUE)
text(slide, "Migration work", 5.35, 5.15, 2.5, 0.3, 13, BLUE, True, PP_ALIGN.CENTER)
text(slide, "Container + health endpoint + gateway client + runtime storage + tracing", 4.85, 5.55, 3.5, 0.8, 12, MUTED, False, PP_ALIGN.CENTER)

# 12
slide = add_slide("11 / Live demo", "A 7-minute path through the product")
demo = [("00:00", "Frame the problem", "One label in; reviewable table out"), ("00:30", "Upload and extract", "Show progress, text/OCR, AI or deterministic mode"), ("02:00", "Inspect results", "Rows, rates, timing, restrictions, confidence"), ("03:30", "Trace a value", "Expand source page/evidence; show warning"), ("04:30", "Edit and review", "Search, sort, edit, approval stations"), ("06:00", "Export", "Open combined and per-label Excel sheets"), ("06:30", "Close", "Current pilot, target deployment, decisions")]
for i, (t, h, b) in enumerate(demo):
    y = 2.05 + i * 0.62
    text(slide, t, 1.0, y, 0.75, 0.25, 12, TEAL, True)
    text(slide, h, 2.0, y, 2.25, 0.25, 14, NAVY, True)
    text(slide, b, 4.45, y, 7.8, 0.25, 13, INK)
    rect(slide, 1.78, y + 0.34, 10.55, 0.015, RGBColor(221, 229, 236), RGBColor(221, 229, 236))
text(slide, "Demo fallback: switch to deterministic mode if the model gateway or budget is unavailable.", 1.1, 6.55, 11.0, 0.3, 14, RED, True, PP_ALIGN.CENTER)

# 13
slide = add_slide("12 / Decisions", "What stakeholders need to confirm")
items = [
    ("01", "Target environment", "QA first, then production?"),
    ("02", "AI access", "AI Gateway endpoint, Entra scope, model IDs, and team budget"),
    ("03", "Runtime scope", "Synchronous first release or background jobs from day one?"),
    ("04", "Control ownership", "Which security controls are inherited from Agentrix/AWS?"),
    ("05", "Acceptance", "Accuracy threshold, reviewer roles, and sign-off owner"),
]
for i, (num, h, b) in enumerate(items):
    y = 2.05 + i * 0.78
    text(slide, num, 1.0, y, 0.65, 0.3, 14, TEAL, True)
    text(slide, h, 2.0, y, 2.7, 0.3, 16, NAVY, True)
    text(slide, b, 4.9, y, 7.3, 0.3, 15, INK)
text(slide, "Success means: a Bayer user can authenticate, extract, inspect, export, and see usage attributed to the approved application/team budget.", 1.0, 6.25, 11.3, 0.55, 19, NAVY, True, PP_ALIGN.CENTER)

# 14
slide = prs.slides.add_slide(blank)
set_bg(slide, NAVY)
text(slide, "THANK YOU", 0.9, 1.15, 11.5, 0.35, 13, RGBColor(152, 218, 216), True, PP_ALIGN.CENTER)
text(slide, "Questions and discussion", 0.9, 2.15, 11.5, 0.65, 32, WHITE, True, PP_ALIGN.CENTER)
text(slide, "Use Summary Tables Extractor", 0.9, 3.15, 11.5, 0.35, 19, RGBColor(220, 232, 241), False, PP_ALIGN.CENTER)
text(slide, "A governed, traceable, human-in-the-loop path from label PDF to regulatory table.", 1.4, 4.15, 10.5, 0.5, 18, RGBColor(188, 207, 222), False, PP_ALIGN.CENTER)
text(slide, "BEAT04090032  |  Karandeep Singh  |  QA target: Agentrix + AI Gateway", 1.0, 6.55, 11.4, 0.25, 10, RGBColor(160, 184, 201), False, PP_ALIGN.CENTER)

prs.save(OUT)
print(OUT)

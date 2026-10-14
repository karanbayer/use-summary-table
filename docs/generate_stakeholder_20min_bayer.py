#!/usr/bin/env python3
"""
15-minute visual stakeholder deck on the Bayer Alpha Centauri master
(+ 10-minute live demo).

Emphasizes diagrams, metric cards, and process flows over dense bullets.
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

TEMPLATE = Path(
    "/Users/karandeep.singh/Library/CloudStorage/OneDrive-Bayer/Desktop/"
    "Digital Label/Alpha Centauri/2023-08-01_WS1-DataFlow_v03.pptx"
)
OUT = Path(__file__).with_name("Use-Summary-Tables-Stakeholder-20min-Bayer.pptx")
HERO_IMAGE = Path(__file__).with_name("stakeholder-hero-agriculture.jpg")

FOOTER = "/// Use Summary Tables Extractor  ·  Stakeholder briefing  ·  BEAT04090032 ///"

# Bayer brand-aligned palette
DARK_BLUE = RGBColor(16, 56, 79)       # #10384F
BRIGHT_BLUE = RGBColor(0, 188, 255)    # #00BCFF
BRIGHT_GREEN = RGBColor(137, 211, 41)  # #89D329
MID_BLUE = RGBColor(0, 120, 170)
WHITE = RGBColor(255, 255, 255)
INK = RGBColor(30, 45, 58)
MUTED = RGBColor(90, 110, 125)
PALE = RGBColor(240, 246, 250)
PALE_BLUE = RGBColor(220, 240, 250)
PALE_GREEN = RGBColor(232, 245, 220)
PALE_AMBER = RGBColor(255, 244, 220)
AMBER = RGBColor(230, 150, 40)
RED = RGBColor(190, 70, 70)
PALE_RED = RGBColor(253, 237, 237)


def layout_by_name(prs, name):
    for layout in prs.slide_layouts:
        if layout.name == name:
            return layout
    raise KeyError(name)


def delete_all_slides(prs):
    sldIdLst = prs.slides._sldIdLst
    for sldId in list(sldIdLst):
        rId = sldId.get(qn("r:id"))
        prs.part.drop_rel(rId)
        sldIdLst.remove(sldId)


def set_runs(paragraph, text, size=None, bold=None, color=None):
    p = paragraph._p
    for child in list(p):
        if child.tag in (qn("a:r"), qn("a:br")):
            p.remove(child)
    run = paragraph.add_run()
    run.text = text
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    return run


def ph(slide, idx):
    for shape in slide.placeholders:
        if shape.placeholder_format.idx == idx:
            return shape
    return None


def set_text(shape, text, size=None, bold=None, color=None):
    if shape is None:
        return
    tf = shape.text_frame
    tf.clear()
    set_runs(tf.paragraphs[0], text, size=size, bold=bold, color=color)


def set_bullets(shape, lines, size=16):
    if shape is None:
        return
    tf = shape.text_frame
    tf.clear()
    for i, item in enumerate(lines):
        text, level = (item if isinstance(item, tuple) else (item, 0))
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = level
        set_runs(p, text, size=size)


def set_footer(slide, text=FOOTER):
    for shape in slide.placeholders:
        if shape.placeholder_format.idx == 11:
            set_text(shape, text, size=10)
            return


def clear_body(slide, idxs=(14, 16, 17, 18, 19, 20)):
    for idx in idxs:
        shape = ph(slide, idx)
        if shape is not None and shape.has_text_frame:
            set_text(shape, " ", size=8)


def fill_picture_placeholders(slide, image_path):
    """Fill title/final 'Insert Picture' slots with a hero image."""
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    for shape in list(slide.shapes):
        try:
            if shape.is_placeholder and int(shape.placeholder_format.type) == 18:  # PICTURE
                shape.insert_picture(str(image_path))
        except Exception:
            continue


def rect(slide, x, y, w, h, fill, line=None, radius=True):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    s = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = line or fill
    if radius:
        try:
            s.adjustments[0] = 0.1
        except Exception:
            pass
    return s


def label(slide, text, x, y, w, h, size=14, color=INK, bold=False, align=PP_ALIGN.CENTER):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = align
    set_runs(p, text, size=size, bold=bold, color=color)
    return box


def card(slide, x, y, w, h, heading, body, fill=PALE, accent=BRIGHT_BLUE, head_size=14, body_size=12):
    rect(slide, x, y, w, h, fill, fill, True)
    rect(slide, x, y, 0.08, h, accent, accent, False)
    label(slide, heading, x + 0.2, y + 0.12, w - 0.35, 0.35, head_size, DARK_BLUE, True, PP_ALIGN.LEFT)
    label(slide, body, x + 0.2, y + 0.5, w - 0.35, h - 0.65, body_size, INK, False, PP_ALIGN.LEFT)


def metric(slide, x, y, w, h, number, caption, fill=PALE_BLUE, number_color=DARK_BLUE):
    rect(slide, x, y, w, h, fill, fill, True)
    label(slide, number, x + 0.08, y + 0.15, w - 0.16, 0.55, 22, number_color, True)
    label(slide, caption, x + 0.08, y + 0.75, w - 0.16, 0.7, 11, MUTED, False)


def node(slide, x, y, w, h, text, fill=PALE_BLUE, color=DARK_BLUE):
    rect(slide, x, y, w, h, fill, fill, True)
    label(slide, text, x + 0.06, y + 0.08, w - 0.12, h - 0.16, 12, color, True)


def arrow(slide, x1, y1, x2, y2, color=BRIGHT_BLUE):
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    line.line.color.rgb = color
    line.line.width = Pt(2)
    line.line.end_arrowhead = True
    return line


def build():
    if not TEMPLATE.exists():
        raise FileNotFoundError(TEMPLATE)

    prs = Presentation(str(TEMPLATE))
    delete_all_slides(prs)

    # ------------------------------------------------------------------ 1 Title
    s = prs.slides.add_slide(layout_by_name(prs, "Title Slide"))
    fill_picture_placeholders(s, HERO_IMAGE)
    set_text(ph(s, 1), "NA ANZ Reg Sci")
    set_text(ph(s, 0), "EPA Use Summary Tables Extractor")
    set_text(
        ph(s, 13),
        "//////////\n"
        "Karandeep Singh\n"
        "October 14, 2026",
    )
    f = ph(s, 16)
    if f:
        set_text(f, FOOTER, size=10)

    # ------------------------------------------------------------------ 2 Agenda (compact, content-rich)
    s = prs.slides.add_slide(layout_by_name(prs, "Content"))
    set_text(ph(s, 13), "Session plan")
    set_text(ph(s, 0), "Agenda — what we will cover")
    clear_body(s)

    # Compact timed rows with real content (not sparse giant cards)
    rows = [
        ("15 min", "Slides", [
            "Why EPA Use Summary Tables were a bottleneck (100+ hrs hand work)",
            "What we built + 2-agent pipeline (Extract + QC) on Agentrix",
            "Proof & impact · FAQ (trust, cyber, more EPA schemas)",
        ], BRIGHT_BLUE, PALE_BLUE),
        ("10 min", "Live demo", [
            "Upload a label → run extraction → inspect source on cells",
            "Edit a value → export Excel — the path regulatory users take",
        ], BRIGHT_GREEN, PALE_GREEN),
        ("Q&A", "Discussion", [
            "Use the FAQ slides — answers ready for critical questions",
        ], AMBER, PALE_AMBER),
    ]
    y = 2.0
    for t, h, bullets, accent, fill in rows:
        row_h = 0.42 + 0.30 * len(bullets) + 0.12
        rect(s, 0.55, y, 12.2, row_h, fill, fill, True)
        rect(s, 0.55, y, 1.45, row_h, accent, accent, True)
        label(s, t, 0.55, y + row_h / 2 - 0.18, 1.45, 0.36, 14, WHITE, True)
        label(s, h, 2.2, y + 0.08, 4.0, 0.32, 15, DARK_BLUE, True, PP_ALIGN.LEFT)
        by = y + 0.40
        for b in bullets:
            label(s, "•  " + b, 2.2, by, 10.2, 0.28, 12, INK, False, PP_ALIGN.LEFT)
            by += 0.30
        y += row_h + 0.14
    set_footer(s)

    # ------------------------------------------------------------------ 3 Problem → Solution (visual)
    s = prs.slides.add_slide(layout_by_name(prs, "Content"))
    set_text(ph(s, 13), "Why + what")
    set_text(ph(s, 0), "From hand work to a reviewable AI draft")
    clear_body(s)

    # Before / After panels
    rect(s, 0.55, 2.05, 5.9, 3.55, PALE_RED, PALE_RED, True)
    label(s, "BEFORE", 0.75, 2.2, 5.5, 0.35, 12, RED, True, PP_ALIGN.LEFT)
    label(s, "Manual transcription", 0.75, 2.55, 5.5, 0.4, 18, DARK_BLUE, True, PP_ALIGN.LEFT)
    metric(s, 0.8, 3.15, 2.6, 1.5, "100+ hrs", "building EPA tables\nby hand from PDFs", PALE, RED)
    metric(s, 3.55, 3.15, 2.6, 1.5, "High risk", "missed footnotes,\nappendices, rates", PALE, AMBER)
    label(s, "Submission waits on scarce expert time", 0.75, 4.9, 5.5, 0.4, 13, INK, False, PP_ALIGN.LEFT)

    rect(s, 6.85, 2.05, 5.9, 3.55, PALE_GREEN, PALE_GREEN, True)
    label(s, "NOW", 7.05, 2.2, 5.5, 0.35, 12, RGBColor(50, 120, 50), True, PP_ALIGN.LEFT)
    label(s, "AI draft + human spot-check", 7.05, 2.55, 5.5, 0.4, 18, DARK_BLUE, True, PP_ALIGN.LEFT)
    metric(s, 7.1, 3.15, 2.6, 1.5, "Minutes", "draft + review\nper label", PALE, BRIGHT_GREEN)
    metric(s, 9.85, 3.15, 2.6, 1.5, "$0.50–0.75", "approx. model cost\nper label", PALE, MID_BLUE)
    label(s, "Fixed 28-col schema · rows scale with each label", 7.05, 4.9, 5.5, 0.4, 13, INK, False, PP_ALIGN.LEFT)
    set_footer(s)

    # ------------------------------------------------------------------ 4 How it works (multi-agent architecture)
    s = prs.slides.add_slide(layout_by_name(prs, "Content"))
    set_text(ph(s, 13), "How it works")
    set_text(ph(s, 0), "Two AI agents + optional remediation")
    clear_body(s)

    # Compact user path
    label(s, "What the user does", 0.55, 1.95, 3.5, 0.28, 11, MUTED, True, PP_ALIGN.LEFT)
    user_steps = ["Upload PDF", "Run extract", "Inspect source", "Edit if needed", "Excel export"]
    for i, text in enumerate(user_steps):
        x = 0.55 + i * 2.55
        rect(s, x, 2.25, 2.35, 0.48, PALE if i % 2 == 0 else PALE_BLUE, None, True)
        label(s, text, x, 2.32, 2.35, 0.35, 12, DARK_BLUE, True)
        if i < 4:
            arrow(s, x + 2.35, 2.49, x + 2.5, 2.49, BRIGHT_BLUE)

    # Two agents + optional remediation (accurate to pipeline)
    label(
        s,
        "AI side: 2 agents (Extractor + independent QC). Remediation is an optional 3rd stage — not a third standing agent.",
        0.55, 2.9, 12.2, 0.28, 11, MUTED, True, PP_ALIGN.LEFT,
    )
    agents = [
        ("Agent 1 · Extractor", "Sonnet drafts the\n28-column rows from\nthe label text", PALE_BLUE, BRIGHT_BLUE),
        ("Agent 2 · QC", "Fresh Sonnet chat\nindependent audit\nClean → Critical", PALE_GREEN, BRIGHT_GREEN),
        ("Stage 3 · Remediate", "Only if QC is\nHigh / Critical\nOpus · ≤ 2 cycles", PALE_AMBER, AMBER),
        ("Then · Human", "Not an AI agent\nSource trail · edit\n· export decision", PALE, DARK_BLUE),
    ]
    for i, (head, body, fill, accent) in enumerate(agents):
        x = 0.55 + i * 3.2
        rect(s, x, 3.2, 3.0, 1.55, fill, fill, True)
        rect(s, x, 3.2, 0.1, 1.55, accent, accent, False)
        label(s, head, x + 0.2, 3.3, 2.7, 0.3, 13, DARK_BLUE, True, PP_ALIGN.LEFT)
        label(s, body, x + 0.2, 3.65, 2.7, 0.95, 12, INK, False, PP_ALIGN.LEFT)
        if i < 3:
            arrow(s, x + 3.0, 3.95, x + 3.15, 3.95, MID_BLUE)

    # Runtime / controls strip (no “governed relay” jargon)
    rect(s, 0.55, 4.95, 12.2, 1.15, PALE_BLUE, PALE_BLUE, True)
    label(s, "Runtime path", 0.75, 5.05, 11.8, 0.28, 12, DARK_BLUE, True, PP_ALIGN.LEFT)
    label(
        s,
        "Browser → Agentrix server → Bayer AI Gateway (Entra) → Claude → back to UI\n"
        "Kill switch · daily budget · rate limits · secrets stay server-side  ·  Accepted by Regulatory · ARS reused the pattern",
        0.75, 5.4, 11.8, 0.55, 12, INK, False, PP_ALIGN.LEFT,
    )
    set_footer(s)

    # ------------------------------------------------------------------ 5 Value + production status (visual)
    s = prs.slides.add_slide(layout_by_name(prs, "Content"))
    set_text(ph(s, 13), "Value & status")
    set_text(ph(s, 0), "In production — and already reused")
    clear_body(s)

    # Big metrics row
    metrics = [
        ("88%", "field-level accuracy\non 5 golden labels", BRIGHT_GREEN, PALE_GREEN),
        ("~149→155", "pages → rows\n(that set only)", BRIGHT_BLUE, PALE_BLUE),
        ("1 or many", "labels per run\nrows always vary", MID_BLUE, PALE),
        ("Always", "human sign-off\nbefore use", AMBER, PALE_AMBER),
    ]
    for i, (num, cap, color, fill) in enumerate(metrics):
        x = 0.55 + i * 3.2
        rect(s, x, 2.05, 3.0, 1.85, fill, fill, True)
        label(s, num, x + 0.1, 2.2, 2.8, 0.55, 22, color, True)
        label(s, cap, x + 0.1, 2.85, 2.8, 0.8, 12, INK, False)

    label(
        s,
        "Golden-record numbers are an example from 5 labels used for comparison — not a fixed output size.",
        0.55, 4.05, 12.2, 0.35, 12, MUTED, False, PP_ALIGN.LEFT,
    )

    # Production status chips (facts, not open decisions)
    status = [
        ("Live on Agentrix", BRIGHT_GREEN),
        ("AI Gateway live", BRIGHT_BLUE),
        ("App daily cost cap", MID_BLUE),
        ("Accepted by Regulatory", DARK_BLUE),
        ("ARS agent built next", AMBER),
    ]
    for i, (text, fill) in enumerate(status):
        x = 0.55 + i * 2.55
        rect(s, x, 4.55, 2.4, 0.85, fill, fill, True)
        label(s, text, x + 0.08, 4.7, 2.24, 0.55, 12, WHITE, True)
    set_footer(s)

    # ------------------------------------------------------------------ 6 FAQ — accuracy, review, provenance
    s = prs.slides.add_slide(layout_by_name(prs, "Content"))
    set_text(ph(s, 13), "FAQ for first-time reviewers")
    set_text(ph(s, 0), "Accuracy, proofreading & human checks")
    clear_body(s)

    faqs_a = [
        ("Is the AI making regulatory decisions?",
         "No. It drafts rows. A human decides what is good enough. No EPA submit."),
        ("How accurate is it?",
         "~88% field-level on 5 golden-record labels — a strong draft, not skip-review."),
        ("Does it invent values?",
         "No. Silent label → NS. Not applicable → NA. ◆ = documented derivation rule."),
        ("How do I proofread / provenance?",
         "▸ expands page + source text. Filter Low confidence. Edit cells. Then Excel."),
        ("Do humans still check every table?",
         "Yes — AI draft → spot-check → human export. Value is speed + traceability."),
        ("What about the 3 review stations?",
         "On before export: document snapshot → extraction sanity → high-risk fields. Yes advances; No pauses to edit."),
    ]
    y = 2.0
    for q, a in faqs_a:
        label(s, "Q  " + q, 0.6, y, 12.1, 0.28, 12, DARK_BLUE, True, PP_ALIGN.LEFT)
        label(s, "A  " + a, 0.6, y + 0.28, 12.1, 0.32, 12, INK, False, PP_ALIGN.LEFT)
        y += 0.62
    set_footer(s)

    # ------------------------------------------------------------------ 7 FAQ — cost, compliance, cyber
    s = prs.slides.add_slide(layout_by_name(prs, "Content"))
    set_text(ph(s, 13), "FAQ for first-time reviewers")
    set_text(ph(s, 0), "Cost, compliance & cybersecurity")
    clear_body(s)

    faqs_b = [
        ("How much does a run cost?",
         "~$0.50–$0.75 per label on a normal path. Hard labels (Opus remediation) cost more."),
        ("How do you stop runaway spend?",
         "App daily budget (default $100/day), rate limit, kill switch, bounded remediation cycles."),
        ("Is this validated / can we submit AI output as-is?",
         "Treat as draft aid for submission prep. Human remains accountable for the table used."),
        ("Does label data leave Bayer?",
         "Calls go Browser → our relay → Bayer AI Gateway (Entra) → approved Claude. No model secret in the browser."),
        ("Cyber / prompt injection / exfiltration?",
         "Label text treated as data; injection phrases flagged; CSP connect-src self; human Apply for chat edits."),
        ("Audit trail — do you store raw labels?",
         "Audit is metadata only (time, status, tokens/cost, QC severity) — not raw label text."),
        ("Why use this if we still check?",
         "Checking a draft with page citations beats 100+ hours building from a blank sheet."),
    ]
    y = 1.95
    for q, a in faqs_b:
        label(s, "Q  " + q, 0.6, y, 12.1, 0.26, 12, DARK_BLUE, True, PP_ALIGN.LEFT)
        label(s, "A  " + a, 0.6, y + 0.26, 12.1, 0.30, 11, INK, False, PP_ALIGN.LEFT)
        y += 0.56
    set_footer(s)

    # ------------------------------------------------------------------ 8 FAQ — more EPA schemas
    s = prs.slides.add_slide(layout_by_name(prs, "Content"))
    set_text(ph(s, 13), "FAQ — future flexibility")
    set_text(ph(s, 0), "Can we support other EPA output schemas?")
    clear_body(s)

    label(s, "Short answer: Yes — same pipeline, new schema pack. Not a free toggle.", 0.6, 2.0, 12.1, 0.35, 14, DARK_BLUE, True, PP_ALIGN.LEFT)

    # Three difficulty cards
    cards = [
        ("Medium", "Close cousin of UST\n(rename / add fields,\nsame row meaning)", BRIGHT_GREEN, PALE_GREEN),
        ("Hard", "Different EPA table\n(new row grain, units,\nnew QC + goldens)", AMBER, PALE_AMBER),
        ("Not advisable", "“Any schema” with\nno SME rules —\naccuracy collapses", RED, PALE_RED),
    ]
    for i, (head, body, accent, fill) in enumerate(cards):
        x = 0.6 + i * 4.2
        rect(s, x, 2.5, 4.0, 1.85, fill, fill, True)
        label(s, head, x + 0.15, 2.65, 3.7, 0.35, 16, accent, True, PP_ALIGN.LEFT)
        label(s, body, x + 0.15, 3.15, 3.7, 1.0, 13, INK, False, PP_ALIGN.LEFT)

    label(s, "Architecture", 0.6, 4.55, 3, 0.28, 12, MUTED, True, PP_ALIGN.LEFT)
    label(
        s,
        "Label → choose Schema Pack (columns + rules + QC + goldens) → Extractor + QC agents → same review UI → Excel\n"
        "Agentrix · AI Gateway stay the same. Cost of a run stays similar; main cost is SME + build time.",
        0.6, 4.85, 12.1, 0.7, 12, INK, False, PP_ALIGN.LEFT,
    )
    set_footer(s)

    # ------------------------------------------------------------------ 9 Demo bridge
    s = prs.slides.add_slide(layout_by_name(prs, "Final Slide"))
    fill_picture_placeholders(s, HERO_IMAGE)
    set_text(ph(s, 1), "Next — live demo (~10 min)")
    set_text(ph(s, 0), "Upload · Extract · Review · Excel")
    set_text(
        ph(s, 13),
        "//////////\n"
        "One label in → reviewable table out, with source on every cell\n"
        "Karandeep Singh\n"
        "Agentrix + Bayer AI Gateway",
    )
    f = ph(s, 11) or ph(s, 16)
    if f:
        set_text(f, FOOTER, size=10)

    prs.save(str(OUT))
    print(f"Wrote {OUT}")
    print(f"Slides: {len(prs.slides)}  (incl. FAQ slides + demo handoff)")


if __name__ == "__main__":
    build()

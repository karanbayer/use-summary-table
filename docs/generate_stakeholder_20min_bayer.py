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
    set_text(ph(s, 1), "Bayer Life Sciences Regulatory")
    set_text(ph(s, 0), "Use Summary Tables Extractor")
    set_text(
        ph(s, 13),
        "Stakeholder briefing  ·  15 min slides + 10 min live demo\n"
        "Karandeep Singh  ·  BEAT04090032  ·  October 2026",
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
            "What we built: generic AI draft, fixed 28-col schema, human review",
            "How it runs: Agentrix · AI Gateway · Sonnet/Opus · cost & guardrails",
            "Proof & impact: golden-record accuracy · in production · ARS follow-on",
        ], BRIGHT_BLUE, PALE_BLUE),
        ("10 min", "Live demo", [
            "Upload a label → run extraction → inspect source on cells",
            "Edit a value → export Excel — the path regulatory users take",
        ], BRIGHT_GREEN, PALE_GREEN),
        ("Q&A", "Discussion", [
            "Questions after the demo — open floor",
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

    # ------------------------------------------------------------------ 4 How it works (visual flow)
    s = prs.slides.add_slide(layout_by_name(prs, "Content"))
    set_text(ph(s, 13), "How it works")
    set_text(ph(s, 0), "Process & architecture at a glance")
    clear_body(s)

    steps = [
        ("1", "Upload", "PDF label(s)"),
        ("2", "Extract", "AI + QC"),
        ("3", "Inspect", "Source trail"),
        ("4", "Correct", "Edit cells"),
        ("5", "Export", "Excel"),
    ]
    for i, (num, head, body) in enumerate(steps):
        x = 0.55 + i * 2.55
        rect(s, x, 2.1, 2.25, 1.55, PALE_BLUE if i % 2 == 0 else PALE_GREEN, None, True)
        rect(s, x + 0.7, 2.25, 0.85, 0.4, DARK_BLUE, DARK_BLUE, True)
        label(s, num, x + 0.7, 2.28, 0.85, 0.35, 14, WHITE, True)
        label(s, head, x + 0.1, 2.8, 2.05, 0.35, 15, DARK_BLUE, True)
        label(s, body, x + 0.1, 3.2, 2.05, 0.3, 12, MUTED, False)
        if i < 4:
            arrow(s, x + 2.25, 2.85, x + 2.45, 2.85, BRIGHT_BLUE)

    # Architecture strip
    label(s, "Under the hood", 0.55, 3.95, 3, 0.3, 12, MUTED, True, PP_ALIGN.LEFT)
    arch = [
        ("Browser UI", PALE),
        ("Governed relay", PALE_BLUE),
        ("AI Gateway", PALE_GREEN),
        ("Claude", PALE_AMBER),
        ("Human review", PALE_BLUE),
    ]
    for i, (text, fill) in enumerate(arch):
        x = 0.55 + i * 2.55
        node(s, x, 4.35, 2.25, 0.85, text, fill, DARK_BLUE)
        if i < 4:
            arrow(s, x + 2.25, 4.75, x + 2.45, 4.75, MID_BLUE)

    label(
        s,
        "Live on Agentrix  ·  Bayer AI Gateway  ·  Sonnet extract/QC  ·  Opus if High/Critical  ·  Accepted by Regulatory  ·  ARS agent reused the pattern",
        0.55, 5.45, 12.2, 0.35, 12, MUTED, False, PP_ALIGN.LEFT,
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

    # ------------------------------------------------------------------ 6 Demo bridge
    s = prs.slides.add_slide(layout_by_name(prs, "Final Slide"))
    set_text(ph(s, 1), "Next — live demo (~10 min)")
    set_text(ph(s, 0), "Upload · Extract · Review · Excel")
    set_text(
        ph(s, 13),
        "One label in → reviewable table out, with source on every cell\n"
        "Questions after the demo\n"
        "Karandeep Singh  ·  BEAT04090032  ·  Agentrix + Bayer AI Gateway",
    )
    f = ph(s, 11) or ph(s, 16)
    if f:
        set_text(f, FOOTER, size=10)

    prs.save(str(OUT))
    print(f"Wrote {OUT}")
    print(f"Slides: {len(prs.slides)}  (~15 min visual talk + 10 min demo)")


if __name__ == "__main__":
    build()

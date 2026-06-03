"""
Generates a beautiful meeting-minutes PDF from structured MeetingData.
Uses reportlab's Platypus framework for a clean, professional layout.
"""

import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable

from ai_processor import MeetingData

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#1B2B4B")
BLUE   = colors.HexColor("#3D7EAA")
LIGHT  = colors.HexColor("#EDF2F7")
ACCENT = colors.HexColor("#2D9CDB")
TEXT   = colors.HexColor("#1A202C")
MUTED  = colors.HexColor("#718096")
WHITE  = colors.white
GREEN  = colors.HexColor("#2D9561")
YELLOW = colors.HexColor("#D69E2E")
RED_BG = colors.HexColor("#FFF5F5")


# ── Custom flowables ──────────────────────────────────────────────────────────
class ColorBar(Flowable):
    """A full-width coloured banner (used for section headers)."""
    def __init__(self, text, bg=BLUE, fg=WHITE, font_size=11, height=0.7*cm):
        super().__init__()
        self.text = text
        self.bg = bg
        self.fg = fg
        self.font_size = font_size
        self._height = height

    def wrap(self, available_width, available_height):
        self._width = available_width
        return available_width, self._height

    def draw(self):
        c = self.canv
        c.setFillColor(self.bg)
        c.rect(0, 0, self._width, self._height, fill=1, stroke=0)
        c.setFillColor(self.fg)
        c.setFont("Helvetica-Bold", self.font_size)
        c.drawString(0.4*cm, 0.18*cm, self.text)


class HeaderBanner(Flowable):
    """The big header that spans the full page including margins."""
    def __init__(self, title, subtitle_lines, page_width, height=3.2*cm):
        super().__init__()
        self.title = title
        self.subtitle_lines = subtitle_lines
        self.page_width = page_width
        self._height = height

    def wrap(self, available_width, available_height):
        self._width = available_width
        return available_width, self._height

    def draw(self):
        c = self.canv
        w, h = self._width, self._height
        # background
        c.setFillColor(NAVY)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        # accent stripe
        c.setFillColor(ACCENT)
        c.rect(0, 0, 0.5*cm, h, fill=1, stroke=0)
        # title
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(1.0*cm, h - 1.1*cm, self.title)
        # subtitle lines
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#A0AEC0"))
        y = h - 1.8*cm
        for line in self.subtitle_lines:
            c.drawString(1.0*cm, y, line)
            y -= 0.5*cm


class Chip(Flowable):
    """Pill-shaped badge for a participant name."""
    PAD_X = 0.25*cm
    PAD_Y = 0.12*cm
    FONT  = "Helvetica"
    FSIZE = 9

    def __init__(self, text, bg=LIGHT, fg=NAVY):
        super().__init__()
        self.text = text
        self.bg = bg
        self.fg = fg
        self._w = None

    def wrap(self, available_width, available_height):
        self.canv.setFont(self.FONT, self.FSIZE)
        tw = self.canv.stringWidth(self.text, self.FONT, self.FSIZE)
        self._w = tw + 2 * self.PAD_X
        self._h = self.FSIZE * 1.1 + 2 * self.PAD_Y
        return self._w, self._h

    def draw(self):
        c = self.canv
        w, h = self._w, self._h
        r = h / 2
        c.setFillColor(self.bg)
        c.roundRect(0, 0, w, h, r, fill=1, stroke=0)
        c.setFillColor(self.fg)
        c.setFont(self.FONT, self.FSIZE)
        c.drawString(self.PAD_X, self.PAD_Y, self.text)


# ── Style sheet ───────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    def s(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "body": s("body", fontName="Helvetica", fontSize=10, leading=15,
                  textColor=TEXT, spaceAfter=4),
        "bullet": s("bullet", fontName="Helvetica", fontSize=10, leading=15,
                    textColor=TEXT, leftIndent=14, bulletIndent=4,
                    spaceAfter=3),
        "small": s("small", fontName="Helvetica", fontSize=8.5, leading=13,
                   textColor=MUTED),
        "bold": s("bold", fontName="Helvetica-Bold", fontSize=10,
                  leading=15, textColor=TEXT),
        "summary": s("summary", fontName="Helvetica-Oblique", fontSize=10.5,
                     leading=17, textColor=TEXT, spaceAfter=4),
        "next_meeting": s("next_meeting", fontName="Helvetica-Bold",
                          fontSize=10, leading=14, textColor=NAVY),
    }


# ── Page template (adds footer on every page) ─────────────────────────────────
def _add_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, 0.9*cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2*cm, 0.3*cm, "Meeting-Protokoll – vertraulich")
    canvas.drawRightString(w - 2*cm, 0.3*cm, f"Seite {doc.page}")
    canvas.restoreState()


# ── Main generator ────────────────────────────────────────────────────────────
def generate_pdf(data: MeetingData) -> bytes:
    buf = io.BytesIO()
    W, H = A4
    ML = MR = 2 * cm
    MT = 2 * cm
    MB = 2 * cm

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB + 1.2*cm,
    )
    frame = Frame(ML, MB + 1.2*cm, W - ML - MR, H - MT - MB - 1.2*cm,
                  id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame],
                                       onPage=_add_footer)])

    ST = _styles()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    subtitle = []
    if data.date:
        subtitle.append(f"Datum: {data.date}" +
                        (f"  ·  Uhrzeit: {data.time}" if data.time else ""))
    if data.location:
        subtitle.append(f"Ort: {data.location}")

    story.append(HeaderBanner(data.title, subtitle, W - ML - MR))
    story.append(Spacer(1, 0.5*cm))

    # ── Participants ───────────────────────────────────────────────────────────
    if data.participants:
        story.append(ColorBar("  TEILNEHMER", NAVY))
        story.append(Spacer(1, 0.25*cm))

        # build chip rows manually as a table
        chip_data = []
        row = []
        COL = 4
        for i, p in enumerate(data.participants):
            row.append(Paragraph(f"<b>{p}</b>", ST["small"]))
            if len(row) == COL:
                chip_data.append(row)
                row = []
        if row:
            row += [""] * (COL - len(row))
            chip_data.append(row)

        if chip_data:
            col_w = (W - ML - MR) / COL
            t = Table(chip_data, colWidths=[col_w] * COL)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT, WHITE]),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ]))
            story.append(t)

        if data.absent:
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(
                "Entschuldigt: " + ", ".join(data.absent), ST["small"]))
        story.append(Spacer(1, 0.5*cm))

    # ── Summary ────────────────────────────────────────────────────────────────
    if data.summary:
        story.append(ColorBar("  ZUSAMMENFASSUNG", BLUE))
        story.append(Spacer(1, 0.25*cm))
        # light blue background box
        summary_table = Table(
            [[Paragraph(data.summary, ST["summary"])]],
            colWidths=[W - ML - MR],
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EBF4FB")),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 1, ACCENT),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.5*cm))

    # ── Topics ─────────────────────────────────────────────────────────────────
    if data.topics:
        story.append(ColorBar("  BESPROCHENE THEMEN", NAVY))
        story.append(Spacer(1, 0.2*cm))
        for topic in data.topics:
            story.append(Paragraph(f"<bullet>•</bullet> {topic}", ST["bullet"]))
        story.append(Spacer(1, 0.4*cm))

    # ── Decisions ──────────────────────────────────────────────────────────────
    if data.decisions:
        story.append(ColorBar("  ENTSCHEIDUNGEN", colors.HexColor("#276749")))
        story.append(Spacer(1, 0.2*cm))
        for decision in data.decisions:
            d_table = Table(
                [[Paragraph(f"✓  {decision}", ST["body"])]],
                colWidths=[W - ML - MR],
            )
            d_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FFF4")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9AE6B4")),
            ]))
            story.append(d_table)
            story.append(Spacer(1, 0.15*cm))
        story.append(Spacer(1, 0.35*cm))

    # ── Action Items ───────────────────────────────────────────────────────────
    if data.action_items:
        story.append(ColorBar("  AUFGABEN", colors.HexColor("#7B341E")))
        story.append(Spacer(1, 0.25*cm))

        header_row = [
            Paragraph("<b>Aufgabe</b>", ST["bold"]),
            Paragraph("<b>Verantwortlich</b>", ST["bold"]),
            Paragraph("<b>Fällig</b>", ST["bold"]),
        ]
        rows = [header_row]
        for item in data.action_items:
            rows.append([
                Paragraph(item.task, ST["body"]),
                Paragraph(item.owner or "–", ST["body"]),
                Paragraph(item.due_date or "–", ST["body"]),
            ])

        cw = W - ML - MR
        t = Table(rows, colWidths=[cw * 0.55, cw * 0.25, cw * 0.20])
        ts = [
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [WHITE, colors.HexColor("#F7FAFC")]),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

    # ── Open questions ─────────────────────────────────────────────────────────
    if data.open_questions:
        story.append(ColorBar("  OFFENE FRAGEN", colors.HexColor("#553C9A")))
        story.append(Spacer(1, 0.2*cm))
        for q in data.open_questions:
            story.append(Paragraph(f"<bullet>?</bullet> {q}", ST["bullet"]))
        story.append(Spacer(1, 0.4*cm))

    # ── Next steps ─────────────────────────────────────────────────────────────
    if data.next_steps:
        story.append(ColorBar("  NÄCHSTE SCHRITTE", NAVY))
        story.append(Spacer(1, 0.2*cm))
        for step in data.next_steps:
            story.append(Paragraph(f"<bullet>→</bullet> {step}", ST["bullet"]))
        story.append(Spacer(1, 0.4*cm))

    # ── Next meeting ───────────────────────────────────────────────────────────
    if data.next_meeting:
        nm_table = Table(
            [[Paragraph(f"\U0001f4c5  Nächstes Meeting: {data.next_meeting}",
                        ST["next_meeting"])]],
            colWidths=[W - ML - MR],
        )
        nm_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EBF4FB")),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 1.5, ACCENT),
        ]))
        story.append(nm_table)

    doc.build(story)
    return buf.getvalue()

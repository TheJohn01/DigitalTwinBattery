"""A small document builder: the same report content as PDF (ReportLab) or Word (python-docx).

A report is a list of blocks: headings, paragraphs, tables (numbered, caption above) and
figures (matplotlib, numbered, caption below). Paragraph text may use <b>bold</b> and <sub>subscript</sub>; both
formats render them.
"""
import math
import re
from datetime import date
from io import BytesIO

import numpy as np
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Table, TableStyle)

from . import __version__

# House style: Trebuchet MS 11 pt, justified, line spacing 1.5, 12 pt before each paragraph;
# tables with three rules (above and below the header, below the last row), header bold and
# centred. Word documents name the font; a PDF needs the font file, read from the usual
# places (Trebuchet MS is Microsoft's, so it is not shipped here).
FONT_NAME, SIZE, LINE, BEFORE = "Trebuchet MS", 11, 1.5, 12
_FONT_FILES = [("C:/Windows/Fonts/trebuc.ttf", "C:/Windows/Fonts/trebucbd.ttf"),
               ("/Library/Fonts/Trebuchet MS.ttf", "/Library/Fonts/Trebuchet MS Bold.ttf"),
               ("/System/Library/Fonts/Supplemental/Trebuchet MS.ttf",
                "/System/Library/Fonts/Supplemental/Trebuchet MS Bold.ttf"),
               ("/usr/share/fonts/truetype/msttcorefonts/Trebuchet_MS.ttf",
                "/usr/share/fonts/truetype/msttcorefonts/Trebuchet_MS_Bold.ttf")]


def _pdf_fonts():
    """(regular, bold) font names for ReportLab: Trebuchet MS if its files are found."""
    for regular, bold in _FONT_FILES:
        try:
            pdfmetrics.registerFont(TTFont("Trebuchet", regular))
            pdfmetrics.registerFont(TTFont("Trebuchet-Bold", bold))
            pdfmetrics.registerFontFamily("Trebuchet", normal="Trebuchet", bold="Trebuchet-Bold")
            return "Trebuchet", "Trebuchet-Bold"
        except Exception:          # file missing on this computer: try the next place
            continue
    return "Helvetica", "Helvetica-Bold"      # shortcut: install Trebuchet MS for the house font


_FONT, _BOLD = _pdf_fonts()
_styles = getSampleStyleSheet()
_BODY = ParagraphStyle("Body", parent=_styles["BodyText"], fontName=_FONT, fontSize=SIZE,
                       leading=LINE * SIZE, spaceBefore=BEFORE, alignment=TA_JUSTIFY)
_PDF_STYLES = {
    "h1": ParagraphStyle("H1", parent=_BODY, fontName=_BOLD, fontSize=15, leading=LINE * 15,
                         alignment=0, spaceAfter=6),
    "h2": ParagraphStyle("H2", parent=_BODY, fontName=_BOLD, fontSize=12, leading=LINE * 12,
                         alignment=0),
    "body": _BODY,
    "small": _BODY,
    "box": ParagraphStyle("Box", parent=_BODY, backColor=colors.HexColor("#FFF4D6"),
                          borderColor=colors.HexColor("#C99A00"), borderWidth=0.6,
                          borderPadding=6, spaceAfter=10),
}
_CELL = ParagraphStyle("Cell", parent=_BODY, spaceBefore=0)
_HEAD = ParagraphStyle("Head", parent=_CELL, fontName=_BOLD, alignment=TA_CENTER)
RULE = 1.5                     # pt, the three rules of a table
_TAG = re.compile(r"(</?b>|</?sub>)")
_AMP = re.compile(r"&(?!amp;|lt;|gt;)")


def fmt_number(x, decimals=0, missing="n/a"):
    """Format a number with thousands separators; words instead of a blank when there is
    no number (None, NaN, inf). Used by the dashboard and both reports."""
    if x is None or not math.isfinite(x):
        return missing
    return f"{x:,.{decimals}f}"


def _escape(text):
    """Escape a bare & for ReportLab (its markup treats & as the start of an entity)."""
    return _AMP.sub("&amp;", text)


class Report:
    def __init__(self, title, footer):
        self.title, self.footer, self.blocks, self.figures, self.tables = title, footer, [], 0, 0

    def intro(self, extra=""):
        """The statement box and the 'how this report was made' note of every report."""
        self.p(f"<b>{self.footer}.</b>", "box")
        self.p(f"Generated {date.today().isoformat()} by Battery Digital Twin v{__version__} "
               "from one simulation run. This is a model report (mock-up) for a student "
               "project: every number comes from the simulation, from the cited literature or "
               f"from an assumption marked as such{extra}.", "small")

    def h1(self, text):
        self.blocks.append(("h1", text))

    def h2(self, text):
        self.blocks.append(("h2", text))

    def p(self, text, style="body"):
        self.blocks.append((style, text))

    def table(self, rows, widths_cm, caption):
        """A table with "Table n." and its caption above it."""
        self.tables += 1
        self.blocks.append(("table", [[str(c) for c in r] for r in rows], widths_cm,
                            f"<b>Table {self.tables}.</b> {caption}"))

    def figure(self, fig, caption, width_cm=15.0):
        """A matplotlib Figure (closed here) with "Figure n." in front of its caption."""
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        w, h = fig.get_size_inches()
        self.figures += 1
        self.blocks.append(("figure", buf.getvalue(), f"<b>Figure {self.figures}.</b> {caption}",
                            width_cm, width_cm * h / w))

    # --- PDF -----------------------------------------------------------------------------
    def pdf(self):
        story, chapters = [], 0
        for block in self.blocks:
            if block[0] == "h1":                       # each chapter starts on a new page
                chapters += 1
                if chapters > 1:
                    story.append(PageBreak())
            if block[0] == "figure":
                _, png, caption, w, h = block
                story.append(KeepTogether([Image(BytesIO(png), width=w * cm, height=h * cm),
                                           Paragraph(_escape(caption), _PDF_STYLES["small"])]))
            elif block[0] == "table":
                _, rows, widths, caption = block
                t = Table([[Paragraph(_escape(c), _HEAD if k == 0 else _CELL) for c in r]
                           for k, r in enumerate(rows)],
                          colWidths=[w * cm for w in widths], repeatRows=1)
                t.setStyle(TableStyle([
                    ("LINEABOVE", (0, 0), (-1, 0), RULE, colors.black),
                    ("LINEBELOW", (0, 0), (-1, 0), RULE, colors.black),
                    ("LINEBELOW", (0, -1), (-1, -1), RULE, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), BEFORE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
                cap = Paragraph(_escape(caption), _PDF_STYLES["small"])
                # a long table may split across pages; a short one stays with its caption
                story += [KeepTogether([cap, t])] if len(rows) < 15 else [cap, t]
            else:
                story.append(Paragraph(_escape(block[1]), _PDF_STYLES[block[0]]))
        buf = BytesIO()

        def footer(canvas, doc):
            canvas.saveState()
            canvas.setFont(_FONT, 7.5)
            canvas.drawString(2 * cm, 1.2 * cm, f"{self.footer}  |  {doc.page}")
            canvas.restoreState()

        SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                          topMargin=1.8 * cm, bottomMargin=1.8 * cm, title=self.title,
                          author="Battery Digital Twin").build(story, onFirstPage=footer,
                                                             onLaterPages=footer)
        return buf.getvalue()

    # --- Word ----------------------------------------------------------------------------
    def docx(self):
        doc = Document()
        section = doc.sections[0]
        section.page_width, section.page_height = Cm(21.0), Cm(29.7)        # A4
        for side in ("left_margin", "right_margin"):
            setattr(section, side, Cm(2))
        section.top_margin = section.bottom_margin = Cm(1.8)
        normal = doc.styles["Normal"]
        normal.font.name, normal.font.size = FONT_NAME, Pt(SIZE)
        normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        normal.paragraph_format.line_spacing = LINE
        normal.paragraph_format.space_before = Pt(BEFORE)
        for name in ("Heading 1", "Heading 2"):
            heading = doc.styles[name]
            heading.font.name, heading.font.color.rgb = FONT_NAME, RGBColor(0, 0, 0)
            heading.paragraph_format.line_spacing = LINE
            heading.paragraph_format.space_before = Pt(BEFORE)
        doc.core_properties.title = self.title
        doc.core_properties.author = "Battery Digital Twin"
        footer = section.footer.paragraphs[0]
        footer.text = f"{self.footer}  |  "
        page = OxmlElement("w:fldSimple")              # the page number, filled in by Word
        page.set(qn("w:instr"), "PAGE")
        footer._p.append(page)
        footer.runs[0].font.size = Pt(7.5)

        chapters = 0
        for block in self.blocks:
            kind = block[0]
            if kind == "figure":
                _, png, caption, w, _ = block
                doc.add_picture(BytesIO(png), width=Cm(w))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                _add_runs(doc.add_paragraph(), caption)
            elif kind in ("h1", "h2"):
                heading = doc.add_heading(_plain(block[1]), level=1 if kind == "h1" else 2)
                if kind == "h1":
                    chapters += 1
                    heading.paragraph_format.page_break_before = chapters > 1
            elif kind == "table":
                _, rows, widths, caption = block
                _add_runs(doc.add_paragraph(), caption)
                t = doc.add_table(rows=len(rows), cols=len(rows[0]))
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                header = OxmlElement("w:tblHeader")    # the header row repeats on each page
                t.rows[0]._tr.get_or_add_trPr().append(header)
                t.autofit = False
                for j, w in enumerate(widths):
                    t.columns[j].width = Cm(w)
                for i, row in enumerate(rows):
                    for j, text in enumerate(row):
                        cell = t.cell(i, j)
                        cell.width = Cm(widths[j])
                        par = cell.paragraphs[0]
                        _add_runs(par, f"<b>{text}</b>" if i == 0 else text)
                        if i == 0:
                            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        _rules(cell, top=i <= 1, bottom=i in (0, len(rows) - 1))
                doc.add_paragraph()
            else:
                par = doc.add_paragraph()
                _add_runs(par, block[1])
                if kind == "box":
                    _shade(par._p.get_or_add_pPr(), "FFF4D6")
        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()


def _plain(text):
    return _TAG.sub("", text)


def _rules(cell, top, bottom):
    """The table rules of the house style on one Word cell (RULE pt, nothing else)."""
    borders = OxmlElement("w:tcBorders")
    for edge, on in (("top", top), ("bottom", bottom)):
        if on:
            line = OxmlElement(f"w:{edge}")
            for key, value in (("val", "single"), ("sz", str(int(RULE * 8))), ("space", "0"),
                               ("color", "000000")):
                line.set(qn(f"w:{key}"), value)
            borders.append(line)
    cell._tc.get_or_add_tcPr().append(borders)


def _add_runs(paragraph, text):
    """Add text with <b> and <sub> markup as formatted runs."""
    bold = sub = False
    for part in _TAG.split(text):
        if part in ("<b>", "</b>"):
            bold = part == "<b>"
        elif part in ("<sub>", "</sub>"):
            sub = part == "<sub>"
        elif part:
            run = paragraph.add_run(part.replace("&amp;", "&").replace("&lt;", "<")
                                    .replace("&gt;", ">"))
            run.bold, run.font.subscript = bold, sub
            run.font.color.rgb = RGBColor(0, 0, 0)


def _shade(properties, hex_colour):
    """Background colour for a table cell (tcPr) or a paragraph (pPr)."""
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:fill"), hex_colour)
    properties.append(shading)


BLUE, GREY = "#26a6e8", "#7f7f7f"


def capacity_figure(curve, cycles_per_year, years, threshold, threshold_label):
    """Capacity [% of new] over the years of operation, with a dashed threshold line."""
    n = min(len(curve), int(cycles_per_year * years))
    fig = Figure(figsize=(7, 2.8))
    ax = fig.subplots()
    ax.plot(np.arange(1, n + 1) / cycles_per_year, 100 * np.asarray(curve[:n]), color=BLUE)
    ax.axhline(100 * threshold, ls="--", color=GREY, label=threshold_label)
    ax.set(xlabel="Years of operation", ylabel="Capacity [% of new]")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    return fig

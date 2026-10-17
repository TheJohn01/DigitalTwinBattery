"""A small document builder: the same report content as PDF (ReportLab) or Word (python-docx).

A report is a list of blocks: headings, paragraphs and tables. Paragraph text may use
<b>bold</b> and <sub>subscript</sub>; both formats render them.
"""
import math
import re
from datetime import date
from io import BytesIO

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from . import __version__

_styles = getSampleStyleSheet()
_PDF_STYLES = {
    "h1": ParagraphStyle("H1", parent=_styles["Heading1"], fontSize=15, spaceBefore=12,
                         spaceAfter=6),
    "h2": ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=12, spaceBefore=8,
                         spaceAfter=4),
    "body": ParagraphStyle("Body", parent=_styles["BodyText"], fontSize=9.5, leading=13),
    "small": ParagraphStyle("Small", parent=_styles["BodyText"], fontSize=8, leading=10),
    "box": ParagraphStyle("Box", parent=_styles["BodyText"], fontSize=9.5, leading=13,
                          backColor=colors.HexColor("#FFF4D6"),
                          borderColor=colors.HexColor("#C99A00"), borderWidth=0.6,
                          borderPadding=6, spaceBefore=6, spaceAfter=10),
}
_CELL = ParagraphStyle("Cell", parent=_styles["BodyText"], fontSize=8, leading=10)
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
        self.title, self.footer, self.blocks = title, footer, []

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

    def table(self, rows, widths_cm):
        self.blocks.append(("table", [[str(c) for c in r] for r in rows], widths_cm))

    # --- PDF -----------------------------------------------------------------------------
    def pdf(self):
        story = []
        for block in self.blocks:
            if block[0] == "table":
                _, rows, widths = block
                t = Table([[Paragraph(_escape(c), _CELL) for c in r] for r in rows],
                          colWidths=[w * cm for w in widths], repeatRows=1)
                t.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF6"))]))
                story.append(t)
            else:
                story.append(Paragraph(_escape(block[1]), _PDF_STYLES[block[0]]))
        buf = BytesIO()

        def footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(2 * cm, 1.2 * cm, f"{self.footer}  |  page {doc.page}")
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
        doc.styles["Normal"].font.name = "Arial"
        doc.styles["Normal"].font.size = Pt(10)
        doc.core_properties.title = self.title
        doc.core_properties.author = "Battery Digital Twin"
        footer = section.footer.paragraphs[0]
        footer.text = self.footer
        footer.runs[0].font.size = Pt(7.5)

        for block in self.blocks:
            kind = block[0]
            if kind in ("h1", "h2"):
                doc.add_heading(_plain(block[1]), level=1 if kind == "h1" else 2)
            elif kind == "table":
                _, rows, widths = block
                t = doc.add_table(rows=len(rows), cols=len(rows[0]))
                t.style = "Table Grid"
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                t.autofit = False
                for j, w in enumerate(widths):
                    t.columns[j].width = Cm(w)
                for i, row in enumerate(rows):
                    for j, text in enumerate(row):
                        cell = t.cell(i, j)
                        cell.width = Cm(widths[j])
                        par = cell.paragraphs[0]
                        _add_runs(par, f"<b>{text}</b>" if i == 0 else text, size=8)
                        if i == 0:
                            _shade(cell._tc.get_or_add_tcPr(), "E8EEF6")
                doc.add_paragraph()
            else:
                par = doc.add_paragraph()
                _add_runs(par, block[1], size=8 if kind == "small" else 10)
                if kind == "box":
                    _shade(par._p.get_or_add_pPr(), "FFF4D6")
        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()


def _plain(text):
    return _TAG.sub("", text)


def _add_runs(paragraph, text, size=10):
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
            run.bold, run.font.subscript, run.font.size = bold, sub, Pt(size)
            run.font.color.rgb = RGBColor(0, 0, 0)


def _shade(properties, hex_colour):
    """Background colour for a table cell (tcPr) or a paragraph (pPr)."""
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:fill"), hex_colour)
    properties.append(shading)

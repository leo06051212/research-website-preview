from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import html
import os
from pathlib import Path
import tempfile

from PIL import Image
from pypdf import PdfReader
import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
)

from scripts.cv_data import CvDocument, OWNER_ID, OWNER_NAME


NAVY = colors.HexColor("#1F4B66")
TEXT = colors.HexColor("#243746")
MUTED = colors.HexColor("#526777")
RAIL = colors.HexColor("#E5EDF2")
WHITE = colors.white


@dataclass(frozen=True)
class PdfBuildResult:
    output: Path
    page_count: int
    byte_count: int


class _EntryParagraph(Paragraph):
    """Move compact CV entries intact when the current frame is too short."""

    def split(self, availWidth: float, availHeight: float) -> list:
        return []


def register_cv_fonts() -> None:
    font_dir = Path(reportlab.__file__).resolve().parent / "fonts"
    font_files = {
        "CvSans": "Vera.ttf",
        "CvSans-Bold": "VeraBd.ttf",
        "CvSans-Italic": "VeraIt.ttf",
        "CvSans-BoldItalic": "VeraBI.ttf",
    }
    for name, filename in font_files.items():
        path = font_dir / filename
        if not path.is_file():
            raise ValueError(f"Required embedded font is missing: {path}")
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily(
        "CvSans",
        normal="CvSans",
        bold="CvSans-Bold",
        italic="CvSans-Italic",
        boldItalic="CvSans-BoldItalic",
    )


def validate_pdf(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    if len(payload) < 10_000 or not payload.startswith(b"%PDF-"):
        raise ValueError(f"Generated CV is not a non-trivial PDF: {path}")
    reader = PdfReader(path)
    if not reader.pages:
        raise ValueError(f"Generated CV has no pages: {path}")
    required = (OWNER_NAME, "Publications", "Academic CV")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    missing = [value for value in required if value not in text]
    if missing:
        raise ValueError(
            f"Generated CV is missing required text: {', '.join(missing)}"
        )
    return len(reader.pages), len(payload)


def render_cv_pdf(
    document: CvDocument,
    portrait: Path,
    output: Path,
    generated_on: date,
) -> PdfBuildResult:
    portrait = portrait.resolve()
    if not portrait.is_file():
        raise ValueError(f"Portrait is missing: {portrait}")
    register_cv_fonts()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        _build_document(document, portrait, temporary, generated_on)
        page_count, byte_count = validate_pdf(temporary)
        os.replace(temporary, output)
        return PdfBuildResult(output, page_count, byte_count)
    finally:
        temporary.unlink(missing_ok=True)


def _xml(value: object) -> str:
    return html.escape(str(value), quote=True)


def _link(label: str, url: str) -> str:
    return f'<link href="{_xml(url)}" color="#1F4B66">{_xml(label)}</link>'


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "body": ParagraphStyle(
            "CvBody",
            fontName="CvSans",
            fontSize=8.7,
            leading=11.2,
            textColor=TEXT,
            spaceAfter=4.5,
        ),
        "heading": ParagraphStyle(
            "CvHeading",
            fontName="CvSans-Bold",
            fontSize=12.5,
            leading=15,
            textColor=NAVY,
            spaceBefore=8,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "entry": ParagraphStyle(
            "CvEntry",
            parent=None,
            fontName="CvSans",
            fontSize=8.7,
            leading=11.2,
            textColor=TEXT,
            spaceAfter=6,
        ),
        "rail": ParagraphStyle(
            "CvRail",
            fontName="CvSans",
            fontSize=7.3,
            leading=9.2,
            textColor=TEXT,
            spaceAfter=3,
        ),
        "rail_heading": ParagraphStyle(
            "CvRailHeading",
            fontName="CvSans-Bold",
            fontSize=9,
            leading=11,
            textColor=NAVY,
            spaceBefore=5,
            spaceAfter=3,
        ),
    }


def _build_document(
    document: CvDocument,
    portrait: Path,
    temporary: Path,
    generated_on: date,
) -> None:
    page_width, page_height = A4
    footer_height = 14 * mm
    first_frame = Frame(
        60 * mm,
        footer_height,
        page_width - 78 * mm,
        page_height - footer_height - 16 * mm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="first-content",
    )
    continuation_frame = Frame(
        18 * mm,
        footer_height,
        page_width - 36 * mm,
        page_height - footer_height - 16 * mm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="continuation-content",
    )

    def first_page(canvas, doc) -> None:
        doc.handle_nextPageTemplate("continuation")
        _draw_rail(canvas, document, portrait)
        _draw_footer(canvas, doc.page, generated_on)

    def continuation_page(canvas, doc) -> None:
        _draw_footer(canvas, doc.page, generated_on)

    pdf = BaseDocTemplate(
        str(temporary),
        pagesize=A4,
        pageTemplates=[
            PageTemplate("first", [first_frame], onPage=first_page),
            PageTemplate(
                "continuation", [continuation_frame], onPage=continuation_page
            ),
        ],
        title=f"{OWNER_NAME} - Academic CV",
        author=OWNER_NAME,
        subject="Academic curriculum vitae",
    )
    styles = _styles()
    story = _story(document, styles)
    pdf.build(story)


def _draw_aspect_fill(canvas, portrait: Path, x: float, y: float, width: float, height: float) -> None:
    with Image.open(portrait) as image:
        image_width, image_height = image.size
    if image_width <= 0 or image_height <= 0:
        raise ValueError(f"Portrait has invalid dimensions: {portrait}")
    scale = max(width / image_width, height / image_height)
    drawn_width = image_width * scale
    drawn_height = image_height * scale
    drawn_x = x + (width - drawn_width) / 2
    drawn_y = y + (height - drawn_height) / 2
    canvas.saveState()
    clipping = canvas.beginPath()
    clipping.rect(x, y, width, height)
    canvas.clipPath(clipping, stroke=0, fill=0)
    canvas.drawImage(
        str(portrait),
        drawn_x,
        drawn_y,
        drawn_width,
        drawn_height,
        preserveAspectRatio=False,
        mask="auto",
    )
    canvas.restoreState()


def _draw_paragraph(canvas, markup: str, style: ParagraphStyle, x: float, y: float, width: float) -> float:
    paragraph = Paragraph(markup, style)
    _, height = paragraph.wrap(width, A4[1])
    paragraph.drawOn(canvas, x, y - height)
    return y - height - style.spaceAfter


def _draw_rail(canvas, document: CvDocument, portrait: Path) -> None:
    page_height = A4[1]
    rail_width = 52 * mm
    inset = 7 * mm
    content_width = rail_width - 2 * inset
    canvas.saveState()
    canvas.setFillColor(RAIL)
    canvas.rect(0, 0, rail_width, page_height, stroke=0, fill=1)
    portrait_height = 49 * mm
    _draw_aspect_fill(
        canvas,
        portrait,
        inset,
        page_height - inset - portrait_height,
        content_width,
        portrait_height,
    )
    styles = _styles()
    y = page_height - inset - portrait_height - 6 * mm
    y = _draw_paragraph(
        canvas,
        f'<font name="CvSans-Bold" size="11.5">{_xml(OWNER_NAME)}</font>',
        styles["rail"],
        inset,
        y,
        content_width,
    )
    postnominals = ", ".join(document.author.postnominals)
    if postnominals:
        y = _draw_paragraph(canvas, _xml(postnominals), styles["rail"], inset, y, content_width)
    y = _draw_paragraph(
        canvas,
        f"<b>{_xml(document.author.role)}</b>",
        styles["rail"],
        inset,
        y,
        content_width,
    )
    y = _draw_paragraph(
        canvas,
        _link(document.author.affiliation, document.author.affiliation_url),
        styles["rail"],
        inset,
        y,
        content_width,
    )
    for item in document.author.links:
        y = _draw_paragraph(
            canvas,
            _link(item.label, item.url),
            styles["rail"],
            inset,
            y,
            content_width,
        )
    y -= 2 * mm
    y = _draw_paragraph(canvas, "Research Interests", styles["rail_heading"], inset, y, content_width)
    interests = "<br/>".join(f"- {_xml(item)}" for item in document.author.interests)
    y = _draw_paragraph(canvas, interests, styles["rail"], inset, y, content_width)
    y = _draw_paragraph(canvas, "Education", styles["rail_heading"], inset, y, content_width)
    for item in document.author.education:
        y = _draw_paragraph(
            canvas,
            f"<b>{_xml(item.degree)}</b><br/>{_xml(item.institution)}, {_xml(item.year)}",
            styles["rail"],
            inset,
            y,
            content_width,
        )
    canvas.restoreState()


def _draw_footer(canvas, page_number: int, generated_on: date) -> None:
    canvas.saveState()
    canvas.setFont("CvSans", 7.2)
    canvas.setFillColor(MUTED)
    baseline = 7.5 * mm
    canvas.drawString(18 * mm, baseline, f"{OWNER_NAME} · Academic CV")
    canvas.drawCentredString(
        A4[0] / 2,
        baseline,
        f"Generated {generated_on.strftime('%d %B %Y')}",
    )
    canvas.drawRightString(A4[0] - 18 * mm, baseline, str(page_number))
    canvas.restoreState()


def _story(document: CvDocument, styles: dict[str, ParagraphStyle]):
    story = []

    def section(title: str, entries: list[Paragraph]) -> None:
        heading = Paragraph(_xml(title), styles["heading"])
        if entries:
            story.append(KeepTogether([heading, entries[0]]))
            story.extend(entries[1:])
        else:
            story.append(heading)

    section(
        "Academic Profile",
        [Paragraph(_xml(document.author.profile), styles["body"])],
    )
    appointment = (
        f"<b>{_xml(document.author.role)}</b><br/>"
        f"{_link(document.author.affiliation, document.author.affiliation_url)}"
    )
    section(
        "Current Academic Appointment",
        [_EntryParagraph(appointment, styles["entry"])],
    )

    publication_entries = []
    for publication in document.publications:
        authors = ", ".join(
            f"<b>{_xml(OWNER_NAME)}</b>" if author == OWNER_ID else _xml(author)
            for author in publication.authors
        )
        citation_parts = [f"<i>{_xml(publication.venue)}</i>"]
        if publication.volume:
            citation_parts.append(_xml(publication.volume))
        if publication.issue:
            citation_parts.append(f"({_xml(publication.issue)})")
        if publication.pages:
            citation_parts.append(_xml(publication.pages))
        elif publication.article_number:
            citation_parts.append(_xml(publication.article_number))
        citation_parts.append(str(publication.published.year))
        links = []
        if publication.doi:
            links.append(_link(f"doi:{publication.doi}", f"https://doi.org/{publication.doi}"))
        if publication.source_url:
            links.append(_link("source", publication.source_url))
        link_line = f"<br/>{' · '.join(links)}" if links else ""
        publication_entries.append(
            _EntryParagraph(
                f"<b>{_xml(publication.title)}</b><br/>{authors}<br/>"
                f"{', '.join(citation_parts)}{link_line}",
                styles["entry"],
            )
        )
    section("Publications", publication_entries)

    talk_entries = []
    for talk in document.talks:
        details = [talk.event, talk.venue, talk.location]
        visible = [_xml(value) for value in details if value]
        source = f"<br/>{_link('source', talk.source_url)}" if talk.source_url else ""
        talk_entries.append(
            _EntryParagraph(
                f"<b>{_xml(talk.title)}</b><br/>{', '.join(visible)}, "
                f"{talk.date.strftime('%d %B %Y')}{source}",
                styles["entry"],
            )
        )
    section("Invited Talks & Presentations", talk_entries)

    teaching_entries = []
    for teaching in document.teaching:
        details = [teaching.teaching_type, teaching.venue, teaching.location]
        visible = [_xml(value) for value in details if value]
        body = " ".join(teaching.body.split())
        body_line = f"<br/>{_xml(body)}" if body else ""
        teaching_entries.append(
            _EntryParagraph(
                f"<b>{_xml(teaching.title)}</b><br/>{', '.join(visible)}{body_line}",
                styles["entry"],
            )
        )
    section("Teaching & Postgraduate Supervision", teaching_entries)
    story.append(Spacer(1, 2 * mm))
    return story

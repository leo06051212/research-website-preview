from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import html
import os
from pathlib import Path
import re
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
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
)

from scripts.cv_data import (
    CvDocument,
    MANDATORY_CV_TEXT,
    OWNER_ID,
    OWNER_NAME,
    cv_content_counts,
    cv_content_manifest,
)


NAVY = colors.HexColor("#1F4B66")
TEXT = colors.HexColor("#243746")
MUTED = colors.HexColor("#526777")
RAIL = colors.HexColor("#E5EDF2")
WHITE = colors.white
FULL_CONTENT_FRAME_HEIGHT = A4[1] - 30 * mm
RAIL_CONTENT_BOTTOM = 14 * mm


@dataclass(frozen=True)
class PdfBuildResult:
    output: Path
    page_count: int
    byte_count: int


class _EntryParagraph(Paragraph):
    """Move compact CV entries intact when the current frame is too short."""

    def split(self, availWidth: float, availHeight: float) -> list:
        _, full_height = self.wrap(availWidth, FULL_CONTENT_FRAME_HEIGHT)
        if full_height <= FULL_CONTENT_FRAME_HEIGHT:
            return []
        return super().split(availWidth, availHeight)


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
    if "STSong-Light" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def validate_pdf(path: Path, expected_manifest: str | None = None) -> tuple[int, int]:
    payload = path.read_bytes()
    if len(payload) < 10_000 or not payload.startswith(b"%PDF-"):
        raise ValueError(f"Generated CV is not a non-trivial PDF: {path}")
    reader = PdfReader(path)
    if not reader.pages:
        raise ValueError(f"Generated CV has no pages: {path}")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    missing = [value for value in MANDATORY_CV_TEXT if value not in text]
    if missing:
        raise ValueError(
            f"Generated CV is missing required text: {', '.join(missing)}"
        )
    if expected_manifest is not None:
        subject = str(reader.metadata.subject or "")
        if subject != expected_manifest:
            raise ValueError(
                "Generated CV content manifest does not match the loaded document: "
                f"expected {expected_manifest!r}, found {subject!r}"
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
    _validate_portrait(portrait)
    register_cv_fonts()
    _validate_rail_capacity(document)
    manifest = cv_content_manifest(cv_content_counts(document))
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
        _build_document(document, portrait, temporary, generated_on, manifest)
        page_count, byte_count = validate_pdf(temporary, manifest)
        os.replace(temporary, output)
        return PdfBuildResult(output, page_count, byte_count)
    finally:
        temporary.unlink(missing_ok=True)


def _xml(value: object) -> str:
    return html.escape(str(value), quote=True)


def _is_cjk(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2FA1F
    )


def _markup(value: object) -> str:
    """Escape text and select the CJK fallback only for covered characters."""
    text = str(value)
    if not text:
        return ""
    pieces: list[str] = []
    start = 0
    cjk = _is_cjk(text[0])
    for index, character in enumerate(text[1:], start=1):
        character_is_cjk = _is_cjk(character)
        if character_is_cjk == cjk:
            continue
        chunk = _xml(text[start:index])
        pieces.append(f'<font name="STSong-Light">{chunk}</font>' if cjk else chunk)
        start = index
        cjk = character_is_cjk
    chunk = _xml(text[start:])
    pieces.append(f'<font name="STSong-Light">{chunk}</font>' if cjk else chunk)
    return "".join(pieces)


def _link(label: str, url: str) -> str:
    return f'<link href="{_xml(url)}" color="#1F4B66">{_markup(label)}</link>'


def _validate_portrait(portrait: Path) -> None:
    try:
        with Image.open(portrait) as image:
            image.load()
            if image.width <= 0 or image.height <= 0:
                raise OSError("invalid dimensions")
    except (OSError, ValueError):
        raise ValueError(f"Portrait {portrait} is not a valid image") from None


_SETEXT_HEADING = re.compile(r"^\s*=+\s*$")
_SETEXT_SUBHEADING = re.compile(r"^\s*-{3,}\s*$")
_ATX_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_BLOCKQUOTE = re.compile(r"^\s*>\s?(.*)$")
_UNORDERED_LIST = re.compile(r"^\s*[-+*]\s+(.*)$")
_ORDERED_LIST = re.compile(r"^\s*(\d+[.)])\s+(.*)$")


def _teaching_markup(body: str) -> str:
    """Convert the supported teaching Markdown blocks to editorial markup."""
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line.strip():
            index += 1
            continue
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if _SETEXT_HEADING.fullmatch(next_line):
            blocks.append(f"<b>{_markup(line.strip())}</b>")
            index += 2
            continue
        if _SETEXT_SUBHEADING.fullmatch(next_line):
            blocks.append(f"<b>{_markup(line.strip())}</b>")
            index += 2
            continue
        atx = _ATX_HEADING.fullmatch(line)
        if atx:
            blocks.append(f"<b>{_markup(atx.group(1))}</b>")
            index += 1
            continue
        blockquote = _BLOCKQUOTE.fullmatch(line)
        if blockquote:
            blocks.append(f"&bull; {_markup(blockquote.group(1))}")
            index += 1
            continue
        unordered = _UNORDERED_LIST.fullmatch(line)
        if unordered:
            blocks.append(f"&bull; {_markup(unordered.group(1))}")
            index += 1
            continue
        ordered = _ORDERED_LIST.fullmatch(line)
        if ordered:
            blocks.append(
                f"{_markup(ordered.group(1))} {_markup(ordered.group(2))}"
            )
            index += 1
            continue
        blocks.append(_markup(line.strip()))
        index += 1
    return "<br/>".join(blocks)


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
    manifest: str,
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
        subject=manifest,
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


@dataclass(frozen=True)
class _RailBlock:
    section: str
    markup: str
    style: ParagraphStyle
    space_before: float = 0


def _rail_blocks(
    document: CvDocument, styles: dict[str, ParagraphStyle]
) -> tuple[_RailBlock, ...]:
    blocks = [
        _RailBlock(
            "Identity",
            f'<font name="CvSans-Bold" size="11.5">{_markup(OWNER_NAME)}</font>',
            styles["rail"],
        )
    ]
    postnominals = ", ".join(document.author.postnominals)
    if postnominals:
        blocks.append(_RailBlock("Identity", _markup(postnominals), styles["rail"]))
    blocks.extend(
        (
            _RailBlock(
                "Appointment",
                f"<b>{_markup(document.author.role)}</b>",
                styles["rail"],
            ),
            _RailBlock(
                "Appointment",
                _link(document.author.affiliation, document.author.affiliation_url),
                styles["rail"],
            ),
        )
    )
    blocks.extend(
        _RailBlock("Profile links", _link(item.label, item.url), styles["rail"])
        for item in document.author.links
    )
    blocks.append(
        _RailBlock(
            "Research Interests",
            "Research Interests",
            styles["rail_heading"],
            2 * mm,
        )
    )
    interests = "<br/>".join(
        f"- {_markup(item)}" for item in document.author.interests
    )
    blocks.append(
        _RailBlock("Research Interests", interests, styles["rail"])
    )
    blocks.append(_RailBlock("Education", "Education", styles["rail_heading"]))
    blocks.extend(
        _RailBlock(
            "Education",
            f"<b>{_markup(item.degree)}</b><br/>"
            f"{_markup(item.institution)}, {_markup(item.year)}",
            styles["rail"],
        )
        for item in document.author.education
    )
    return tuple(blocks)


def _rail_layout(document: CvDocument) -> tuple[tuple[Paragraph, float], ...]:
    styles = _styles()
    inset = 7 * mm
    portrait_height = 49 * mm
    content_width = 52 * mm - 2 * inset
    y = A4[1] - inset - portrait_height - 6 * mm
    positioned = []
    for block in _rail_blocks(document, styles):
        y -= block.space_before
        paragraph = Paragraph(block.markup, block.style)
        _, height = paragraph.wrap(content_width, A4[1])
        draw_y = y - height
        end_y = draw_y - block.style.spaceAfter
        if end_y < RAIL_CONTENT_BOTTOM:
            raise ValueError(
                "CV first-page rail overflows in "
                f"{block.section}: content ends at {end_y / mm:.1f} mm, "
                f"minimum is {RAIL_CONTENT_BOTTOM / mm:.1f} mm"
            )
        positioned.append((paragraph, draw_y))
        y = end_y
    return tuple(positioned)


def _validate_rail_capacity(document: CvDocument) -> None:
    _rail_layout(document)


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
    for paragraph, draw_y in _rail_layout(document):
        paragraph.drawOn(canvas, inset, draw_y)
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
        heading = Paragraph(_markup(title), styles["heading"])
        if entries:
            story.append(KeepTogether([heading, entries[0]]))
            story.extend(entries[1:])
        else:
            story.append(heading)

    section(
        "Academic Profile",
        [Paragraph(_markup(document.author.profile), styles["body"])],
    )
    appointment = (
        f"<b>{_markup(document.author.role)}</b><br/>"
        f"{_link(document.author.affiliation, document.author.affiliation_url)}"
    )
    section(
        "Current Academic Appointment",
        [_EntryParagraph(appointment, styles["entry"])],
    )

    publication_entries = []
    for publication in document.publications:
        authors = ", ".join(
            f"<b>{_markup(OWNER_NAME)}</b>" if author == OWNER_ID else _markup(author)
            for author in publication.authors
        )
        citation_parts = [f"<i>{_markup(publication.venue)}</i>"]
        if publication.volume:
            citation_parts.append(_markup(publication.volume))
        if publication.issue:
            citation_parts.append(f"({_markup(publication.issue)})")
        if publication.pages:
            citation_parts.append(_markup(publication.pages))
        elif publication.article_number:
            citation_parts.append(_markup(publication.article_number))
        citation_parts.append(str(publication.published.year))
        links = []
        if publication.doi:
            links.append(_link(f"doi:{publication.doi}", f"https://doi.org/{publication.doi}"))
        if publication.source_url:
            links.append(_link("source", publication.source_url))
        link_line = f"<br/>{' · '.join(links)}" if links else ""
        publication_entries.append(
            _EntryParagraph(
                f"<b>{_markup(publication.title)}</b><br/>{authors}<br/>"
                f"{', '.join(citation_parts)}{link_line}",
                styles["entry"],
            )
        )
    section("Publications", publication_entries)

    talk_entries = []
    for talk in document.talks:
        venue_line = ", ".join(
            _markup(value) for value in (talk.venue, talk.location) if value
        )
        source = f"<br/>{_link('source', talk.source_url)}" if talk.source_url else ""
        talk_entries.append(
            _EntryParagraph(
                f"<b>{_markup(talk.title)}</b><br/>{_markup(talk.event)}<br/>"
                f"{venue_line}, {talk.date.strftime('%d %B %Y')}{source}",
                styles["entry"],
            )
        )
    section("Invited Talks & Presentations", talk_entries)

    teaching_entries = []
    for teaching in document.teaching:
        details = [teaching.teaching_type, teaching.venue, teaching.location]
        visible = [_markup(value) for value in details if value]
        body = _teaching_markup(teaching.body)
        body_line = f"<br/>{body}" if body else ""
        teaching_entries.append(
            _EntryParagraph(
                f"<b>{_markup(teaching.title)}</b><br/>{', '.join(visible)}{body_line}",
                styles["entry"],
            )
        )
    section("Teaching", teaching_entries)
    story.append(Spacer(1, 2 * mm))
    return story

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from scripts.publication_importer import (
    citation_record_from_frontmatter,
    iter_publication_indexes,
    read_frontmatter,
)


OWNER_ID = "me"
OWNER_NAME = "Sean Longyu Ma"
LEGACY_CV_PROVENANCE = "migrated_legacy"
MANDATORY_CV_TEXT = (
    OWNER_NAME,
    "Academic CV",
    "Academic Profile",
    "Current Academic Appointment",
    "Research Interests",
    "Education",
    "Publications",
    "Invited Talks & Presentations",
    "Teaching & Postgraduate Supervision",
)
CV_BASELINE_PUBLICATION_BUNDLES = frozenset(
    {
        "content/publications/2018-10-18-optimized-layer-architecture-for-layered-ldpc-code-decoder",
        "content/publications/2019-10-15-a-novel-data-packing-technique-for-qc-ldpc-decoder-architecture-appli",
        "content/publications/2019-11-19-a-real-time-flexible-telecommunication-decoding-architecture-using-fp",
        "content/publications/2019-12-09-soc-fpga-based-implementation-of-iris-recognition-enhanced-by-qc-ldpc",
        "content/publications/2020-03-10-iris-recognition-system-implementation-improved-by-qc-ldpc-codes",
        "content/publications/2020-10-03-a-novel-iris-verification-framework-using-machine-learning-algorithm-",
        "content/publications/2020-10-13-an-iris-recognition-system-implementation-with-error-correction-capab",
        "content/publications/2020-12-08-a-risc-v-soc-for-mobile-payment-based-on-visible-light-communication",
        "content/publications/2021-10-12-a-dynamically-reconfigurable-qc-ldpc-implementation-for-iris-recognit",
        "content/publications/2021-10-12-a-highly-integrated-risc-v-based-soc-for-on-board-unit-in-etc-system",
        "content/publications/2021-10-12-cnn-accelerator-with-non-blocking-network-design",
        "content/publications/2021-12-08-an-effective-multi-mode-iris-authentication-system-on-a-microprocesso",
        "content/publications/2022-10-18-implementation-for-jscc-scheme-based-on-qc-ldpc-codes",
        "content/publications/2024-01-30-joint-source-channel-coding-system-for-6g-communication-design-protot",
        "content/publications/2024-02-19-early-stopped-technique-for-bch-decoding-algorithm-under-tolerant-fau",
        "content/publications/2024-03-22-urban-aquatic-scene-expansion-for-semantic-segmentation-in-cityscapes",
        "content/publications/2024-04-22-pqde-comprehensive-progressive-quantization-with-discretization-error",
        "content/publications/2024-06-13-vit-lob-efficient-vision-transformer-for-stockprice-trend-prediction-",
        "content/publications/2024-10-29-a-framework-for-mapping-convolutional-neural-network-onto-memristor-c",
        "content/publications/2024-10-29-a-mobile-computing-friendly-stock-price-trend-prediction-model",
        "content/publications/2024-10-29-an-edge-ai-system-based-on-fpga-platform-for-railway-fault-detection",
        "content/publications/2024-10-29-mtst-a-multi-task-scheduling-transformer-accelerator-for-edge-computi",
        "content/publications/2025-02-12-kernelvm-teaching-linux-kernel-programming-through-a-browser-based-vi",
        "content/publications/2025-06-09-target-tracking-in-underwater-multi-sensor-systems-using-delayed-bear",
        "content/publications/2025-06-30-a-novel-computing-paradigm-for-mobilenetv3-using-memristor",
        "content/publications/2025-06-30-joint-post-training-pruning-and-power-of-two-quantization-for-efficie",
        "content/publications/2025-06-30-lha-layer-wise-hardware-acceleration-of-progressive-quantizing-infere",
        "content/publications/2025-07-17-lightfsa-a-lightweight-financial-sentiment-analysis-model",
        "content/publications/2025-09-23-enhancing-synthesis-efficiency-in-hls-through-llm-based-automated-cod",
        "content/publications/2025-09-23-fpga-based-real-time-image-tampering-detection-system-for-edge-comput",
        "content/publications/2025-11-01-visually-meaningful-asymmetric-image-encryption-based-on-a-random-dev",
        "content/publications/2025-12-15-a-review-of-fpga-driven-llm-acceleration",
        "content/publications/2025-12-15-adaptive-gradual-quantization-with-a-custom-risc-v-simd-accelerator",
    }
)
CV_BASELINE_INTERESTS = frozenset(
    {
        "FPGA acceleration",
        "RISC-V customisation",
        "High-level synthesis",
        "Heterogeneous computing",
    }
)
CV_BASELINE_EDUCATION = frozenset(
    {
        ("PhD in Computer Science", "The University of Auckland", 2023),
        ("Master of Integrated Circuit Engineering", "Shanghai Jiao Tong University", 2016),
        ("Bachelor of Communication Engineering", "Harbin Engineering University", 2010),
    }
)
CV_BASELINE_TALK_TITLES = frozenset(
    {
        "2026 IEEE International Symposium on Circuits and Systems",
        "Technical Talks of IEEE Consumer Technoligy Society - 19th Webinar",
        "IEEE CASS Workshop: Circuit-Level Intelligence: From Secure Silicon to AI-Ready Systems",
        "Interal Talk with staff in Computer Science, UoA",
        "Journey to the “South”: Advancing Computing from Traditional Architectures to Emerging Technologies",
        "Joint 6G-PHYSEC & INTERACT Workshop on 6G Technologies and PHY Layer Security",
        "WebVM - an innovative approach to teaching OS concepts",
    }
)
CV_BASELINE_TEACHING_TITLES = frozenset(
    {
        "UoA Postgraduate Supervision experience",
        "UoA Undergraduate Teaching experience",
    }
)


@dataclass(frozen=True)
class CvLink:
    label: str
    url: str


@dataclass(frozen=True)
class CvEducation:
    degree: str
    institution: str
    year: int


@dataclass(frozen=True)
class CvAuthor:
    display_name: str
    postnominals: tuple[str, ...]
    role: str
    profile: str
    affiliation: str
    affiliation_url: str
    links: tuple[CvLink, ...]
    interests: tuple[str, ...]
    education: tuple[CvEducation, ...]


@dataclass(frozen=True)
class CvPublication:
    bundle_path: str
    title: str
    authors: tuple[str, ...]
    published: datetime
    publication_type: str
    venue: str
    volume: str
    issue: str
    pages: str
    article_number: str
    publisher: str
    doi: str
    source_url: str


@dataclass(frozen=True)
class CvTalk:
    title: str
    event: str
    venue: str
    location: str
    date: datetime
    source_url: str


@dataclass(frozen=True)
class CvTeaching:
    title: str
    teaching_type: str
    venue: str
    location: str
    body: str


@dataclass(frozen=True)
class PublicationReview:
    bundle_path: str
    title: str
    date: str
    venue: str
    doi: str
    draft: bool
    requires_correction: bool
    source_url: str
    included: bool
    reason: str


@dataclass(frozen=True)
class CvDocument:
    author: CvAuthor
    publications: tuple[CvPublication, ...]
    talks: tuple[CvTalk, ...]
    teaching: tuple[CvTeaching, ...]
    publication_reviews: tuple[PublicationReview, ...]


def validate_cv_baseline(document: CvDocument) -> None:
    actual = {
        "publication": {item.bundle_path for item in document.publications},
        "interest": set(document.author.interests),
        "education": {
            (item.degree, item.institution, item.year)
            for item in document.author.education
        },
        "talk": {item.title for item in document.talks},
        "teaching": {item.title for item in document.teaching},
    }
    baseline = {
        "publication": CV_BASELINE_PUBLICATION_BUNDLES,
        "interest": CV_BASELINE_INTERESTS,
        "education": CV_BASELINE_EDUCATION,
        "talk": CV_BASELINE_TALK_TITLES,
        "teaching": CV_BASELINE_TEACHING_TITLES,
    }
    for category, required in baseline.items():
        missing = required - actual[category]
        if missing:
            formatted = ", ".join(repr(item) for item in sorted(missing))
            raise ValueError(
                f"CV baseline {category} identities are missing: {formatted}"
            )


def cv_content_counts(document: CvDocument) -> dict[str, int]:
    return {
        "publications": len(document.publications),
        "interests": len(document.author.interests),
        "education": len(document.author.education),
        "talks": len(document.talks),
        "teaching": len(document.teaching),
    }


def cv_content_manifest(counts: dict[str, int]) -> str:
    ordered = ("publications", "interests", "education", "talks", "teaching")
    return "Academic curriculum vitae | " + ";".join(
        f"{name}={counts[name]}" for name in ordered
    )


def load_frontmatter_page(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError(f"Invalid YAML front matter: {path}")
    metadata = yaml.safe_load(parts[1])
    if not isinstance(metadata, dict):
        raise ValueError(f"Front matter must be a mapping: {path}")
    body = parts[2]
    if body.startswith("\n"):
        body = body[1:]
    return metadata, body


def load_cv_document(root: Path) -> CvDocument:
    root = root.resolve()
    author = _load_author(root / "data/authors/me.yaml")
    publications, reviews = _load_publications(root)
    talks = _load_talks(root / "content/events", root)
    teaching = _load_teaching(root / "content/teaching", root)
    return CvDocument(author, publications, talks, teaching, reviews)


def write_publication_review(document: CvDocument, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "# Academic CV Publication Review",
        "",
        "| Title | Date | Venue | DOI | Draft | Correction | Source | CV |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for item in document.publication_reviews:
        source = _review_source_cell(item.source_url)
        decision = "Include" if item.included else f"Exclude: {item.reason}"
        rows.append(
            f"| {_review_cell(item.title)} | {_review_cell(item.date)} | "
            f"{_review_cell(item.venue)} | {_review_cell(item.doi)} | "
            f"{_review_cell(str(item.draft).lower())} | "
            f"{_review_cell(str(item.requires_correction).lower())} | {source} | "
            f"{_review_cell(decision)} |"
        )
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _review_cell(value: str, *, trusted_markdown: bool = False) -> str:
    normalised = value.replace("\r\n", "\n").replace("\r", "\n")
    escaped = normalised if trusted_markdown else html.escape(normalised, quote=True)
    escaped = escaped.replace("\\", "\\\\").replace("|", "\\|")
    if not trusted_markdown:
        for character in "`*_[]{}()!":
            escaped = escaped.replace(character, f"\\{character}")
    return escaped.replace("\n", "<br>")


def _review_source_cell(url: str) -> str:
    if not url:
        return ""
    encoded = quote(url, safe="/:?#@!$&+,;=%")
    return _review_cell(f"[source](<{encoded}>)", trusted_markdown=True)


def _field_error(path: Path, field: str, message: str) -> ValueError:
    return ValueError(f"{path}: {field} {message}")


def _required_string(value: Any, path: Path, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_error(path, field, "must be a non-empty string")
    return value.strip()


def _string_tuple(value: Any, path: Path, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise _field_error(path, field, "must be a list of non-empty strings")
    return tuple(item.strip() for item in value)


def _non_empty_string_tuple(value: Any, path: Path, field: str) -> tuple[str, ...]:
    items = _string_tuple(value, path, field)
    if not items:
        raise _field_error(path, field, "must be a non-empty list of strings")
    return items


def _load_author(path: Path) -> CvAuthor:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise _field_error(path, "author", "must be a mapping")

    name = loaded.get("name")
    if not isinstance(name, dict):
        raise _field_error(path, "name", "must be a mapping")
    display_name = _required_string(name.get("display"), path, "name.display")

    affiliations = loaded.get("affiliations")
    if not isinstance(affiliations, list) or not affiliations or not isinstance(
        affiliations[0], dict
    ):
        raise _field_error(path, "affiliations", "must be a non-empty list of mappings")
    affiliation = _required_string(
        affiliations[0].get("name"), path, "affiliations[0].name"
    )
    affiliation_url = _required_string(
        affiliations[0].get("url"), path, "affiliations[0].url"
    )

    raw_links = loaded.get("links")
    if not isinstance(raw_links, list) or not raw_links or any(
        not isinstance(item, dict) for item in raw_links
    ):
        raise _field_error(path, "links", "must be a non-empty list of mappings")
    links = tuple(
        CvLink(
            _required_string(item.get("label"), path, f"links[{index}].label"),
            _required_string(item.get("url"), path, f"links[{index}].url"),
        )
        for index, item in enumerate(raw_links)
    )

    interests = _non_empty_string_tuple(loaded.get("interests"), path, "interests")
    raw_education = loaded.get("education")
    if not isinstance(raw_education, list) or not raw_education or any(
        not isinstance(item, dict) for item in raw_education
    ):
        raise _field_error(
            path, "education", "must be a non-empty list of mappings"
        )
    education = []
    for index, item in enumerate(raw_education):
        end = item.get("end")
        try:
            if isinstance(end, datetime):
                year = end.year
            elif isinstance(end, date):
                year = end.year
            elif isinstance(end, str):
                year = date.fromisoformat(end).year
            else:
                raise TypeError
        except (TypeError, ValueError) as error:
            raise _field_error(
                path, f"education[{index}].end", "must be an ISO date"
            ) from error
        education.append(
            CvEducation(
                _required_string(
                    item.get("degree"), path, f"education[{index}].degree"
                ),
                _required_string(
                    item.get("institution"), path, f"education[{index}].institution"
                ),
                year,
            )
        )

    return CvAuthor(
        display_name=display_name,
        postnominals=_string_tuple(
            loaded.get("postnominals"), path, "postnominals"
        ),
        role=_required_string(loaded.get("role"), path, "role"),
        profile=_required_string(loaded.get("bio"), path, "bio"),
        affiliation=affiliation,
        affiliation_url=affiliation_url,
        links=links,
        interests=interests,
        education=tuple(education),
    )


def _parse_datetime(value: Any, path: Path, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise _field_error(path, field, "must be a complete parseable date") from error
    else:
        raise _field_error(path, field, "must be a complete parseable date")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_string(value: Any, path: Path, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise _field_error(path, field, "must be a string")
    return value.strip()


def _source_url(metadata: dict[str, Any], path: Path) -> str:
    links = metadata.get("links", [])
    if links is None:
        return ""
    if not isinstance(links, list):
        raise _field_error(path, "links", "must be a list")
    for index, link in enumerate(links):
        if not isinstance(link, dict):
            raise _field_error(path, f"links[{index}]", "must be a mapping")
        if link.get("type") == "source":
            return _optional_string(link.get("url"), path, f"links[{index}].url")
    return ""


def _publication_values(
    metadata: dict[str, Any], path: Path
) -> tuple[str, tuple[str, ...], datetime, str, dict[str, Any], str, str]:
    title = _required_string(metadata.get("title"), path, "title")
    authors = _non_empty_string_tuple(metadata.get("authors"), path, "authors")
    published = _parse_datetime(metadata.get("date"), path, "date")
    publication_types = metadata.get("publication_types")
    if not isinstance(publication_types, list) or len(publication_types) != 1:
        raise _field_error(
            path, "publication_types", "must contain exactly one non-empty string"
        )
    publication_type = _required_string(
        publication_types[0], path, "publication_types[0]"
    )
    publication = metadata.get("publication")
    if not isinstance(publication, dict):
        raise _field_error(path, "publication", "must be a mapping")
    venue = _required_string(publication.get("name"), path, "publication.name")
    try:
        doi_value = metadata.get("hugoblox", {}).get("ids", {}).get("doi", "")
    except AttributeError as error:
        raise _field_error(path, "hugoblox.ids.doi", "must be a string") from error
    doi = _optional_string(doi_value, path, "hugoblox.ids.doi")
    return title, authors, published, publication_type, publication, venue, doi


def _is_managed_publication(metadata: dict[str, Any], path: Path) -> bool:
    has_legacy_marker = "cv_provenance" in metadata
    has_importer_marker = "publication_importer" in metadata
    if has_legacy_marker:
        provenance = metadata["cv_provenance"]
        if provenance != LEGACY_CV_PROVENANCE:
            raise _field_error(
                path,
                "cv_provenance",
                f"must equal {LEGACY_CV_PROVENANCE!r}",
            )
        if has_importer_marker:
            raise _field_error(
                path,
                "cv_provenance",
                "cannot be combined with publication_importer",
            )
        return False

    if not has_importer_marker:
        raise _field_error(
            path,
            "provenance",
            "must declare cv_provenance or publication_importer",
        )
    marker = metadata["publication_importer"]
    if not isinstance(marker, dict) or set(marker) != {"managed_citation"}:
        raise _field_error(
            path,
            "publication_importer",
            "must be a mapping containing only managed_citation: true",
        )
    if marker["managed_citation"] is not True:
        raise _field_error(
            path,
            "publication_importer.managed_citation",
            "must be the boolean true",
        )
    return True


def _load_publications(
    root: Path,
) -> tuple[tuple[CvPublication, ...], tuple[PublicationReview, ...]]:
    publications: list[CvPublication] = []
    reviews: list[PublicationReview] = []
    seen_dois: dict[str, Path] = {}

    for bundle, index in iter_publication_indexes(root):
        metadata, _ = read_frontmatter(index)
        bundle_path = bundle.relative_to(root).as_posix()
        managed = _is_managed_publication(metadata, index)
        raw_draft = metadata.get("draft")
        raw_requires_correction = metadata.get("requires_correction")
        draft = raw_draft is True
        requires_correction = raw_requires_correction is True
        reason = ""
        if managed and draft:
            reason = "managed publication is draft"
        elif managed and raw_draft is not False:
            reason = "managed publication draft status is not final"
        elif managed and requires_correction:
            reason = "managed publication requires correction"
        elif managed and raw_requires_correction is not False:
            reason = "managed publication correction status is not final"
        elif managed:
            try:
                citation_record, correction_reasons = (
                    citation_record_from_frontmatter(metadata)
                )
            except Exception as error:
                citation_record = None
                correction_reasons = [
                    f"managed publication metadata is invalid: {type(error).__name__}"
                ]
            if citation_record is None or correction_reasons:
                reason = "; ".join(correction_reasons) or "managed publication is invalid"

        title_value = metadata.get("title", "")
        title = title_value.strip() if isinstance(title_value, str) else ""
        date_value = metadata.get("date", "")
        review_date = date_value.isoformat() if isinstance(date_value, (date, datetime)) else str(date_value)
        publication_value = metadata.get("publication", {})
        venue_value = publication_value.get("name", "") if isinstance(publication_value, dict) else ""
        venue = venue_value.strip() if isinstance(venue_value, str) else ""
        try:
            doi_value = metadata.get("hugoblox", {}).get("ids", {}).get("doi", "")
        except AttributeError:
            doi_value = ""
        doi = doi_value.strip() if isinstance(doi_value, str) else ""
        source_url = _source_url(metadata, index)

        included = not reason
        if included:
            (
                title,
                authors,
                published,
                publication_type,
                publication,
                venue,
                doi,
            ) = _publication_values(metadata, index)
            normalised_doi = doi.casefold()
            if normalised_doi:
                if normalised_doi in seen_dois:
                    raise ValueError(
                        "Duplicate eligible publication DOI "
                        f"{doi}: {seen_dois[normalised_doi]} and {index}"
                    )
                seen_dois[normalised_doi] = index
            publications.append(
                CvPublication(
                    bundle_path=bundle_path,
                    title=title,
                    authors=authors,
                    published=published,
                    publication_type=publication_type,
                    venue=venue,
                    volume=_optional_string(publication.get("volume"), index, "publication.volume"),
                    issue=_optional_string(publication.get("issue"), index, "publication.issue"),
                    pages=_optional_string(publication.get("pages"), index, "publication.pages"),
                    article_number=_optional_string(
                        publication.get("article_number"), index, "publication.article_number"
                    ),
                    publisher=_optional_string(
                        publication.get("publisher"), index, "publication.publisher"
                    ),
                    doi=doi,
                    source_url=source_url,
                )
            )

        reviews.append(
            PublicationReview(
                bundle_path=bundle_path,
                title=title,
                date=review_date,
                venue=venue,
                doi=doi,
                draft=draft,
                requires_correction=requires_correction,
                source_url=source_url,
                included=included,
                reason=reason,
            )
        )

    publications.sort(key=lambda item: (item.published, item.title.casefold()), reverse=True)
    return tuple(publications), tuple(reviews)


def _content_pages(directory: Path, root: Path) -> tuple[Path, ...]:
    root = root.resolve()
    content_directory = root / "content"
    if (
        content_directory.is_symlink()
        or content_directory.is_junction()
        or content_directory.resolve() != content_directory
    ):
        raise ValueError(
            f"{content_directory}: content directory must resolve inside repository "
            "without links"
        )
    if directory.is_symlink() or directory.is_junction():
        raise ValueError(
            f"{directory}: content directory must resolve inside repository "
            "content without links"
        )
    if not directory.exists():
        raise ValueError(f"{directory}: required content directory is missing")
    if not directory.is_dir():
        raise ValueError(f"{directory}: required content directory is not a directory")
    resolved_directory = directory.resolve()
    if resolved_directory != directory or resolved_directory.parent != content_directory:
        raise ValueError(
            f"{directory}: content directory must resolve inside repository "
            "content without links"
        )
    pages: list[Path] = []
    for candidate in sorted(directory.glob("*.md")):
        if candidate.name == "_index.md":
            continue
        if candidate.is_symlink() or candidate.is_junction():
            raise ValueError(
                f"Content page must resolve inside repository content without links: "
                f"{candidate}"
            )
        resolved = candidate.resolve()
        if resolved != candidate:
            raise ValueError(
                f"Content page must resolve inside repository content without links: "
                f"{candidate}"
            )
        try:
            resolved.relative_to(resolved_directory)
        except ValueError as error:
            raise ValueError(f"Content page must resolve inside {directory}: {candidate}") from error
        if resolved.parent != resolved_directory:
            raise ValueError(f"Content page must remain directly inside {directory}: {candidate}")
        pages.append(resolved)
    return tuple(pages)


def _load_talks(directory: Path, root: Path) -> tuple[CvTalk, ...]:
    talks = []
    for path in _content_pages(directory, root):
        metadata, _ = load_frontmatter_page(path)
        event_value = metadata.get("event")
        if not isinstance(event_value, str) or not event_value.strip():
            event_value = metadata.get("event_name")
        talks.append(
            CvTalk(
                title=_required_string(metadata.get("title"), path, "title"),
                event=_required_string(event_value, path, "event"),
                venue=_optional_string(metadata.get("venue"), path, "venue"),
                location=_optional_string(metadata.get("location"), path, "location"),
                date=_parse_datetime(metadata.get("date"), path, "date"),
                source_url=_source_url(metadata, path),
            )
        )
    talks.sort(key=lambda item: (item.date, item.title.casefold()), reverse=True)
    if not talks:
        raise ValueError(f"{directory}: must contain at least one talk record")
    return tuple(talks)


def _load_teaching(directory: Path, root: Path) -> tuple[CvTeaching, ...]:
    teaching = []
    for path in _content_pages(directory, root):
        metadata, body = load_frontmatter_page(path)
        teaching.append(
            CvTeaching(
                title=_required_string(metadata.get("title"), path, "title"),
                teaching_type=_required_string(
                    metadata.get("teaching_type"), path, "teaching_type"
                ),
                venue=_optional_string(metadata.get("venue"), path, "venue"),
                location=_optional_string(metadata.get("location"), path, "location"),
                body=body,
            )
        )
    teaching.sort(key=lambda item: item.title.casefold())
    if not teaching:
        raise ValueError(f"{directory}: must contain at least one teaching record")
    return tuple(teaching)

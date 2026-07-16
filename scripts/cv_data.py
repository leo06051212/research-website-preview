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
INITIAL_CV_CONTENT_COUNTS = {
    "publications": 33,
    "interests": 4,
    "education": 3,
    "talks": 7,
    "teaching": 2,
}


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

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from datetime import date as calendar_date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

import yaml

DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
IEEE_PATH_RE = re.compile(r"^/document/(\d+)/?$", re.IGNORECASE)
PUBLICATION_TYPES = {
    "article-journal",
    "paper-conference",
    "chapter",
    "report",
    "manuscript",
}
REQUEST_STATUSES = {"pending", "processed", "duplicate", "failed"}


@dataclass(frozen=True)
class Identifier:
    kind: str
    value: str


@dataclass(frozen=True)
class ProcessResult:
    status: str
    result_path: str = ""
    error: str = ""


def normalize_source(source: str) -> Identifier:
    cleaned = source.strip()
    parsed = urlsplit(cleaned)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Enter a valid DOI or IEEE Xplore URL")
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in {"doi.org", "dx.doi.org"}:
            doi = unquote(parsed.path.lstrip("/"))
            if DOI_RE.fullmatch(doi):
                return Identifier("doi", doi.lower())
        elif hostname == "ieeexplore.ieee.org":
            ieee = IEEE_PATH_RE.fullmatch(parsed.path)
            if ieee:
                return Identifier("ieee", ieee.group(1))
        raise ValueError("Enter a valid DOI or IEEE Xplore URL")
    doi = unquote(cleaned)
    if DOI_RE.fullmatch(doi):
        return Identifier("doi", doi.lower())
    raise ValueError("Enter a valid DOI or IEEE Xplore URL")


def fetch_json_url(url: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for delay in [0, 1, 2]:
        if delay:
            time.sleep(delay)
        request = Request(
            url,
            headers={"User-Agent": "SeanMaAcademicSite/1.0 (mailto:sean.ma@auckland.ac.nz)"},
        )
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except (URLError, TimeoutError) as error:
            last_error = error
    raise RuntimeError(f"Metadata request failed after 3 attempts: {last_error}") from last_error


def resolve_ieee(
    identifier: Identifier, fetch_json: Callable[[str], dict[str, Any]]
) -> Identifier:
    if identifier.kind == "doi":
        return identifier
    api_key = os.environ.get("IEEE_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "This IEEE URL has no DOI in the URL; configure IEEE_API_KEY or enter the DOI"
        )
    url = (
        "https://ieeexploreapi.ieee.org/api/v1/search/articles"
        f"?article_number={quote(identifier.value)}&apikey={quote(api_key)}"
    )
    try:
        response = fetch_json(url)
    except Exception as error:
        raise RuntimeError("IEEE metadata request failed") from error
    articles = response.get("articles", [])
    doi = articles[0].get("doi", "") if articles else ""
    if not doi:
        raise ValueError("IEEE returned no DOI for this document number")
    return normalize_source(doi)


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")[:90]


def validate_request(request: dict[str, Any]) -> None:
    source = request.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    status = request.get("status", "pending")
    if not isinstance(status, str) or status not in REQUEST_STATUSES:
        raise ValueError("status must be one of: pending, processed, duplicate, failed")
    publication_type = request.get("publication_type", "article-journal")
    if not isinstance(publication_type, str) or publication_type not in PUBLICATION_TYPES:
        raise ValueError(
            "publication_type must be one of: " + ", ".join(sorted(PUBLICATION_TYPES))
        )
    if "featured" in request and type(request["featured"]) is not bool:
        raise ValueError("featured must be a boolean")
    for field in ("pdf_url", "code_url", "dataset_url", "slides_url"):
        if field in request and not isinstance(request[field], str):
            raise ValueError(f"{field} must be a string")


def crossref_date_parts(message: dict[str, Any]) -> list[int]:
    date_block = (
        message.get("published-print")
        or message.get("published-online")
        or message.get("issued")
    )
    if date_block is None:
        return []
    if not isinstance(date_block, dict):
        raise ValueError("Crossref publication date must be an object")
    groups = date_block.get("date-parts")
    if not isinstance(groups, list) or not groups or not isinstance(groups[0], list):
        raise ValueError("Crossref publication date-parts must contain a list")
    parts = groups[0]
    if not 1 <= len(parts) <= 3 or any(type(part) is not int for part in parts):
        raise ValueError("Crossref publication date must contain one to three integers")
    try:
        calendar_date(
            parts[0],
            parts[1] if len(parts) > 1 else 1,
            parts[2] if len(parts) > 2 else 1,
        )
    except ValueError as error:
        raise ValueError(f"Invalid Crossref publication date: {error}") from error
    return parts


def crossref_scalar(message: dict[str, Any], field: str) -> str:
    value = message.get(field, "")
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"Crossref {field} must be a scalar")
    return str(value)


def record_from_crossref(
    message: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(message, dict):
        raise ValueError("Crossref message must be a mapping")
    doi_value = message.get("DOI")
    if not isinstance(doi_value, str):
        raise ValueError("Crossref DOI must be a string")
    doi = normalize_source(doi_value).value
    title_values = message.get("title", [])
    if not isinstance(title_values, list) or any(
        not isinstance(value, str) for value in title_values
    ):
        raise ValueError("Crossref title must be a list of strings")
    title = title_values[0].strip() if title_values else ""
    author_values = message.get("author", [])
    if not isinstance(author_values, list):
        raise ValueError("Crossref author must be a list")
    authors = []
    for author in author_values:
        if not isinstance(author, dict):
            raise ValueError("Each Crossref author must be an object")
        if any(
            key in author and not isinstance(author[key], str)
            for key in ("given", "family")
        ):
            raise ValueError("Crossref author names must be strings")
        name = " ".join(
            part
            for part in [author.get("given", ""), author.get("family", "")]
            if part
        ).strip()
        if name:
            authors.append("me" if name.casefold() == "sean longyu ma" else name)
    date_parts = crossref_date_parts(message)
    correction_reasons = []
    if not title:
        correction_reasons.append("Crossref metadata is missing the publication title")
    if not authors:
        correction_reasons.append("Crossref metadata is missing usable authors")
    if not date_parts:
        correction_reasons.append("Crossref metadata is missing the publication date")
        date_precision = "missing"
    elif len(date_parts) == 1:
        correction_reasons.append("Crossref supplied only a publication year")
        date_precision = "year"
    elif len(date_parts) == 2:
        correction_reasons.append("Crossref supplied only a publication year and month")
        date_precision = "month"
    else:
        date_precision = "day"
    links = []
    for kind in ["pdf", "code", "dataset", "slides"]:
        value = str(request.get(f"{kind}_url", "")).strip()
        if value:
            links.append({"type": kind, "url": value})
    source_value = message.get("URL", "")
    if source_value is None:
        source_value = ""
    if not isinstance(source_value, str):
        raise ValueError("Crossref URL must be a string")
    source_url = source_value.strip()
    if source_url:
        links.append({"type": "source", "url": source_url})
    container_titles = message.get("container-title", [])
    if not isinstance(container_titles, list) or any(
        not isinstance(value, str) for value in container_titles
    ):
        raise ValueError("Crossref container-title must be a list of strings")
    abstract = message.get("abstract", "")
    if abstract is None:
        abstract = ""
    if not isinstance(abstract, str):
        raise ValueError("Crossref abstract must be a string")
    record = {
        "publication_types": [request.get("publication_type", "article-journal")],
        "publication": {
            "name": container_titles[0] if container_titles else "",
            "volume": crossref_scalar(message, "volume"),
            "issue": crossref_scalar(message, "issue"),
            "pages": crossref_scalar(message, "page"),
            "article_number": crossref_scalar(message, "article-number"),
            "publisher": crossref_scalar(message, "publisher"),
        },
        "abstract": re.sub(r"<[^>]+>", "", abstract).strip(),
        "summary": "",
        "featured": request.get("featured", False),
        "draft": True,
        "requires_correction": bool(correction_reasons),
        "correction_reasons": correction_reasons,
        "date_precision": date_precision,
        "publication_date_parts": date_parts,
        "hugoblox": {"ids": {"doi": doi}},
        "links": links,
        "projects": [],
        "slides": "",
    }
    if title:
        record["title"] = title
    if authors:
        record["authors"] = authors
    if len(date_parts) == 3:
        record["date"] = (
            f"{date_parts[0]:04d}-{date_parts[1]:02d}-{date_parts[2]:02d}T00:00:00Z"
        )
    return record


def duplicate_path(root: Path, doi: str) -> Path | None:
    normalised = doi.lower()
    for index in (root / "content/publications").glob("*/index.md"):
        text = index.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
            existing_doi = frontmatter.get("hugoblox", {}).get("ids", {}).get("doi", "")
            existing_normalised = normalize_source(str(existing_doi)).value
        except (AttributeError, TypeError, ValueError, yaml.YAMLError):
            continue
        if normalised == existing_normalised:
            return index.parent
    return None


def bibtex_escape(value: Any) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "%": r"\%",
        "&": r"\&",
        "_": r"\_",
        "#": r"\#",
        "$": r"\$",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in str(value))


def render_bibtex(record: dict[str, Any]) -> str:
    doi = record["hugoblox"]["ids"]["doi"]
    date_parts = record.get("publication_date_parts", [])
    year = str(date_parts[0]) if date_parts else ""
    authors = record.get("authors", [])
    title = record.get("title", "")
    first_author = authors[0].split()[-1] if authors else "import"
    key = (
        f"{slugify(first_author)}{year}"
        f"{slugify(title).split('-')[0] if title else 'record'}"
    )
    venue = record["publication"]["name"]
    publication_type = record["publication_types"][0]
    entry_type, venue_field = {
        "article-journal": ("article", "journal"),
        "paper-conference": ("inproceedings", "booktitle"),
        "chapter": ("incollection", "booktitle"),
        "report": ("techreport", "institution"),
        "manuscript": ("unpublished", "note"),
    }[publication_type]
    publication = record["publication"]
    fields = {
        "title": title,
        "author": " and ".join(
            "Sean Longyu Ma" if name == "me" else name for name in authors
        ),
        venue_field: venue,
        "year": year,
        "volume": publication.get("volume", ""),
        "number": publication.get("issue", ""),
        "pages": publication.get("pages", ""),
        "eid": publication.get("article_number", ""),
        "publisher": publication.get("publisher", ""),
        "doi": doi,
        "url": f"https://doi.org/{doi}",
    }
    lines = [f"@{entry_type}{{{key},"]
    lines.extend(
        f"  {name} = {{{bibtex_escape(value)}}},"
        for name, value in fields.items()
        if value
    )
    lines.append("}")
    return "\n".join(lines) + "\n"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=path.parent
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def save_request(path: Path, request: dict[str, Any]) -> None:
    atomic_write(path, yaml.safe_dump(request, sort_keys=False, allow_unicode=True))


def validate_request_path(path: Path, root: Path) -> Path:
    if ".." in path.parts:
        raise ValueError("Publication import request path must not contain parent traversal")
    resolved_root = root.resolve()
    import_directory = (resolved_root / "data/publication-imports").resolve()
    resolved_path = path.resolve(strict=True)
    if resolved_path.suffix != ".yml" or resolved_path.parent != import_directory:
        raise ValueError(
            "Publication import request must be a .yml file directly under "
            "data/publication-imports"
        )
    return resolved_path


def process_request(
    path: Path,
    root: Path,
    fetch_json: Callable[[str], dict[str, Any]] = fetch_json_url,
) -> ProcessResult:
    path = validate_request_path(path, root)
    loaded_request = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded_request, dict):
        raise ValueError("Publication import request must be a YAML mapping")
    request = loaded_request
    created_bundle: Path | None = None
    try:
        validate_request(request)
        current_status = str(request.get("status", "pending"))
        if current_status != "pending":
            return ProcessResult(
                current_status,
                str(request.get("result_path", "")),
                str(request.get("error", "")),
            )
        identifier = resolve_ieee(
            normalize_source(str(request.get("source", ""))), fetch_json
        )
        existing = duplicate_path(root, identifier.value)
        if existing:
            relative_existing = str(existing.relative_to(root)).replace("\\", "/")
            request.update(
                status="duplicate",
                result_path=relative_existing,
                error="DOI already exists",
            )
            save_request(path, request)
            return ProcessResult(
                "duplicate", relative_existing, "DOI already exists"
            )
        url = f"https://api.crossref.org/works/{quote(identifier.value, safe='')}"
        response = fetch_json(url)
        if not isinstance(response, dict):
            raise ValueError("Crossref response must be a mapping")
        message = response.get("message", response)
        if not isinstance(message, dict):
            raise ValueError("Crossref message must be a mapping")
        returned_value = message.get("DOI", "")
        if not isinstance(returned_value, str):
            raise ValueError("Crossref DOI must be a string")
        returned_doi = returned_value.strip()
        if not returned_doi:
            raise ValueError("Crossref metadata is missing DOI")
        if normalize_source(returned_doi).value != identifier.value:
            raise ValueError("Crossref DOI does not match requested DOI")
        record = record_from_crossref(message, request)
        parts = record.get("publication_date_parts", [])
        slug_year = str(parts[0]) if parts else "undated"
        slug_identity = record.get("title") or identifier.value
        slug = slugify(f"{slug_year}-{slug_identity}")
        bundle = root / "content/publications" / slug
        if bundle.exists():
            raise FileExistsError(f"Publication bundle already exists: {bundle.name}")
        frontmatter = yaml.safe_dump(record, sort_keys=False, allow_unicode=True).strip()
        citation = render_bibtex(record)
        bundle.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{slug}-", dir=bundle.parent))
        try:
            atomic_write(staging / "index.md", f"---\n{frontmatter}\n---\n")
            atomic_write(staging / "cite.bib", citation)
            staging.replace(bundle)
            created_bundle = bundle
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        relative = str(bundle.relative_to(root)).replace("\\", "/")
        request.update(
            status="processed",
            result_path=relative,
            error="",
            processed_at=datetime.now(timezone.utc).isoformat(),
        )
        save_request(path, request)
        return ProcessResult("processed", relative)
    except Exception as error:
        if created_bundle is not None and created_bundle.exists():
            shutil.rmtree(created_bundle)
        request.update(status="failed", result_path="", error=str(error))
        save_request(path, request)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all-pending", action="store_true")
    mode.add_argument("request", nargs="?", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    paths = (
        sorted((root / "data/publication-imports").glob("*.yml"))
        if args.all_pending
        else [args.request]
    )
    failures = 0
    for path in paths:
        try:
            process_request(path, root)
        except Exception as error:
            failures += 1
            print(f"{path.name}: {error}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

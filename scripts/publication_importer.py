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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

import yaml

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
IEEE_RE = re.compile(r"ieeexplore\.ieee\.org/(?:document/)?(\d+)", re.IGNORECASE)


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
    cleaned = unquote(source.strip())
    doi = DOI_RE.search(cleaned)
    if doi:
        return Identifier("doi", doi.group(0).rstrip(".,;)}]").lower())
    ieee = IEEE_RE.search(cleaned)
    if ieee:
        return Identifier("ieee", ieee.group(1))
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


def record_from_crossref(
    message: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    title = (message.get("title") or [""])[0].strip()
    authors = []
    for author in message.get("author", []):
        name = " ".join(
            part
            for part in [author.get("given", ""), author.get("family", "")]
            if part
        ).strip()
        if name:
            authors.append("me" if name.casefold() == "sean longyu ma" else name)
    date_parts = (
        message.get("published-print")
        or message.get("published-online")
        or message.get("issued")
        or {}
    ).get("date-parts", [[]])[0]
    if not title or not authors or not date_parts:
        raise ValueError("Crossref metadata is missing title, authors, or publication date")
    year = int(date_parts[0])
    month = int(date_parts[1]) if len(date_parts) > 1 else 1
    day = int(date_parts[2]) if len(date_parts) > 2 else 1
    links = []
    for kind in ["pdf", "code", "dataset", "slides"]:
        value = str(request.get(f"{kind}_url", "")).strip()
        if value:
            links.append({"type": kind, "url": value})
    source_url = str(message.get("URL", "")).strip()
    if source_url:
        links.append({"type": "source", "url": source_url})
    return {
        "title": title,
        "authors": authors,
        "date": f"{year:04d}-{month:02d}-{day:02d}T00:00:00Z",
        "publication_types": [request.get("publication_type", "article-journal")],
        "publication": {
            "name": (message.get("container-title") or [""])[0],
            "volume": str(message.get("volume", "")),
            "issue": str(message.get("issue", "")),
            "pages": str(message.get("page", "")),
        },
        "abstract": re.sub(r"<[^>]+>", "", str(message.get("abstract", ""))).strip(),
        "summary": "",
        "featured": bool(request.get("featured", False)),
        "draft": True,
        "hugoblox": {"ids": {"doi": str(message["DOI"]).lower()}},
        "links": links,
        "projects": [],
        "slides": "",
    }


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


def render_bibtex(record: dict[str, Any]) -> str:
    doi = record["hugoblox"]["ids"]["doi"]
    year = record["date"][:4]
    key = (
        f"{slugify(record['authors'][0].split()[-1])}{year}"
        f"{slugify(record['title']).split('-')[0]}"
    )
    venue = record["publication"]["name"]
    entry_type = (
        "inproceedings"
        if record["publication_types"][0] == "paper-conference"
        else "article"
    )
    fields = {
        "title": record["title"],
        "author": " and ".join(
            "Sean Longyu Ma" if name == "me" else name for name in record["authors"]
        ),
        "booktitle" if entry_type == "inproceedings" else "journal": venue,
        "year": year,
        "doi": doi,
        "url": f"https://doi.org/{doi}",
    }
    lines = [f"@{entry_type}{{{key},"]
    lines.extend(f"  {name} = {{{value}}}," for name, value in fields.items() if value)
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


def process_request(
    path: Path,
    root: Path,
    fetch_json: Callable[[str], dict[str, Any]] = fetch_json_url,
) -> ProcessResult:
    request = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    current_status = str(request.get("status", "pending"))
    if current_status != "pending":
        return ProcessResult(
            current_status,
            str(request.get("result_path", "")),
            str(request.get("error", "")),
        )
    try:
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
        message = response.get("message", response)
        returned_doi = str(message.get("DOI", "")).strip()
        if not returned_doi:
            raise ValueError("Crossref metadata is missing DOI")
        if normalize_source(returned_doi).value != identifier.value:
            raise ValueError("Crossref DOI does not match requested DOI")
        record = record_from_crossref(message, request)
        slug = slugify(f"{record['date'][:4]}-{record['title']}")
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
        request.update(status="failed", result_path="", error=str(error))
        save_request(path, request)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--all-pending", action="store_true")
    parser.add_argument("request", nargs="?", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    paths = (
        sorted((root / "data/publication-imports").glob("*.yml"))
        if args.all_pending
        else [args.request.resolve()]
    )
    failures = 0
    for path in paths:
        request = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if request.get("status", "pending") != "pending":
            continue
        try:
            process_request(path, root)
        except Exception as error:
            failures += 1
            print(f"{path.name}: {error}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

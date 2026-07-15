from __future__ import annotations

import argparse
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any

import yaml

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
BIB_RE = re.compile(r"(?:```(?:bibtex)?\s*)?(@[A-Za-z]+\s*\{.*\})\s*(?:```)?\s*$", re.IGNORECASE | re.DOTALL)
AUTHOR_RE = re.compile(r'\bauthor\s*=\s*(?:\{([^}]+)\}|"([^"]+)")', re.IGNORECASE | re.DOTALL)
SINGLE_QUOTED_SCALAR_RE = re.compile(r"^(\s*[^:#]+:\s*)'(.*)'(\s*(?:#.*)?)$")


def repair_single_quoted_scalars(frontmatter: str) -> str:
    repaired = []
    for line in frontmatter.splitlines():
        match = SINGLE_QUOTED_SCALAR_RE.match(line)
        if match:
            value = re.sub(r"(?<!')'(?!')", "''", match.group(2))
            line = f"{match.group(1)}'{value}'{match.group(3)}"
        repaired.append(line)
    return "\n".join(repaired)


def read_legacy(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8-sig")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"Missing YAML front matter: {path}")
    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        metadata = yaml.safe_load(repair_single_quoted_scalars(parts[1])) or {}
    return metadata, parts[2].strip()


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug[:80] or "untitled"


def extract_bibtex(body: str) -> tuple[str, str]:
    match = BIB_RE.search(body)
    if not match:
        return body.strip(), ""
    clean_body = body[: match.start()].replace("Recommended citation:", "").strip()
    bibtex = "\n".join(line.rstrip() for line in match.group(1).strip().splitlines()) + "\n"
    return clean_body, bibtex


def extract_doi(metadata: dict[str, Any], body: str) -> str:
    joined = " ".join([str(metadata.get("paperurl", "")), str(metadata.get("citation", "")), body])
    match = DOI_RE.search(joined)
    return match.group(0).rstrip(".,;)}]") if match else ""


def extract_authors(bibtex: str) -> list[str]:
    match = AUTHOR_RE.search(bibtex)
    if not match:
        return ["me"]
    authors = []
    author_field = match.group(1) or match.group(2)
    for raw_name in re.split(r"\s+and\s+", author_field, flags=re.IGNORECASE):
        name = raw_name.strip()
        if name.casefold() in {
            "ma, sean longyu",
            "sean longyu ma",
            "ma, longyu",
            "longyu ma",
            "ma, sean",
            "sean ma",
        }:
            authors.append("me")
        elif "," in name:
            family, given = [part.strip() for part in name.split(",", 1)]
            authors.append(f"{given} {family}".strip())
        else:
            authors.append(name)
    return authors or ["me"]


def extract_citation_authors(citation: str, title: str) -> list[str]:
    names_text, separator, _ = citation.partition(title)
    if not separator:
        return ["me"]
    authors = []
    for raw_name in names_text.rstrip(". ").split(","):
        name = raw_name.strip()
        if not name:
            continue
        if name.casefold() in {"ma l", "ma s.l.", "ma sl"}:
            authors.append("me")
            continue
        parts = name.split(maxsplit=1)
        authors.append(f"{parts[1]} {parts[0]}" if len(parts) == 2 else name)
    return authors or ["me"]


def publication_type(venue: str) -> str:
    lowered = venue.lower()
    if any(word in lowered for word in ["conference", "symposium", "workshop", "proceedings", "congress", "mcsoc"]):
        return "paper-conference"
    return "article-journal"


def write_frontmatter(path: Path, payload: dict[str, Any], body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).strip()
    content = f"---\n{rendered}\n---\n"
    if body.strip():
        content += f"\n{body.strip()}\n"
    path.write_text(content, encoding="utf-8", newline="\n")


def migrate_publication(source: Path, output_root: Path) -> Path:
    metadata, body = read_legacy(source)
    abstract, bibtex = extract_bibtex(body)
    doi = extract_doi(metadata, body)
    slug = slugify(f"{metadata.get('date', '')}-{metadata['title']}")
    bundle = output_root / slug
    links = []
    if metadata.get("paperurl"):
        links.append({"type": "source", "url": str(metadata["paperurl"])})
    citation = str(metadata.get("citation", ""))
    authors = extract_authors(bibtex) if bibtex else extract_citation_authors(citation, str(metadata["title"]))
    payload = {
        "title": metadata["title"],
        "authors": authors,
        "date": f"{metadata['date']}T00:00:00Z",
        "publication_types": [publication_type(str(metadata.get("venue", "")))],
        "publication": {"name": str(metadata.get("venue", ""))},
        "abstract": abstract,
        "summary": str(metadata.get("excerpt", "")),
        "featured": False,
        "draft": True,
        "hugoblox": {"ids": {"doi": doi}} if doi else {"ids": {}},
        "links": links,
        "projects": [],
        "slides": "",
    }
    if citation:
        payload["citation"] = citation
    write_frontmatter(bundle / "index.md", payload)
    if bibtex:
        (bundle / "cite.bib").write_text(bibtex, encoding="utf-8", newline="\n")
    return bundle


def migrate_talk(source: Path, output_root: Path) -> Path:
    metadata, body = read_legacy(source)
    destination = output_root / f"{source.stem}.md"
    payload = {
        "title": metadata["title"],
        "date": f"{metadata['date']}T00:00:00Z",
        "event_name": metadata["title"],
        "location": str(metadata.get("location", metadata.get("venue", ""))),
        "summary": body.splitlines()[0] if body else "",
        "abstract": body,
        "event_start": f"{metadata['date']}T00:00:00Z",
        "event_all_day": True,
        "authors": ["me"],
        "tags": [str(metadata.get("type", "Talk"))],
        "featured": False,
        "projects": [],
    }
    write_frontmatter(destination, payload)
    return destination


def migrate_generic(source: Path, output_root: Path, kind: str) -> Path:
    metadata, body = read_legacy(source)
    destination = output_root / f"{source.stem}.md"
    payload = {
        "title": metadata["title"],
        "date": str(metadata.get("date", "2026-01-01")),
        "summary": str(metadata.get("excerpt", "")),
        "authors": ["me"],
        "tags": metadata.get("tags", [kind]),
        "draft": True,
    }
    write_frontmatter(destination, payload, body)
    return destination


def migrate_site(legacy_root: Path, target_root: Path) -> None:
    mappings = [
        ("_publications", "content/publications", migrate_publication),
        ("_talks", "content/events", migrate_talk),
        ("_posts", "content/blog", lambda src, dst: migrate_generic(src, dst, "Blog")),
        ("_teaching", "content/teaching", lambda src, dst: migrate_generic(src, dst, "Teaching")),
    ]
    for source_dir, target_dir, converter in mappings:
        for source in sorted((legacy_root / source_dir).glob("*.md")):
            converter(source, target_root / target_dir)
    source_images = legacy_root / "images"
    if source_images.is_dir():
        shutil.copytree(source_images, target_root / "static/images", dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy_root", type=Path)
    parser.add_argument("target_root", type=Path)
    args = parser.parse_args()
    migrate_site(args.legacy_root.resolve(), args.target_root.resolve())


if __name__ == "__main__":
    main()

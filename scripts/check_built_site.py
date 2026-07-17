from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import argparse
import sys

import yaml
from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.cv_data import (  # noqa: E402
    FORBIDDEN_CV_TEXT,
    MANDATORY_CV_TEXT,
    cv_content_manifest,
    cv_content_counts,
    load_cv_document,
    validate_cv_baseline,
)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = False
        self.h1 = 0
        self.links = []
        self.images_without_alt = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"])
        elif tag == "img" and "alt" not in values:
            self.images_without_alt.append(values.get("src", "unknown"))

    def handle_data(self, data):
        if self._in_title and data.strip():
            self.title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False


def target_for(public: Path, href: str, base_path: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc or href.startswith(("mailto:", "#")):
        return None
    base_path = f"/{base_path.strip('/')}/"
    path = parsed.path
    if path.startswith(base_path):
        path = path[len(base_path) :]
    elif path.startswith("/"):
        return public / "__outside_preview_path__" / path.lstrip("/")
    candidate = public / path.lstrip("/")
    if candidate.suffix:
        return candidate
    return candidate / "index.html"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) != 3:
        return {}
    loaded = yaml.safe_load(parts[1])
    return loaded if isinstance(loaded, dict) else {}


def _draft_output(public: Path, content: Path, source: Path) -> Path:
    metadata = _frontmatter(source)
    configured_url = metadata.get("url")
    if isinstance(configured_url, str) and configured_url.strip():
        return public / configured_url.strip("/") / "index.html"
    relative = source.relative_to(content)
    if relative.name in {"index.md", "_index.md"}:
        output_directory = relative.parent
    else:
        output_directory = relative.with_suffix("")
    return public / output_directory / "index.html"


def validate_cv(public_dir: Path, content_dir: Path | None = None) -> list[str]:
    cv_path = public_dir / "uploads" / "sean-ma-cv.pdf"
    if not cv_path.exists():
        return [f"Academic CV is missing: {cv_path}"]

    try:
        if not cv_path.is_file():
            raise ValueError("path is not a file")
        size = cv_path.stat().st_size
        if size <= 10_000:
            raise ValueError(f"file is too small ({size} bytes; expected more than 10000)")
        with cv_path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("missing %PDF- signature")
        reader = PdfReader(cv_path)
        if not reader.pages:
            raise ValueError("PDF has no pages")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        for forbidden in FORBIDDEN_CV_TEXT:
            if forbidden in text:
                raise ValueError(f"PDF text contains forbidden text {forbidden!r}")
        for expected in MANDATORY_CV_TEXT:
            if expected not in text:
                raise ValueError(f"PDF text is missing {expected!r}")
        if content_dir is not None:
            document = load_cv_document(content_dir.resolve().parent)
            validate_cv_baseline(document)
            expected_manifest = cv_content_manifest(cv_content_counts(document))
            subject = str(reader.metadata.subject or "")
            if subject != expected_manifest:
                raise ValueError(
                    "PDF content manifest is invalid: "
                    f"expected {expected_manifest!r}, found {subject!r}"
                )
    except Exception as error:
        return [f"Academic CV is invalid: {cv_path}: {error}"]
    return []


def check_site(public: Path, base_path: str, content: Path | None = None) -> list[str]:
    errors = []
    cv_path = public / "uploads" / "sean-ma-cv.pdf"
    pages = list(public.rglob("*.html"))
    if not pages:
        errors.append(f"{public}: no generated HTML pages")
    for page in pages:
        parser = PageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        if not parser.title:
            errors.append(f"{page}: missing title")
        if parser.images_without_alt:
            errors.append(f"{page}: images without alt: {parser.images_without_alt}")
        for href in parser.links:
            target = target_for(public, href, base_path)
            if target is not None and not target.exists():
                if target == cv_path:
                    continue
                errors.append(f"{page}: broken internal link {href}")
    if content is not None:
        for source in content.rglob("*.md"):
            try:
                metadata = _frontmatter(source)
            except (OSError, UnicodeError, yaml.YAMLError) as error:
                errors.append(f"{source}: cannot inspect draft status: {error}")
                continue
            if metadata.get("draft") is True:
                output = _draft_output(public, content, source)
                if output.exists():
                    errors.append(f"{output}: draft content was generated from {source}")
    errors.extend(validate_cv(public, content))
    return errors


def check(public: Path, base_path: str, content: Path | None = None) -> list[str]:
    return check_site(public, base_path, content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("public", type=Path)
    parser.add_argument("--base-path", default="/research-website-preview/")
    parser.add_argument("--content", type=Path)
    args = parser.parse_args()
    failures = check_site(args.public, args.base_path, args.content)
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Checked {len(list(args.public.rglob('*.html')))} HTML pages")

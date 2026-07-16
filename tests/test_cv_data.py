from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import yaml

from scripts.cv_data import (
    PublicationReview,
    load_cv_document,
    write_publication_review,
)


ROOT = Path(__file__).resolve().parents[1]


def write_frontmatter(path: Path, metadata: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
        + "---\n"
        + body,
        encoding="utf-8",
    )


def author_record() -> dict:
    return {
        "name": {
            "display": "Dr Sean Longyu Ma",
            "given": "Sean Longyu",
            "family": "Ma",
        },
        "postnominals": ["PhD"],
        "role": "Lecturer in Computer Science",
        "bio": "Research profile.",
        "affiliations": [
            {"name": "The University of Auckland", "url": "https://www.auckland.ac.nz/"}
        ],
        "links": [
            {"label": "Email", "url": "mailto:sean.ma@auckland.ac.nz"},
            {"label": "Google Scholar", "url": "https://scholar.google.com/example"},
            {"label": "ORCID", "url": "https://orcid.org/0000-0002-3350-004X"},
        ],
        "interests": ["FPGA acceleration", "RISC-V customisation"],
        "education": [
            {
                "degree": "PhD in Computer Science",
                "institution": "The University of Auckland",
                "end": "2023-12-31",
            }
        ],
    }


def publication_record(
    title: str,
    doi: str,
    *,
    draft: bool,
    managed: bool,
    requires_correction: bool,
) -> dict:
    metadata = {
        "title": title,
        "authors": ["me", "Alice Researcher"],
        "date": "2025-02-12T00:00:00Z",
        "draft": draft,
        "publication_types": ["article-journal"],
        "publication": {"name": "IEEE Transactions on Example"},
        "hugoblox": {"ids": {"doi": doi}},
        "links": [{"type": "source", "url": f"https://doi.org/{doi}"}],
        "requires_correction": requires_correction,
    }
    if managed:
        metadata["publication_importer"] = {"managed_citation": True}
    return metadata


class CvDataTests(unittest.TestCase):
    def make_repo(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "data/authors").mkdir(parents=True)
        (root / "data/authors/me.yaml").write_text(
            yaml.safe_dump(author_record(), sort_keys=False),
            encoding="utf-8",
        )
        (root / "content/publications").mkdir(parents=True)
        (root / "content/events").mkdir(parents=True)
        (root / "content/teaching").mkdir(parents=True)
        return temporary, root

    def replace_with_junction(self, path: Path, target: Path) -> None:
        path.rmdir()
        result = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(path), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.addCleanup(os.rmdir, path)

    def test_migrated_draft_is_included_but_managed_draft_is_excluded(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        write_frontmatter(
            root / "content/publications/legacy/index.md",
            publication_record(
                "Legacy Paper",
                "10.1000/legacy",
                draft=True,
                managed=False,
                requires_correction=False,
            ),
        )
        write_frontmatter(
            root / "content/publications/imported/index.md",
            publication_record(
                "Imported Draft",
                "10.1000/imported",
                draft=True,
                managed=True,
                requires_correction=False,
            ),
        )
        document = load_cv_document(root)
        self.assertEqual([item.title for item in document.publications], ["Legacy Paper"])
        reviews = {item.title: item for item in document.publication_reviews}
        self.assertTrue(reviews["Legacy Paper"].included)
        self.assertFalse(reviews["Imported Draft"].included)
        self.assertEqual(reviews["Imported Draft"].reason, "managed publication is draft")

    def test_managed_record_requires_final_valid_metadata(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        write_frontmatter(
            root / "content/publications/ready/index.md",
            publication_record(
                "Ready Paper",
                "10.1000/ready",
                draft=False,
                managed=True,
                requires_correction=False,
            ),
        )
        write_frontmatter(
            root / "content/publications/correction/index.md",
            publication_record(
                "Needs Correction",
                "10.1000/correction",
                draft=False,
                managed=True,
                requires_correction=True,
            ),
        )
        missing_draft = publication_record(
            "Missing Draft Review",
            "10.1000/missing-draft",
            draft=False,
            managed=True,
            requires_correction=False,
        )
        del missing_draft["draft"]
        write_frontmatter(
            root / "content/publications/missing-draft/index.md", missing_draft
        )
        missing_correction = publication_record(
            "Missing Correction Review",
            "10.1000/missing-correction",
            draft=False,
            managed=True,
            requires_correction=False,
        )
        del missing_correction["requires_correction"]
        write_frontmatter(
            root / "content/publications/missing-correction/index.md",
            missing_correction,
        )
        document = load_cv_document(root)
        self.assertEqual([item.title for item in document.publications], ["Ready Paper"])

    def test_duplicate_eligible_doi_fails(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        for slug in ("a", "b"):
            write_frontmatter(
                root / f"content/publications/{slug}/index.md",
                publication_record(
                    slug,
                    "10.1000/duplicate",
                    draft=True,
                    managed=False,
                    requires_correction=False,
                ),
            )
        with self.assertRaisesRegex(ValueError, "Duplicate eligible publication DOI"):
            load_cv_document(root)

    def test_migrated_publication_requires_at_least_one_author(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        metadata = publication_record(
            "Authorless Paper",
            "10.1000/authorless",
            draft=True,
            managed=False,
            requires_correction=False,
        )
        metadata["authors"] = []
        index = root / "content/publications/authorless/index.md"
        write_frontmatter(index, metadata)

        with self.assertRaisesRegex(
            ValueError, rf"{re.escape(str(index))}.*authors.*non-empty"
        ):
            load_cv_document(root)

    def test_publication_type_requires_exactly_one_non_empty_string(self):
        invalid_values = (
            "article-journal",
            [],
            ["article-journal", "chapter"],
            [42],
            ["   "],
        )
        for publication_types in invalid_values:
            with self.subTest(publication_types=publication_types):
                temporary, root = self.make_repo()
                self.addCleanup(temporary.cleanup)
                metadata = publication_record(
                    "Bad Type",
                    "10.1000/bad-type",
                    draft=True,
                    managed=False,
                    requires_correction=False,
                )
                metadata["publication_types"] = publication_types
                index = root / "content/publications/bad-type/index.md"
                write_frontmatter(index, metadata)

                with self.assertRaisesRegex(
                    ValueError,
                    rf"{re.escape(str(index))}.*publication_types",
                ):
                    load_cv_document(root)

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_event_and_teaching_directory_junctions_cannot_escape_repository(self):
        for section in ("events", "teaching"):
            with self.subTest(section=section):
                temporary, root = self.make_repo()
                self.addCleanup(temporary.cleanup)
                external = tempfile.TemporaryDirectory()
                self.addCleanup(external.cleanup)
                external_root = Path(external.name)
                self.replace_with_junction(root / "content" / section, external_root)

                with self.assertRaisesRegex(
                    ValueError, rf"{section}.*inside.*repository"
                ):
                    load_cv_document(root)

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_dangling_event_directory_junction_is_not_treated_as_missing(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        external_root = Path(tempfile.mkdtemp())
        self.replace_with_junction(root / "content/events", external_root)
        external_root.rmdir()

        with self.assertRaisesRegex(ValueError, r"events.*inside.*repository"):
            load_cv_document(root)

    def test_event_file_link_cannot_escape_repository(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        external_page = Path(external.name) / "outside.md"
        write_frontmatter(
            external_page,
            {
                "title": "Outside",
                "event": "External",
                "date": "2025-01-01T00:00:00Z",
            },
        )
        link = root / "content/events/outside.md"
        try:
            link.symlink_to(external_page)
        except OSError as error:
            if os.name != "nt":
                self.skipTest(f"File symlinks unavailable: {error}")
            result = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(link), external.name],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.addCleanup(os.rmdir, link)

        with self.assertRaisesRegex(ValueError, "Content page must resolve inside"):
            load_cv_document(root)

    def test_teaching_body_preserves_markdown_whitespace(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        body = "    indented code\nHard line break  \n\n"
        write_frontmatter(
            root / "content/teaching/whitespace.md",
            {
                "title": "Whitespace",
                "teaching_type": "Course",
                "venue": "University",
                "location": "Auckland",
            },
            body,
        )

        document = load_cv_document(root)

        self.assertEqual(document.teaching[0].body, body)

    def test_review_report_contains_required_columns(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        write_frontmatter(
            root / "content/publications/paper/index.md",
            publication_record(
                "Review Me",
                "10.1000/review",
                draft=True,
                managed=False,
                requires_correction=False,
            ),
        )
        document = load_cv_document(root)
        output = root / "output/cv/publication-review.md"
        write_publication_review(document, output)
        text = output.read_text(encoding="utf-8")
        self.assertIn("| Title | Date | Venue | DOI | Draft | Correction | Source | CV |", text)
        self.assertIn("Review Me", text)
        self.assertIn("10.1000/review", text)

    def test_review_report_safely_encodes_every_data_cell_and_source_url(self):
        temporary, root = self.make_repo()
        self.addCleanup(temporary.cleanup)
        document = load_cv_document(root)
        review = PublicationReview(
            bundle_path="content/publications/unsafe",
            title="Title | slash \\ line\nnext [link](javascript:alert(1))",
            date="Date | slash \\ line\nnext",
            venue="Venue | slash \\ line\nnext",
            doi="10.1000/a|b\\c\nnext",
            draft=True,
            requires_correction=True,
            source_url="https://example.test/a_(b)|c\\d\nnext?q=<unsafe>",
            included=False,
            reason="Reason | slash \\ line\nnext",
        )
        output = root / "output/cv/publication-review.md"
        write_publication_review(
            replace(document, publication_reviews=(review,)), output
        )
        text = output.read_text(encoding="utf-8")

        self.assertEqual(len(text.splitlines()), 5)
        for prefix in ("Title", "Date", "Venue"):
            self.assertIn(f"{prefix} \\| slash \\\\ line<br>next", text)
        self.assertIn(
            r"\[link\]\(javascript:alert\(1\)\)",
            text,
        )
        self.assertIn("10.1000/a\\|b\\\\c<br>next", text)
        self.assertIn("Exclude: Reason \\| slash \\\\ line<br>next", text)
        self.assertIn(
            "[source](<https://example.test/a_%28b%29%7Cc%5Cd%0Anext?q=%3Cunsafe%3E>)",
            text,
        )

    def test_real_repository_initial_cv_contains_all_33_migrated_publications(self):
        document = load_cv_document(ROOT)
        self.assertEqual(len(document.publications), 33)
        self.assertEqual(len({item.bundle_path for item in document.publications}), 33)


if __name__ == "__main__":
    unittest.main()

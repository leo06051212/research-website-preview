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
from scripts.publication_importer import read_frontmatter


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MIGRATED_BUNDLES = {
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
    else:
        metadata["cv_provenance"] = "migrated_legacy"
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
        write_frontmatter(
            root / "content/events/baseline.md",
            {
                "title": "Baseline Talk",
                "event": "Baseline Event",
                "date": "2025-01-01T00:00:00Z",
            },
        )
        write_frontmatter(
            root / "content/teaching/z-baseline.md",
            {
                "title": "Z Baseline Teaching",
                "teaching_type": "Course",
                "venue": "University",
                "location": "Auckland",
            },
            "Baseline teaching.",
        )
        return temporary, root

    def replace_with_junction(self, path: Path, target: Path) -> None:
        for child in path.iterdir():
            child.unlink()
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

    def test_publication_provenance_fails_closed(self):
        invalid_markers = {
            "deleted managed marker": None,
            "managed false": {"managed_citation": False},
            "managed string true": {"managed_citation": "true"},
            "misspelled managed key": {"managed_citaton": True},
        }
        for label, marker in invalid_markers.items():
            with self.subTest(label=label):
                temporary, root = self.make_repo()
                self.addCleanup(temporary.cleanup)
                metadata = publication_record(
                    "Untrusted Publication",
                    "10.1000/untrusted",
                    draft=True,
                    managed=True,
                    requires_correction=True,
                )
                if marker is None:
                    del metadata["publication_importer"]
                else:
                    metadata["publication_importer"] = marker
                index = root / "content/publications/untrusted/index.md"
                write_frontmatter(index, metadata)

                with self.assertRaisesRegex(
                    ValueError,
                    rf"{re.escape(str(index))}.*(provenance|publication_importer)",
                ):
                    load_cv_document(root)

    def test_legacy_provenance_must_be_exact_and_cannot_mix_with_importer(self):
        invalid_records = []
        wrong_value = publication_record(
            "Wrong Legacy",
            "10.1000/wrong-legacy",
            draft=True,
            managed=False,
            requires_correction=False,
        )
        wrong_value["cv_provenance"] = "legacy"
        invalid_records.append(wrong_value)
        mixed = publication_record(
            "Mixed Legacy",
            "10.1000/mixed-legacy",
            draft=True,
            managed=False,
            requires_correction=False,
        )
        mixed["publication_importer"] = {"managed_citation": True}
        invalid_records.append(mixed)

        for index_number, metadata in enumerate(invalid_records):
            with self.subTest(title=metadata["title"]):
                temporary, root = self.make_repo()
                self.addCleanup(temporary.cleanup)
                index = root / f"content/publications/invalid-{index_number}/index.md"
                write_frontmatter(index, metadata)
                with self.assertRaisesRegex(ValueError, "cv_provenance"):
                    load_cv_document(root)

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

        teaching = next(item for item in document.teaching if item.title == "Whitespace")
        self.assertEqual(teaching.body, body)

    def test_required_author_collections_cannot_be_empty(self):
        for field in ("links", "interests", "education"):
            with self.subTest(field=field):
                temporary, root = self.make_repo()
                self.addCleanup(temporary.cleanup)
                author = author_record()
                author[field] = []
                path = root / "data/authors/me.yaml"
                path.write_text(
                    yaml.safe_dump(author, sort_keys=False), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, rf"{field}.*non-empty"):
                    load_cv_document(root)

    def test_required_talk_and_teaching_collections_cannot_be_missing_or_empty(self):
        for section, baseline in (
            ("events", "baseline.md"),
            ("teaching", "z-baseline.md"),
        ):
            for missing_directory in (False, True):
                with self.subTest(
                    section=section, missing_directory=missing_directory
                ):
                    temporary, root = self.make_repo()
                    self.addCleanup(temporary.cleanup)
                    directory = root / "content" / section
                    (directory / baseline).unlink()
                    if missing_directory:
                        directory.rmdir()
                    with self.assertRaisesRegex(
                        ValueError, rf"{section}.*(missing|at least one)"
                    ):
                        load_cv_document(root)

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
        self.assertEqual(
            {item.bundle_path for item in document.publications},
            EXPECTED_MIGRATED_BUNDLES,
        )
        self.assertEqual(
            document.author.interests,
            (
                "FPGA acceleration",
                "RISC-V customisation",
                "High-level synthesis",
                "Heterogeneous computing",
            ),
        )
        self.assertEqual(
            tuple((item.degree, item.institution, item.year) for item in document.author.education),
            (
                ("PhD in Computer Science", "The University of Auckland", 2023),
                ("Master of Integrated Circuit Engineering", "Shanghai Jiao Tong University", 2016),
                ("Bachelor of Communication Engineering", "Harbin Engineering University", 2010),
            ),
        )
        self.assertEqual(
            tuple(item.title for item in document.talks),
            (
                "2026 IEEE International Symposium on Circuits and Systems",
                "Technical Talks of IEEE Consumer Technoligy Society - 19th Webinar",
                "IEEE CASS Workshop: Circuit-Level Intelligence: From Secure Silicon to AI-Ready Systems",
                "Interal Talk with staff in Computer Science, UoA",
                "Journey to the “South”: Advancing Computing from Traditional Architectures to Emerging Technologies",
                "Joint 6G-PHYSEC & INTERACT Workshop on 6G Technologies and PHY Layer Security",
                "WebVM - an innovative approach to teaching OS concepts",
            ),
        )
        self.assertEqual(
            tuple(item.title for item in document.teaching),
            (
                "UoA Postgraduate Supervision experience",
                "UoA Undergraduate Teaching experience",
            ),
        )

        for publication in document.publications:
            index = ROOT / publication.bundle_path / "index.md"
            metadata, _ = read_frontmatter(index)
            self.assertEqual(
                metadata.get("cv_provenance"),
                "migrated_legacy",
                index,
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas
import yaml

from scripts.cv_data import CvTeaching, MANDATORY_CV_TEXT, load_cv_document
from scripts.cv_pdf import render_cv_pdf, validate_pdf
from tests.test_cv_data import author_record, publication_record, write_frontmatter


ROOT = Path(__file__).resolve().parents[1]


class CvPdfTests(unittest.TestCase):
    def _write_minimal_repo(self, root: Path) -> None:
        (root / "data/authors").mkdir(parents=True)
        author = author_record()
        author["bio"] = "Research profile & secure <systems>."
        (root / "data/authors/me.yaml").write_text(
            yaml.safe_dump(author, sort_keys=False),
            encoding="utf-8",
        )
        for index in range(45):
            metadata = publication_record(
                f"Research Publication {index:02d}",
                f"10.1000/paper-{index:02d}",
                draft=True,
                managed=False,
                requires_correction=False,
            )
            if index == 0:
                metadata["title"] = "Safe <Research> & Development"
            write_frontmatter(
                root / f"content/publications/paper-{index:02d}/index.md",
                metadata,
            )
        write_frontmatter(
            root / "content/events/talk.md",
            {
                "title": "Invited Research Talk",
                "event": "Research Seminar",
                "venue": "The University of Auckland",
                "location": "Auckland, New Zealand",
                "date": "2025-06-01T00:00:00Z",
                "links": [{"type": "source", "url": "https://example.org/talk"}],
            },
        )
        write_frontmatter(
            root / "content/teaching/teaching.md",
            {
                "title": "Course Teaching",
                "teaching_type": "Course",
                "venue": "The University of Auckland",
                "location": "Auckland, New Zealand",
            },
            "Current course teaching.",
        )

    def _render_fixture(self, root: Path):
        self._write_minimal_repo(root)
        portrait = root / "portrait.jpg"
        Image.new("RGB", (600, 800), "#1d2939").save(portrait, "JPEG")
        output = root / "static/uploads/sean-ma-cv.pdf"
        result = render_cv_pdf(
            load_cv_document(root),
            portrait,
            output,
            generated_on=date(2026, 7, 17),
        )
        return output, result

    def _render_canonical(self, root: Path):
        portrait = root / "portrait.jpg"
        Image.new("RGB", (600, 800), "#1d2939").save(portrait, "JPEG")
        output = root / "canonical.pdf"
        result = render_cv_pdf(
            load_cv_document(ROOT),
            portrait,
            output,
            generated_on=date(2026, 7, 17),
        )
        return output, result

    def test_pdf_is_searchable_paginated_and_contains_required_sections(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output, result = self._render_fixture(Path(temporary.name))
        self.assertEqual(output.read_bytes()[:5], b"%PDF-")
        self.assertGreater(output.stat().st_size, 10_000)
        reader = PdfReader(output)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertGreaterEqual(len(reader.pages), 2)
        for required in (
            "Sean Longyu Ma",
            "Academic Profile",
            "Current Academic Appointment",
            "Publications",
            "Research Interests",
            "Education",
            "Invited Talks & Presentations",
            "Teaching",
            "Generated 17 July 2026",
            "Safe <Research> & Development",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertEqual(reader.metadata.title, "Sean Longyu Ma - Academic CV")
        self.assertEqual(reader.metadata.author, "Sean Longyu Ma")
        self.assertEqual(result.page_count, len(reader.pages))
        self.assertGreater(result.byte_count, 10_000)

    def test_validate_pdf_rejects_obsolete_teaching_supervision_heading(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "obsolete-heading.pdf"
        document = canvas.Canvas(str(output), pageCompression=0)
        y = 800
        for value in MANDATORY_CV_TEXT:
            rendered = (
                "Teaching & Postgraduate Supervision"
                if value == "Teaching"
                else value
            )
            document.drawString(40, y, rendered)
            y -= 20
        document.drawString(40, y, "Current undergraduate course teaching details")
        document.drawString(40, y - 20, "x" * 12_000)
        document.save()

        with self.assertRaisesRegex(
            ValueError,
            "forbidden.*Teaching & Postgraduate Supervision",
        ):
            validate_pdf(output)

    def test_pdf_contains_doi_and_profile_link_annotations(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output, _ = self._render_fixture(Path(temporary.name))
        reader = PdfReader(output)
        uris = {
            annotation.get_object()["/A"]["/URI"]
            for page in reader.pages
            for annotation in page.get("/Annots", [])
            if "/A" in annotation.get_object()
            and "/URI" in annotation.get_object()["/A"]
        }
        self.assertIn("https://doi.org/10.1000/paper-00", uris)
        self.assertIn("https://orcid.org/0000-0002-3350-004X", uris)
        self.assertIn("mailto:sean.ma@auckland.ac.nz", uris)
        self.assertIn("https://www.auckland.ac.nz/", uris)
        self.assertIn("https://example.org/talk", uris)

    def test_owner_author_uses_embedded_bold_font(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output, _ = self._render_fixture(Path(temporary.name))
        reader = PdfReader(output)
        fonts = {
            str(font.get_object().get("/BaseFont", ""))
            for page in reader.pages
            for font in page["/Resources"]["/Font"].get_object().values()
        }
        self.assertTrue(any("BitstreamVeraSans-Bold" in name for name in fonts), fonts)

    def test_rail_name_is_not_split_before_the_family_name(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output, _ = self._render_fixture(Path(temporary.name))
        first_page_text = PdfReader(output).pages[0].extract_text() or ""
        self.assertNotIn("Sean Longyu\nMa\nPhD", first_page_text)

    def test_first_page_rail_overflow_fails_before_replacing_output(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self._write_minimal_repo(root)
        document = load_cv_document(root)
        document = replace(
            document,
            author=replace(
                document.author,
                interests=tuple(
                    f"Extremely long research interest {index} with additional detail"
                    for index in range(60)
                ),
            ),
        )
        portrait = root / "portrait.jpg"
        Image.new("RGB", (600, 800), "#1d2939").save(portrait, "JPEG")
        output = root / "static/uploads/sean-ma-cv.pdf"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"%PDF-existing-candidate")

        with self.assertRaisesRegex(
            ValueError, r"first-page rail.*Research Interests"
        ):
            render_cv_pdf(
                document,
                portrait,
                output,
                generated_on=date(2026, 7, 17),
            )

        self.assertEqual(output.read_bytes(), b"%PDF-existing-candidate")

    def test_first_page_rail_near_capacity_still_renders_complete_education(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self._write_minimal_repo(root)
        document = load_cv_document(root)
        document = replace(
            document,
            author=replace(
                document.author,
                interests=tuple(
                    f"Research interest {index} with concise supporting detail"
                    for index in range(16)
                ),
            ),
        )
        portrait = root / "portrait.jpg"
        Image.new("RGB", (600, 800), "#1d2939").save(portrait, "JPEG")
        output = root / "near-capacity.pdf"

        render_cv_pdf(
            document,
            portrait,
            output,
            generated_on=date(2026, 7, 17),
        )

        first_page_text = PdfReader(output).pages[0].extract_text() or ""
        self.assertIn("PhD in Computer Science", first_page_text)

    def test_publication_entry_is_not_split_across_pages(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output, _ = self._render_fixture(Path(temporary.name))
        second_page_lines = (
            PdfReader(output).pages[1].extract_text() or ""
        ).splitlines()
        self.assertTrue(
            second_page_lines[3].startswith("Research Publication"),
            second_page_lines[:6],
        )

    def test_failure_does_not_replace_previous_pdf(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self._write_minimal_repo(root)
        output = root / "static/uploads/sean-ma-cv.pdf"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"%PDF-old-valid-placeholder")
        missing_portrait = root / "missing.jpg"
        with self.assertRaisesRegex(ValueError, "Portrait"):
            render_cv_pdf(
                load_cv_document(root),
                missing_portrait,
                output,
                generated_on=date(2026, 7, 17),
            )
        self.assertEqual(output.read_bytes(), b"%PDF-old-valid-placeholder")

    def test_canonical_cjk_venue_is_visible_and_searchable(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output, _ = self._render_canonical(Path(temporary.name))
        reader = PdfReader(output)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("Room 408 微电子楼", text)
        self.assertNotIn("\x00", text)
        fonts = {
            str(font.get_object().get("/BaseFont", ""))
            for page in reader.pages
            for font in page["/Resources"]["/Font"].get_object().values()
        }
        self.assertTrue(any("STSong-Light" in font for font in fonts), fonts)

    def test_real_pdf_contains_courses_but_no_supervision_or_student_details(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "cv.pdf"
        document = load_cv_document(ROOT)
        render_cv_pdf(
            document,
            ROOT / "assets/media/authors/me.jpg",
            output,
            generated_on=date(2026, 7, 17),
        )
        reader = PdfReader(output)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertIn("Teaching", text)
        self.assertNotIn("Teaching & Postgraduate Supervision", text)
        _, teaching_heading, teaching_text = text.rpartition("\nTeaching\n")
        self.assertEqual(teaching_heading, "\nTeaching\n")
        for course in (
            "COMPSCI 110 Introduction to Computer Systems",
            "COMPSCI 315 Data Communications Technologies",
            "COMPSCI 215 Data Communication",
            "SOFTENG 370 Operating System",
            "COMPSCI 340 Operating System",
        ):
            self.assertIn(course, teaching_text)
        for private_text in (
            "UoA Postgraduate Supervision experience",
            "Neural Network Circuit and Computing-in-Memory Accelerator",
            "Doctor of Philosophy in Computer Science",
        ):
            self.assertNotIn(private_text, text)
        for student_name in (
            "Xu Chen",
            "Jiale Li",
            "Yulin Fu",
            "Tingjiang Tan",
            "Taojingnan Wang",
            "Ziyuan Zhang",
            "Chenge Gao",
            "Cheng Cheng",
        ):
            self.assertNotIn(student_name, teaching_text)
        self.assertTrue(str(reader.metadata.subject).endswith("talks=7;teaching=1"))

    def test_overheight_teaching_entry_splits_and_preserves_all_text(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self._write_minimal_repo(root)
        portrait = root / "portrait.jpg"
        Image.new("RGB", (600, 800), "#1d2939").save(portrait, "JPEG")
        items = [f"Searchable teaching item {index:04d}" for index in range(400)]
        teaching_body = (
            "# Editorial Heading\n"
            "Lead with hard break  \n"
            "continuation\n"
            "1. Ordered guidance\n"
            + "\n".join(f"- {item}" for item in items)
        )
        document = replace(
            load_cv_document(root),
            teaching=(
                CvTeaching(
                    title="Long Teaching Record",
                    teaching_type="Teaching",
                    venue="The University of Auckland",
                    location="Auckland, New Zealand",
                    body=teaching_body,
                ),
            ),
        )
        output = root / "long-teaching.pdf"
        result = render_cv_pdf(
            document,
            portrait,
            output,
            generated_on=date(2026, 7, 17),
        )
        text = "\n".join(page.extract_text() or "" for page in PdfReader(output).pages)
        self.assertGreater(result.page_count, 4)
        self.assertEqual(text.count("Searchable teaching item"), len(items))
        self.assertIn(items[0], text)
        self.assertIn(items[-1], text)
        self.assertIn("Editorial Heading", text)
        self.assertNotIn("# Editorial Heading", text)
        self.assertIn("Lead with hard break\ncontinuation", text)
        self.assertIn("1. Ordered guidance", text)

    def test_corrupt_portrait_is_rejected_before_build_and_preserves_output(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self._write_minimal_repo(root)
        portrait = root / "corrupt-portrait.jpg"
        portrait.write_bytes(b"this is not an image")
        output = root / "static/uploads/sean-ma-cv.pdf"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"%PDF-old-valid-placeholder")

        with self.assertRaisesRegex(
            ValueError,
            rf"Portrait.*{portrait.name}.*valid image",
        ):
            render_cv_pdf(
                load_cv_document(root),
                portrait,
                output,
                generated_on=date(2026, 7, 17),
            )

        self.assertEqual(output.read_bytes(), b"%PDF-old-valid-placeholder")
        self.assertEqual(list(output.parent.glob(f".{output.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()

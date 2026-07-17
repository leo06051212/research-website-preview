from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date
import importlib.util
import io
import shutil
import unittest

from reportlab.pdfgen import canvas
import yaml

from scripts.cv_data import load_cv_document
from scripts.cv_pdf import render_cv_pdf

ROOT = Path(__file__).resolve().parents[1]
MANDATORY_CV_SECTIONS = (
    "Academic Profile",
    "Current Academic Appointment",
    "Research Interests",
    "Education",
    "Publications",
    "Invited Talks & Presentations",
    "Teaching",
)
VALID_CV_MANIFEST = (
    "Academic curriculum vitae | publications=33;interests=4;education=3;"
    "talks=7;teaching=1"
)


def load_checker():
    path = ROOT / "scripts/check_built_site.py"
    if not path.is_file():
        raise AssertionError(f"missing built-site checker: {path}")
    spec = importlib.util.spec_from_file_location("check_built_site", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BuiltSiteCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.public = self.root / "public"
        self.content = self.root / "content"

    def tearDown(self):
        self.temp.cleanup()

    def write_valid_site(self, *, sections=MANDATORY_CV_SECTIONS, subject=VALID_CV_MANIFEST):
        self.public.mkdir(parents=True)
        self.content.mkdir(parents=True)
        (self.public / "index.html").write_text(
            "<html><title>Home</title></html>", encoding="utf-8"
        )
        cv_path = self.public / "uploads" / "sean-ma-cv.pdf"
        cv_path.parent.mkdir(parents=True)
        buffer = io.BytesIO()
        document = canvas.Canvas(buffer, pageCompression=0)
        document.setSubject(subject)
        document.drawString(72, 760, "Sean Longyu Ma")
        document.drawString(72, 740, "Academic CV")
        y = 720
        for section in sections:
            document.drawString(72, y, section)
            y -= 20
        document.drawString(72, y, "x" * 12_000)
        document.save()
        cv_path.write_bytes(buffer.getvalue())

    def test_target_for_rejects_root_links_outside_preview(self):
        checker = load_checker()
        public = Path("public")
        self.assertEqual(
            checker.target_for(public, "/research-website-preview/blog/", "/research-website-preview/"),
            public / "blog" / "index.html",
        )
        self.assertEqual(
            checker.target_for(public, "/blog/", "/research-website-preview/"),
            public / "__outside_preview_path__" / "blog",
        )
        self.assertIsNone(checker.target_for(public, "https://example.org", "/research-website-preview/"))
        self.assertEqual(
            checker.target_for(
                public,
                "/research-website-preview/uploads/sean-ma-cv.pdf",
                "/research-website-preview/",
            ),
            public / "uploads" / "sean-ma-cv.pdf",
        )

    def test_check_accepts_real_cv(self):
        checker = load_checker()
        self.write_valid_site()

        failures = checker.check_site(
            self.public, "/research-website-preview/", ROOT / "content"
        )

        self.assertEqual(failures, [])

    def test_check_rejects_missing_cv(self):
        checker = load_checker()
        self.write_valid_site()
        for name in ("index.html", "second.html", "nested/page.html"):
            page = self.public / name
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(
                '<html><title>CV link</title><a href="/research-website-preview/'
                'uploads/sean-ma-cv.pdf">Academic CV</a></html>',
                encoding="utf-8",
            )
        (self.public / "uploads" / "sean-ma-cv.pdf").unlink()

        failures = checker.check_site(
            self.public, "/research-website-preview/", ROOT / "content"
        )

        self.assertEqual(len(failures), 1)
        self.assertIn("Academic CV is missing", failures[0])
        self.assertNotIn("broken internal link", failures[0])

    def test_check_rejects_tiny_cv(self):
        checker = load_checker()
        self.write_valid_site()
        cv_path = self.public / "uploads" / "sean-ma-cv.pdf"
        cv_path.write_bytes(b"not a pdf")

        failures = checker.check_site(
            self.public, "/research-website-preview/", ROOT / "content"
        )

        self.assertEqual(len(failures), 1)
        self.assertIn(f"Academic CV is invalid: {cv_path}", failures[0])
        self.assertIn("too small", failures[0])

    def test_check_rejects_oversized_cv_without_pdf_signature(self):
        checker = load_checker()
        self.write_valid_site()
        cv_path = self.public / "uploads" / "sean-ma-cv.pdf"
        cv_path.write_bytes(b"not a pdf" + b"x" * 11_000)

        failures = checker.check_site(
            self.public, "/research-website-preview/", ROOT / "content"
        )

        self.assertEqual(len(failures), 1)
        self.assertIn(f"Academic CV is invalid: {cv_path}", failures[0])
        self.assertIn("missing %PDF- signature", failures[0])

    def test_check_rejects_oversized_unparseable_pdf(self):
        checker = load_checker()
        self.write_valid_site()
        cv_path = self.public / "uploads" / "sean-ma-cv.pdf"
        cv_path.write_bytes(b"%PDF-1.7\n" + b"x" * 11_000 + b"\n%%EOF")

        failures = checker.check_site(
            self.public, "/research-website-preview/", ROOT / "content"
        )

        self.assertEqual(len(failures), 1)
        self.assertIn(f"Academic CV is invalid: {cv_path}", failures[0])
        self.assertNotIn("too small", failures[0])
        self.assertNotIn("missing %PDF- signature", failures[0])

    def test_check_rejects_cv_missing_a_mandatory_section(self):
        checker = load_checker()
        self.write_valid_site(sections=MANDATORY_CV_SECTIONS[:-1])

        failures = checker.check_site(
            self.public, "/research-website-preview/", ROOT / "content"
        )

        self.assertEqual(len(failures), 1)
        self.assertIn("Teaching", failures[0])

    def test_check_rejects_cv_with_wrong_real_content_counts(self):
        checker = load_checker()
        self.write_valid_site(
            subject=VALID_CV_MANIFEST.replace("talks=7", "talks=6")
        )

        failures = checker.check_site(
            self.public, "/research-website-preview/", ROOT / "content"
        )

        self.assertEqual(len(failures), 1)
        self.assertIn("content manifest", failures[0])

    def test_full_gate_accepts_valid_34th_managed_publication(self):
        checker = load_checker()
        shutil.copytree(ROOT / "data", self.root / "data")
        shutil.copytree(ROOT / "content", self.content)
        future = {
            "title": "Future managed publication",
            "authors": ["me", "Future Researcher"],
            "date": "2026-07-17T00:00:00Z",
            "draft": False,
            "publication_types": ["article-journal"],
            "publication": {"name": "Future Journal"},
            "hugoblox": {
                "ids": {"doi": "10.1000/future-managed-publication"}
            },
            "links": [
                {
                    "type": "source",
                    "url": "https://doi.org/10.1000/future-managed-publication",
                }
            ],
            "requires_correction": False,
            "publication_importer": {"managed_citation": True},
        }
        future_index = (
            self.content / "publications/future-managed-publication/index.md"
        )
        future_index.parent.mkdir(parents=True)
        future_index.write_text(
            "---\n"
            + yaml.safe_dump(future, sort_keys=False)
            + "---\n",
            encoding="utf-8",
        )
        document = load_cv_document(self.root)
        self.assertEqual(len(document.publications), 34)
        self.public.mkdir(parents=True)
        (self.public / "index.html").write_text(
            "<html><title>Home</title></html>", encoding="utf-8"
        )
        render_cv_pdf(
            document,
            ROOT / "assets/media/authors/me.jpg",
            self.public / "uploads/sean-ma-cv.pdf",
            date(2026, 7, 17),
        )

        failures = checker.check_site(
            self.public,
            "/research-website-preview/",
            self.content,
        )

        self.assertEqual(failures, [])

    def test_check_reports_missing_semantics_and_broken_internal_link(self):
        checker = load_checker()
        with TemporaryDirectory() as temp:
            public = Path(temp)
            (public / "index.html").write_text(
                '<html><title>Home</title><img src="portrait.webp">'
                '<a href="/research-website-preview/missing/">Missing</a></html>',
                encoding="utf-8",
            )

            failures = checker.check(public, "/research-website-preview/")

        self.assertTrue(any("images without alt" in failure for failure in failures))
        self.assertTrue(any("broken internal link" in failure for failure in failures))

    def test_check_rejects_generated_output_for_source_draft(self):
        checker = load_checker()
        with TemporaryDirectory() as temp:
            root = Path(temp)
            public = root / "public"
            content = root / "content"
            draft_source = content / "publications" / "review-me" / "index.md"
            draft_output = public / "publications" / "review-me" / "index.html"
            draft_source.parent.mkdir(parents=True)
            draft_output.parent.mkdir(parents=True)
            draft_source.write_text("---\ntitle: Review me\ndraft: true\n---\n", encoding="utf-8")
            draft_output.write_text("<html><title>Leaked draft</title></html>", encoding="utf-8")

            failures = checker.check(public, "/research-website-preview/", content)

        self.assertTrue(any("draft content was generated" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()

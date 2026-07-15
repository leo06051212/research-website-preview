from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]


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
        self.assertIsNone(
            checker.target_for(
                public,
                "/research-website-preview/uploads/sean-ma-cv.pdf",
                "/research-website-preview/",
            )
        )

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

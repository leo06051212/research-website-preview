from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class SiteContractTests(unittest.TestCase):
    def load_yaml(self, relative_path: str):
        return yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))

    def test_preview_url_and_language(self):
        config = self.load_yaml("config/_default/hugo.yaml")
        self.assertEqual(
            config["baseURL"],
            "https://leo06051212.github.io/research-website-preview/",
        )
        self.assertEqual(config["defaultContentLanguage"], "en")

    def test_navigation_contract(self):
        menus = self.load_yaml("config/_default/menus.yaml")
        labels = [item["name"] for item in menus["main"]]
        self.assertEqual(
            labels,
            ["About", "Research", "Publications", "Talks", "Teaching", "Blog", "CV"],
        )

    def test_owner_contract(self):
        owner = self.load_yaml("data/authors/me.yaml")
        self.assertEqual(owner["name"]["display"], "Dr Sean Longyu Ma")
        self.assertEqual(owner["role"], "Lecturer in Computer Science")
        urls = {link["url"] for link in owner["links"]}
        self.assertIn("https://orcid.org/0000-0002-3350-004X", urls)
        self.assertIn("https://scholar.google.com/citations?user=zDtLcAUAAAAJ&hl=en", urls)

    def test_required_section_roots_exist(self):
        for path in [
            "content/research/_index.md",
            "content/publications/_index.md",
            "content/events/_index.md",
            "content/teaching/_index.md",
            "content/blog/_index.md",
        ]:
            self.assertTrue((ROOT / path).is_file(), path)

    def test_homepage_contains_required_sections(self):
        text = (ROOT / "content/_index.md").read_text(encoding="utf-8")
        for heading in [
            "Research Interests",
            "Selected Publications",
            "Recent Updates",
            "Prospective Students",
        ]:
            self.assertIn(heading, text)

    def test_preview_is_not_indexed(self):
        hook = ROOT / "layouts/_partials/hooks/head-end/noindex.html"
        self.assertIn('content="noindex,nofollow"', hook.read_text(encoding="utf-8"))

    def test_editorial_typography_contract(self):
        params = self.load_yaml("config/_default/params.yaml")
        self.assertEqual(params["hugoblox"]["typography"]["pack"], "academic")

        css = (ROOT / "assets/css/custom.css").read_text(encoding="utf-8")
        self.assertIn("--sean-interface-font: ui-sans-serif", css)
        interface_rule = re.search(
            r"([^{}]+)\{[^{}]*font-family:\s*var\(--sean-interface-font\);[^{}]*\}",
            css,
        )
        self.assertIsNotNone(interface_rule)
        interface_selectors = {
            selector.strip() for selector in interface_rule.group(1).split(",")
        }
        for selector in [
            "nav",
            ".navbar",
            ".nav-link",
            ".nav-dropdown-link",
            "button",
            "input",
            "select",
            "textarea",
            '[role="button"]',
            ".btn",
            ".page-footer",
            "footer",
        ]:
            self.assertIn(selector, interface_selectors)
        self.assertNotIn("h1", interface_selectors)

    def test_pages_cms_collections(self):
        cms = self.load_yaml(".pages.yml")
        collections = {item["name"]: item for item in cms["content"]}
        self.assertEqual(
            set(collections),
            {"publication_imports", "publications", "talks", "blog", "teaching", "profile"},
        )

        expected_sources = {
            "publication_imports": (
                "data/publication-imports",
                "yaml",
                "{year}-{month}-{day}-{hour}-{minute}-{source}.yml",
            ),
            "publications": ("content/publications", "yaml-frontmatter", None),
            "talks": (
                "content/events",
                "yaml-frontmatter",
                "{year}-{month}-{day}-{title}.md",
            ),
            "blog": (
                "content/blog",
                "yaml-frontmatter",
                "{year}-{month}-{day}-{title}.md",
            ),
            "teaching": ("content/teaching", "yaml-frontmatter", "{title}.md"),
            "profile": ("data/authors/me.yaml", "yaml", None),
        }
        for name, (path, format_name, filename) in expected_sources.items():
            collection = collections[name]
            self.assertEqual(collection["path"], path)
            self.assertEqual(collection["format"], format_name)
            self.assertEqual(collection.get("filename"), filename)

        publications = collections["publications"]
        self.assertFalse(publications["operations"]["create"])
        self.assertEqual(publications["view"]["node"]["filename"], "index.md")
        publication_fields = {
            field["name"]: field for field in publications["fields"]
        }
        self.assertIn("requires_correction", publication_fields)
        self.assertNotIn("readonly", publication_fields["requires_correction"])
        for name in ["correction_reasons", "date_precision", "publication_date_parts"]:
            self.assertIn(name, publication_fields)
            self.assertTrue(publication_fields[name]["readonly"])
        metadata_fields = {
            field["name"]
            for field in publication_fields["publication"]["fields"]
        }
        self.assertIn("publisher", metadata_fields)
        self.assertIn("article_number", metadata_fields)

        for name in ["talks", "blog", "teaching"]:
            fields = {field["name"]: field for field in collections[name]["fields"]}
            self.assertTrue(fields["draft"]["default"])

        import_fields = {
            field["name"]: field for field in collections["publication_imports"]["fields"]
        }
        self.assertEqual(import_fields["status"]["default"], "pending")
        for name in ["status", "result_path", "error"]:
            self.assertTrue(import_fields[name]["readonly"])

        profile_fields = {field["name"] for field in collections["profile"]["fields"]}
        self.assertEqual(profile_fields, {"role", "bio", "interests"})

        self.assertEqual(cms["media"]["input"], "static/uploads")
        self.assertEqual(cms["media"]["output"], "/research-website-preview/uploads")
        self.assertIs(cms.get("settings", {}).get("content", {}).get("merge"), True)

if __name__ == "__main__":
    unittest.main()

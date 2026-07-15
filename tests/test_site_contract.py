from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()

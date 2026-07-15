from pathlib import Path
from html.parser import HTMLParser
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class GeneratedHomepageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section_id = None
        self.current_anchor = None
        self.cv_cta = None
        self.custom_css_href = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "section":
            self.section_id = attributes.get("id")
        elif tag == "a":
            self.current_anchor = {
                "attributes": attributes,
                "section_id": self.section_id,
                "text": [],
            }
        elif tag == "link":
            href = attributes.get("href", "")
            if "/css/custom.min." in href:
                self.custom_css_href = href

    def handle_data(self, data):
        if self.current_anchor is not None:
            self.current_anchor["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_anchor is not None:
            text = " ".join("".join(self.current_anchor["text"]).split())
            if text == "Download CV":
                self.cv_cta = self.current_anchor
            self.current_anchor = None
        elif tag == "section":
            self.section_id = None


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

    def test_generated_cv_cta_uses_interface_font(self):
        homepage = (ROOT / "public/index.html").read_text(encoding="utf-8")
        parser = GeneratedHomepageParser()
        parser.feed(homepage)

        self.assertIsNotNone(parser.cv_cta, "generated Download CV CTA not found")
        self.assertEqual(parser.cv_cta["section_id"], "section-resume-biography-3")
        href = parser.cv_cta["attributes"].get("href", "")
        self.assertTrue(href.endswith("/uploads/sean-ma-cv.pdf"), href)

        self.assertIsNotNone(parser.custom_css_href, "generated custom CSS not linked")
        css_path = ROOT / "public" / parser.custom_css_href.removeprefix(
            "/research-website-preview/"
        )
        css = css_path.read_text(encoding="utf-8")
        selector = (
            f'#{parser.cv_cta["section_id"]} '
            'a[href$="/uploads/sean-ma-cv.pdf"]'
        )
        rules = {
            item.strip(): declarations
            for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]+)\}", css)
            for item in selectors.split(",")
        }
        self.assertIn(selector, rules)
        self.assertIn("font-family:var(--sean-interface-font)", rules[selector])


if __name__ == "__main__":
    unittest.main()

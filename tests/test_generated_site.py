from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

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


class GeneratedSiteTests(unittest.TestCase):
    def test_cv_cta_uses_interface_font(self):
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

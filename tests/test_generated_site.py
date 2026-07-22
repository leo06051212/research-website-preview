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


class GeneratedSelectedPublicationsParser(HTMLParser):
    SECTION_ID = "section-content-collection"
    HEADING = "Selected Publications"

    def __init__(self):
        super().__init__()
        self.section_depth = 0
        self.in_selected_publications = False
        self.has_expected_heading = False
        self.current_section_has_expected_heading = False
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "section":
            if self.in_selected_publications:
                self.section_depth += 1
            elif attributes.get("id") == self.SECTION_ID:
                self.in_selected_publications = True
                self.section_depth = 1
                self.current_section_has_expected_heading = False
        elif (
            self.in_selected_publications
            and self.current_section_has_expected_heading
            and tag == "a"
            and attributes.get("href")
        ):
            self.links.append(attributes["href"])

    def handle_data(self, data):
        if (
            self.in_selected_publications
            and " ".join(data.split()) == self.HEADING
        ):
            self.has_expected_heading = True
            self.current_section_has_expected_heading = True

    def handle_endtag(self, tag):
        if tag == "section" and self.in_selected_publications:
            self.section_depth -= 1
            if self.section_depth == 0:
                self.in_selected_publications = False
                self.current_section_has_expected_heading = False


class GeneratedContentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])

    def handle_data(self, data):
        if data.strip():
            self.text_parts.append(data.strip())

    @property
    def text(self):
        return " ".join(" ".join(self.text_parts).split())


def parse_generated_page(path: Path) -> GeneratedContentParser:
    parser = GeneratedContentParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


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
            "/"
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

    def test_publications_listing_contains_all_local_records_and_homepage_features(self):
        expected_slugs = {
            index.parent.name
            for index in (ROOT / "content/publications").glob("*/index.md")
        }
        self.assertEqual(len(expected_slugs), 33)
        listing_pages = [ROOT / "public/publications/index.html"] + sorted(
            (ROOT / "public/publications/page").glob("*/index.html")
        )
        listing_links = {
            link
            for page in listing_pages
            for link in parse_generated_page(page).links
        }
        listed_slugs = set()
        for link in listing_links:
            match = re.fullmatch(
                r"/publications/([^/]+)/",
                link,
            )
            if match:
                listed_slugs.add(match.group(1))
        self.assertEqual(listed_slugs, expected_slugs)

        expected_featured_slugs = {
            "2025-12-15-a-review-of-fpga-driven-llm-acceleration",
            "2025-12-15-adaptive-gradual-quantization-with-a-custom-risc-v-simd-accelerator",
            "2025-09-23-enhancing-synthesis-efficiency-in-hls-through-llm-based-automated-cod",
            "2025-06-30-lha-layer-wise-hardware-acceleration-of-progressive-quantizing-infere",
        }
        homepage = (ROOT / "public/index.html").read_text(encoding="utf-8")
        selected_publications = GeneratedSelectedPublicationsParser()
        selected_publications.feed(homepage)
        self.assertTrue(
            selected_publications.has_expected_heading,
            "generated Selected Publications collection not found",
        )
        featured_slugs = set()
        for link in selected_publications.links:
            match = re.fullmatch(
                r"/publications/([^/]+)/",
                link,
            )
            if match:
                featured_slugs.add(match.group(1))
        self.assertEqual(featured_slugs, expected_featured_slugs)

    def test_research_page_renders_the_four_approved_themes(self):
        text = parse_generated_page(ROOT / "public/research/index.html").text
        for heading in (
            "FPGA-Based Computing and Acceleration",
            "RISC-V Customisation and System-on-Chip Design",
            "High-Level Synthesis and Microarchitecture Optimisation",
            "Hardware–Software Co-Design for Edge and Heterogeneous Computing",
        ):
            self.assertIn(heading, text)

    def test_supervision_page_renders_current_and_completed_students(self):
        page = ROOT / "public/teaching/uoa-cs-pg-teaching/index.html"
        text = parse_generated_page(page).text
        for detail in (
            "Yulin Fu (2025–Present)",
            "Tingjiang Tan (2026–Present)",
            "Taojingnan Wang (2025–2026, Graduated)",
            "Ziyuan Zhang (2025–2026, Graduated)",
            "Chenge Gao (2025–2026, Graduated)",
            "Cheng Cheng (2025–2026, Graduated)",
        ):
            self.assertIn(detail, text)
        self.assertNotIn("Chen Chen", text)


if __name__ == "__main__":
    unittest.main()

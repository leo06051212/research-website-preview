from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.migrate_legacy import (
    extract_authors,
    extract_bibtex,
    migrate_publication,
    migrate_talk,
    publication_type,
    read_legacy,
)

FIXTURES = Path(__file__).parent / "fixtures" / "legacy"


class LegacyMigrationTests(unittest.TestCase):
    def test_publication_without_bibtex_preserves_citation_authors(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "legacy.md"
            source.write_text(
                "---\n"
                'title: "Urban Aquatic Scene Expansion"\n'
                "date: 2024-03-22\n"
                "venue: MDPI\n"
                "citation: 'Yue Z, Lo C-Y, Wu R, Ma L, Sham C-W. Urban Aquatic Scene Expansion. Urban Science. 2024.'\n"
                "---\n\nAbstract.\n",
                encoding="utf-8",
            )
            bundle = migrate_publication(source, root / "output")
            index = (bundle / "index.md").read_text(encoding="utf-8")
            self.assertIn("- Z Yue", index)
            self.assertIn("- C-Y Lo", index)
            self.assertIn("- R Wu", index)
            self.assertIn("- me", index)
            self.assertIn("- C-W Sham", index)
            self.assertIn("citation: Yue Z, Lo C-Y, Wu R, Ma L, Sham C-W.", index)

    def test_extracts_bibtex_from_a_markdown_code_fence(self):
        body, bibtex = extract_bibtex(
            "Abstract.\n\nRecommended citation:\n```\n"
            "@inproceedings{x,\n"
            "  author={Ma, Longyu and Sham, Chiu Wing}, \n"
            "  title={Example}}\n```"
        )
        self.assertEqual("Abstract.", body)
        self.assertTrue(bibtex.startswith("@inproceedings"))
        self.assertNotIn("```", bibtex)
        self.assertTrue(all(line == line.rstrip() for line in bibtex.splitlines()))

    def test_extracts_multiline_quoted_bibtex_authors_and_maps_owner(self):
        bibtex = '''@InProceedings{example,
author="Wang, Shih-Shuan
and Chou, Hong-fu
and Ma, Sean Longyu"}'''
        self.assertEqual(
            ["Shih-Shuan Wang", "Hong-fu Chou", "me"],
            extract_authors(bibtex),
        )

    def test_maps_legacy_short_owner_name(self):
        self.assertEqual(["me"], extract_authors("@article{x, author={Ma, Longyu}}"))

    def test_maps_kernelvm_short_owner_name(self):
        self.assertEqual(["me"], extract_authors("@article{x, author={Ma, Sean}}"))

    def test_congress_venue_is_a_conference_publication(self):
        self.assertEqual(
            "paper-conference",
            publication_type("International Congress on Information Technology"),
        )

    def test_reads_legacy_single_quoted_value_with_an_unescaped_apostrophe(self):
        with TemporaryDirectory() as temp:
            source = Path(temp) / "legacy.md"
            source.write_text(
                "---\ntitle: Test\ncitation: 'a devil's vortex'\n---\n\nBody.\n",
                encoding="utf-8",
            )
            metadata, body = read_legacy(source)
            self.assertEqual("a devil's vortex", metadata["citation"])
            self.assertEqual("Body.", body)

    def test_publication_becomes_bundle_with_bibtex_and_doi(self):
        with TemporaryDirectory() as temp:
            output = Path(temp)
            bundle = migrate_publication(FIXTURES / "publication.md", output)
            index = (bundle / "index.md").read_text(encoding="utf-8")
            bib = (bundle / "cite.bib").read_text(encoding="utf-8")
            self.assertIn("publication_types:\n- paper-conference", index)
            self.assertIn("10.1109/MCSoC67473.2025.00122", index)
            self.assertIn("draft: true", index)
            self.assertIn("- Zongcheng Yue", index)
            self.assertIn("- me", index)
            self.assertIn("@INPROCEEDINGS", bib)
            self.assertFalse(index.endswith("\n\n"))

    def test_talk_preserves_event_and_location(self):
        with TemporaryDirectory() as temp:
            destination = migrate_talk(FIXTURES / "talk.md", Path(temp))
            text = destination.read_text(encoding="utf-8")
            self.assertIn("event_name: 2026 IEEE International Symposium", text)
            self.assertIn("location: Shanghai, China", text)
            self.assertIn("authors:\n- me", text)


if __name__ == "__main__":
    unittest.main()

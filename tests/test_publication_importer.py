from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest
from unittest.mock import patch
import yaml

import scripts.publication_importer as publication_importer
from scripts.publication_importer import normalize_source, process_request

FIXTURE = Path(__file__).parent / "fixtures" / "crossref-work.json"


class PublicationImporterTests(unittest.TestCase):
    def test_normalises_bare_doi_and_doi_url(self):
        bare = normalize_source("10.1109/MCSoC67473.2025.00122")
        url = normalize_source("https://doi.org/10.1109/MCSoC67473.2025.00122")
        self.assertEqual(bare.kind, "doi")
        self.assertEqual(bare.value, "10.1109/mcsoc67473.2025.00122")
        self.assertEqual(bare, url)

    def test_normalises_percent_encoded_doi_url(self):
        identifier = normalize_source(
            "https://doi.org/10.1109%2FMCSoC67473.2025.00122"
        )
        self.assertEqual(identifier.kind, "doi")
        self.assertEqual(identifier.value, "10.1109/mcsoc67473.2025.00122")

    def test_extracts_ieee_document_number(self):
        identifier = normalize_source("https://ieeexplore.ieee.org/document/11310955")
        self.assertEqual(identifier.kind, "ieee")
        self.assertEqual(identifier.value, "11310955")

    def test_valid_doi_creates_draft_bundle_and_updates_request(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "paper.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "publication_type: paper-conference\n"
                "featured: true\nstatus: pending\n",
                encoding="utf-8",
            )
            result = process_request(request, root, lambda _: fixture)
            index = (root / result.result_path / "index.md").read_text(encoding="utf-8")
            updated = yaml.safe_load(request.read_text(encoding="utf-8"))
            self.assertIn("draft: true", index)
            self.assertIn("featured: true", index)
            self.assertIn("- me", index)
            self.assertTrue((root / result.result_path / "cite.bib").is_file())
            self.assertIn(
                "Sean Longyu Ma",
                (root / result.result_path / "cite.bib").read_text(encoding="utf-8"),
            )
            self.assertEqual(updated["status"], "processed")

    def test_duplicate_doi_does_not_overwrite_publication(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            existing = root / "content/publications/existing"
            existing.mkdir(parents=True)
            existing.joinpath("index.md").write_text(
                "---\nhugoblox:\n  ids:\n    doi: 10.1109/mcsoc67473.2025.00122\n---\n",
                encoding="utf-8",
            )
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "duplicate.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "publication_type: paper-conference\nstatus: pending\n",
                encoding="utf-8",
            )
            result = process_request(request, root, lambda _: fixture)
            self.assertEqual(result.status, "duplicate")
            self.assertEqual(len(list((root / "content/publications").glob("*/index.md"))), 1)
            updated = yaml.safe_load(request.read_text(encoding="utf-8"))
            self.assertEqual(updated["result_path"], "content/publications/existing")

    def test_invalid_identifier_is_recorded_as_failed(self):
        with self.assertRaisesRegex(ValueError, "DOI or IEEE Xplore"):
            normalize_source("not a publication identifier")

    def test_metadata_failure_is_written_back_to_request(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "failed.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "publication_type: paper-conference\nstatus: pending\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "service unavailable"):
                process_request(
                    request,
                    root,
                    lambda _: (_ for _ in ()).throw(RuntimeError("service unavailable")),
                )
            updated = yaml.safe_load(request.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "failed")
            self.assertEqual(updated["error"], "service unavailable")

    def test_ieee_api_key_is_not_written_to_failed_request(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "ieee.yml"
            request.write_text(
                "source: https://ieeexplore.ieee.org/document/11310955\n"
                "status: pending\n",
                encoding="utf-8",
            )
            secret = "do-not-persist-this-key"

            def failing_fetch(url):
                raise RuntimeError(f"service rejected {url}")

            with patch.dict(os.environ, {"IEEE_API_KEY": secret}):
                with self.assertRaisesRegex(RuntimeError, "IEEE metadata request failed"):
                    process_request(request, root, failing_fetch)

            updated_text = request.read_text(encoding="utf-8")
            self.assertNotIn(secret, updated_text)

    def test_slug_collision_does_not_overwrite_existing_bundle(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["DOI"] = "10.1109/different.2025.1"
        with TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = (
                root
                / "content/publications"
                / "2025-adaptive-gradual-quantization-with-a-custom-risc-v-simd-accelerator"
            )
            bundle.mkdir(parents=True)
            bundle.joinpath("index.md").write_text("original index\n", encoding="utf-8")
            bundle.joinpath("cite.bib").write_text("original citation\n", encoding="utf-8")
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "collision.yml"
            request.write_text(
                "source: 10.1109/different.2025.1\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(FileExistsError, "bundle already exists"):
                process_request(request, root, lambda _: fixture)

            self.assertEqual(bundle.joinpath("index.md").read_text(), "original index\n")
            self.assertEqual(bundle.joinpath("cite.bib").read_text(), "original citation\n")
            self.assertEqual(
                yaml.safe_load(request.read_text(encoding="utf-8"))["status"], "failed"
            )

    def test_invalid_empty_author_does_not_leave_partial_bundle(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["author"] = [{}]
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "invalid-author.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "missing title, authors"):
                process_request(request, root, lambda _: fixture)

            publications = root / "content/publications"
            self.assertFalse(publications.exists())

    def test_bundle_write_failure_does_not_leave_partial_bundle(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "write-failure.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )
            real_atomic_write = publication_importer.atomic_write

            def fail_citation(path, text):
                if path.name == "cite.bib":
                    raise OSError("disk full")
                real_atomic_write(path, text)

            with patch.object(publication_importer, "atomic_write", fail_citation):
                with self.assertRaisesRegex(OSError, "disk full"):
                    process_request(request, root, lambda _: fixture)

            bundles = list((root / "content/publications").glob("*/index.md"))
            self.assertEqual(bundles, [])

    def test_processed_request_is_idempotent(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "done.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "status: processed\n"
                "result_path: content/publications/already-created\n",
                encoding="utf-8",
            )

            def unexpected_fetch(_):
                self.fail("a processed request must not fetch metadata")

            result = process_request(request, root, unexpected_fetch)

            self.assertEqual(result.status, "processed")
            self.assertEqual(
                result.result_path, "content/publications/already-created"
            )

    def test_crossref_doi_mismatch_is_failed_without_output(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "mismatch.yml"
            request.write_text(
                "source: 10.1109/different.2025.1\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not match requested DOI"):
                process_request(request, root, lambda _: fixture)

            self.assertFalse((root / "content/publications").exists())
            self.assertEqual(
                yaml.safe_load(request.read_text(encoding="utf-8"))["status"], "failed"
            )

    def test_similar_doi_prefix_is_not_treated_as_duplicate(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["DOI"] = "10.1109/example"
        with TemporaryDirectory() as temp:
            root = Path(temp)
            existing = root / "content/publications/existing"
            existing.mkdir(parents=True)
            existing.joinpath("index.md").write_text(
                "---\nhugoblox:\n  ids:\n    doi: 10.1109/example.extended\n---\n",
                encoding="utf-8",
            )
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "similar.yml"
            request.write_text(
                "source: 10.1109/example\nstatus: pending\n",
                encoding="utf-8",
            )

            result = process_request(request, root, lambda _: fixture)

            self.assertEqual(result.status, "processed")
            self.assertNotEqual(result.result_path, "content/publications/existing")

    def test_ieee_document_resolves_to_doi_with_api_key(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        requested_urls = []

        def fetch(url):
            requested_urls.append(url)
            if "ieeexploreapi.ieee.org" in url:
                return {"articles": [{"doi": fixture["message"]["DOI"]}]}
            return fixture

        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "ieee.yml"
            request.write_text(
                "source: https://ieeexplore.ieee.org/document/11310955\n"
                "status: pending\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"IEEE_API_KEY": "fixture-key"}, clear=True):
                result = process_request(request, root, fetch)

            self.assertEqual(result.status, "processed")
            self.assertEqual(len(requested_urls), 2)
            self.assertIn("article_number=11310955", requested_urls[0])
            self.assertIn("api.crossref.org/works/", requested_urls[1])

    def test_ieee_document_without_api_key_preserves_readable_error(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "ieee-no-key.yml"
            request.write_text(
                "source: https://ieeexplore.ieee.org/document/11310955\n"
                "status: pending\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "configure IEEE_API_KEY"):
                    process_request(request, root, lambda _: self.fail("unexpected fetch"))

            updated = yaml.safe_load(request.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "failed")
            self.assertIn("configure IEEE_API_KEY", updated["error"])

    def test_missing_abstract_and_owner_links_are_supported(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"].pop("abstract")
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "links.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "status: pending\n"
                "pdf_url: https://example.test/paper.pdf\n"
                "code_url: https://example.test/code\n"
                "dataset_url: https://example.test/data\n"
                "slides_url: https://example.test/slides\n",
                encoding="utf-8",
            )

            result = process_request(request, root, lambda _: fixture)
            frontmatter = yaml.safe_load(
                (root / result.result_path / "index.md")
                .read_text(encoding="utf-8")
                .split("---", 2)[1]
            )

            self.assertEqual(frontmatter["abstract"], "")
            self.assertEqual(
                [link["type"] for link in frontmatter["links"]],
                ["pdf", "code", "dataset", "slides", "source"],
            )


if __name__ == "__main__":
    unittest.main()

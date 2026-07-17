from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import re
import subprocess
import sys
import unittest
from unittest.mock import patch
import yaml

import scripts.publication_importer as publication_importer
from scripts.publication_importer import (
    main,
    normalize_source,
    process_request,
    record_from_crossref,
    render_bibtex,
)

FIXTURE = Path(__file__).parent / "fixtures" / "crossref-work.json"


def parse_generated_bibtex(text):
    header = re.fullmatch(r"@(\w+)\{([^,]+),", text.splitlines()[0])
    if not header:
        raise AssertionError("invalid BibTeX header")
    fields = {}
    for line in text.splitlines()[1:-1]:
        match = re.fullmatch(r"  ([a-z]+) = \{(.*)\},", line)
        if not match:
            raise AssertionError(f"invalid BibTeX field: {line}")
        value = match.group(2)
        depth = 0
        escaped = False
        for character in value:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth < 0:
                    raise AssertionError("unbalanced BibTeX value")
        if depth:
            raise AssertionError("unbalanced BibTeX value")
        replacements = {
            r"\textbackslash{}": "\\",
            r"\textasciitilde{}": "~",
            r"\textasciicircum{}": "^",
            r"\%": "%",
            r"\&": "&",
            r"\_": "_",
            r"\#": "#",
            r"\$": "$",
            r"\{": "{",
            r"\}": "}",
        }
        for escaped_value, original in replacements.items():
            value = value.replace(escaped_value, original)
        fields[match.group(1)] = value
    if text.splitlines()[-1] != "}":
        raise AssertionError("invalid BibTeX closing brace")
    return header.group(1), header.group(2), fields


def create_directory_link(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError as error:
        if os.name != "nt":
            raise unittest.SkipTest(f"directory symlinks unavailable: {error}")
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if created.returncode:
        raise unittest.SkipTest(
            f"directory symlinks and junctions unavailable: {created.stderr.strip()}"
        )


def remove_directory_link(link):
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        os.rmdir(link)


class PublicationImporterTests(unittest.TestCase):
    def test_remove_directory_link_removes_platform_directory_link(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            create_directory_link(link, target)

            remove_directory_link(link)

            self.assertFalse(link.exists())
            self.assertTrue(target.exists())

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

    def test_preserves_complete_legacy_doi_suffix(self):
        source = "10.1002/1097-4679(199601)52:1<15::AID-JCLP3>3.0.CO;2-3"
        identifier = normalize_source(source)
        self.assertEqual(identifier.kind, "doi")
        self.assertEqual(identifier.value, source.lower())

    def test_doi_url_ignores_url_query_and_fragment(self):
        identifier = normalize_source(
            "https://doi.org/10.1002%2F1097-4679(199601)52%3A1%3C15%3A%3AAID-JCLP3%3E3.0.CO%3B2-3"
            "?utm_source=fixture#details"
        )
        self.assertEqual(
            identifier.value,
            "10.1002/1097-4679(199601)52:1<15::aid-jclp3>3.0.co;2-3",
        )

    def test_rejects_doi_on_hostile_resolver_hostname(self):
        with self.assertRaisesRegex(ValueError, "DOI or IEEE Xplore"):
            normalize_source("https://doi.org.evil.example/10.1109/example")

    def test_rejects_ieee_hostname_embedded_in_hostile_url(self):
        with self.assertRaisesRegex(ValueError, "DOI or IEEE Xplore"):
            normalize_source(
                "https://evil.example/ieeexplore.ieee.org/document/11310955"
            )

    def test_rejects_trailing_text_after_bare_doi(self):
        with self.assertRaisesRegex(ValueError, "DOI or IEEE Xplore"):
            normalize_source("10.1109/example trailing junk")

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

    def test_duplicate_scan_ignores_child_bundle_junction_outside_repository(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            publication_dir = root / "content/publications"
            request_dir = root / "data/publication-imports"
            publication_dir.mkdir(parents=True)
            request_dir.mkdir(parents=True)
            outside = base / "outside-bundle"
            outside.mkdir()
            external_index = (
                "---\nhugoblox:\n  ids:\n"
                "    doi: 10.1109/mcsoc67473.2025.00122\n---\nexternal\n"
            )
            outside.joinpath("index.md").write_text(external_index, encoding="utf-8")
            linked = publication_dir / "linked"
            create_directory_link(linked, outside)
            request = request_dir / "paper.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "publication_type: paper-conference\nstatus: pending\n",
                encoding="utf-8",
            )

            try:
                result = process_request(request, root, lambda _: fixture)
                self.assertEqual(result.status, "processed")
                self.assertNotEqual(result.result_path, "content/publications/linked")
                self.assertEqual(
                    outside.joinpath("index.md").read_text(encoding="utf-8"),
                    external_index,
                )
            finally:
                remove_directory_link(linked)

    def test_duplicate_scan_ignores_external_index_link_with_junction_fallback(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            bundle = root / "content/publications/linked-index"
            request_dir = root / "data/publication-imports"
            bundle.mkdir(parents=True)
            request_dir.mkdir(parents=True)
            outside_index = base / "external-index.md"
            external_index = (
                "---\nhugoblox:\n  ids:\n"
                "    doi: 10.1109/mcsoc67473.2025.00122\n---\nexternal\n"
            )
            outside_index.write_text(external_index, encoding="utf-8")
            linked_index = bundle / "index.md"
            bundle_is_link = False
            try:
                linked_index.symlink_to(outside_index)
            except OSError:
                os.rmdir(bundle)
                outside_bundle = base / "external-bundle"
                outside_bundle.mkdir()
                outside_index = outside_bundle / "index.md"
                outside_index.write_text(external_index, encoding="utf-8")
                create_directory_link(bundle, outside_bundle)
                bundle_is_link = True
            request = request_dir / "paper.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "publication_type: paper-conference\nstatus: pending\n",
                encoding="utf-8",
            )

            try:
                result = process_request(request, root, lambda _: fixture)

                self.assertEqual(result.status, "processed")
                self.assertEqual(outside_index.read_text(encoding="utf-8"), external_index)
            finally:
                if bundle_is_link:
                    remove_directory_link(bundle)

    def test_duplicate_scan_skips_unreadable_non_utf8_and_malformed_indexes(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for bad_kind in ("unreadable", "non-utf8", "malformed"):
            with self.subTest(bad_kind=bad_kind), TemporaryDirectory() as temp:
                root = Path(temp)
                bad_index = root / "content/publications/bad/index.md"
                bad_index.parent.mkdir(parents=True)
                if bad_kind == "unreadable":
                    bad_index.mkdir()
                elif bad_kind == "non-utf8":
                    bad_index.write_bytes(b"\xff\xfe\x00")
                else:
                    bad_index.write_text("---\ntitle: [unterminated\n---\n")
                request_dir = root / "data/publication-imports"
                request_dir.mkdir(parents=True)
                request = request_dir / "paper.yml"
                request.write_text(
                    "source: 10.1109/MCSoC67473.2025.00122\n"
                    "publication_type: paper-conference\nstatus: pending\n",
                    encoding="utf-8",
                )

                result = process_request(request, root, lambda _: fixture)

                self.assertEqual(result.status, "processed")

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

    def test_invalid_author_shape_does_not_leave_partial_bundle(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["author"] = [{"given": []}]
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "invalid-author.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "author names must be strings"):
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

    def test_processed_status_write_failure_rolls_back_new_bundle(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "status-write-failure.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )
            real_save_request = publication_importer.save_request

            def fail_processed_status(path, data):
                if data.get("status") == "processed":
                    raise OSError("request disk full")
                real_save_request(path, data)

            with patch.object(
                publication_importer, "save_request", fail_processed_status
            ):
                with self.assertRaisesRegex(OSError, "request disk full"):
                    process_request(request, root, lambda _: fixture)

            self.assertEqual(
                list((root / "content/publications").glob("*/index.md")), []
            )
            updated = yaml.safe_load(request.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "failed")
            self.assertEqual(updated["error"], "request disk full")
            self.assertNotIn("processed_at", updated)
            self.assertNotIn("result_path", updated)

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

    def test_rejects_request_outside_publication_import_directory(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            root.mkdir()
            (root / "data/publication-imports").mkdir(parents=True)
            outside = base / "outside.yml"
            original = "source: 10.1109/example\nstatus: pending\n"
            outside.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "publication-imports"):
                process_request(outside, root, lambda _: self.fail("unexpected fetch"))

            self.assertEqual(outside.read_text(encoding="utf-8"), original)

    def test_rejects_request_path_containing_parent_traversal(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "traversal.yml"
            request.write_text(
                "source: 10.1109/example\nstatus: pending\n", encoding="utf-8"
            )
            traversing_path = request_dir / ".." / "publication-imports" / request.name

            with self.assertRaisesRegex(ValueError, "parent traversal"):
                process_request(
                    traversing_path, root, lambda _: self.fail("unexpected fetch")
                )

    def test_rejects_request_symlink_escaping_import_directory(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            outside_directory = base / "outside"
            outside_directory.mkdir()
            outside = outside_directory / "outside.yml"
            original = "source: 10.1109/example\nstatus: pending\n"
            outside.write_text(original, encoding="utf-8")
            link = request_dir / "linked.yml"
            try:
                link.symlink_to(outside)
            except OSError as error:
                if os.name != "nt":
                    self.skipTest(f"file symlinks unavailable: {error}")
                junction = request_dir / "escape"
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(junction), str(outside_directory)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if created.returncode:
                    self.skipTest(
                        f"symlinks and junctions unavailable: {created.stderr.strip()}"
                    )
                link = junction / outside.name

            try:
                with self.assertRaisesRegex(ValueError, "publication-imports"):
                    process_request(link, root, lambda _: self.fail("unexpected fetch"))
            finally:
                if "junction" in locals() and junction.exists():
                    remove_directory_link(junction)

            self.assertEqual(outside.read_text(encoding="utf-8"), original)

    def test_rejects_import_directory_junction_outside_repository(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            (root / "data").mkdir(parents=True)
            outside = base / "external-imports"
            outside.mkdir()
            import_link = root / "data/publication-imports"
            create_directory_link(import_link, outside)
            request = import_link / "request.yml"
            original = "source: 10.1109/example\nstatus: pending\n"
            request.write_text(original, encoding="utf-8")

            try:
                with self.assertRaisesRegex(ValueError, "inside the repository"):
                    process_request(request, root, lambda _: self.fail("unexpected fetch"))
                self.assertEqual(request.read_text(encoding="utf-8"), original)
            finally:
                remove_directory_link(import_link)

    def test_rejects_publication_directory_junction_outside_repository(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "request.yml"
            request.write_text(
                "source: 10.1109/example\nstatus: pending\n", encoding="utf-8"
            )
            (root / "content").mkdir()
            outside = base / "external-publications"
            outside.mkdir()
            publication_link = root / "content/publications"
            create_directory_link(publication_link, outside)

            try:
                with self.assertRaisesRegex(ValueError, "[Pp]ublication directory"):
                    process_request(request, root, lambda _: self.fail("unexpected fetch"))
                self.assertEqual(list(outside.iterdir()), [])
            finally:
                remove_directory_link(publication_link)

    def test_citation_sync_rejects_child_bundle_junction_without_external_writes(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            publication_dir = root / "content/publications"
            publication_dir.mkdir(parents=True)
            outside = base / "outside-bundle"
            outside.mkdir()
            index_text = (
                "---\npublication_importer: {managed_citation: true}\n"
                "title: External title\nauthors: [me]\n"
                "date: '2026-01-02T00:00:00Z'\n"
                "publication_types: [article-journal]\n"
                "publication: {name: External Journal}\n"
                "hugoblox: {ids: {doi: 10.1109/external}}\n"
                "draft: false\nrequires_correction: false\n---\n"
            )
            cite_text = "@article{external,\n  title = {External original},\n}\n"
            outside.joinpath("index.md").write_text(index_text, encoding="utf-8")
            outside.joinpath("cite.bib").write_text(cite_text, encoding="utf-8")
            linked = publication_dir / "linked"
            create_directory_link(linked, outside)

            try:
                with self.assertRaisesRegex(RuntimeError, "inside the repository"):
                    publication_importer.sync_imported_citations(root)
                self.assertEqual(outside.joinpath("index.md").read_text(), index_text)
                self.assertEqual(outside.joinpath("cite.bib").read_text(), cite_text)
            finally:
                remove_directory_link(linked)

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

    def test_malformed_ieee_shapes_use_stable_key_free_error(self):
        malformed_responses = [
            [],
            {"articles": [None]},
            {"articles": [{"doi": []}]},
        ]
        for position, malformed in enumerate(malformed_responses):
            with self.subTest(position=position), TemporaryDirectory() as temp:
                root = Path(temp)
                request_dir = root / "data/publication-imports"
                request_dir.mkdir(parents=True)
                request = request_dir / "malformed-ieee.yml"
                request.write_text(
                    "source: https://ieeexplore.ieee.org/document/11310955\n"
                    "status: pending\n",
                    encoding="utf-8",
                )
                secret = "shape-test-secret"
                with patch.dict(os.environ, {"IEEE_API_KEY": secret}, clear=True):
                    with self.assertRaisesRegex(
                        ValueError, "IEEE metadata response is invalid"
                    ):
                        process_request(request, root, lambda _: malformed)

                updated = request.read_text(encoding="utf-8")
                self.assertIn("IEEE metadata response is invalid", updated)
                self.assertNotIn(secret, updated)

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

    def test_rejects_non_mapping_request_without_rewriting_it(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "list.yml"
            original = "- source: 10.1109/example\n"
            request.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "YAML mapping"):
                process_request(request, root, lambda _: self.fail("unexpected fetch"))

            self.assertEqual(request.read_text(encoding="utf-8"), original)

    def test_rejects_string_featured_instead_of_coercing_it(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "featured.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "featured: 'false'\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "featured must be a boolean"):
                process_request(request, root, lambda _: fixture)

            self.assertFalse((root / "content/publications").exists())
            updated = yaml.safe_load(request.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "failed")

    def test_rejects_unsupported_publication_type(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "type.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\n"
                "publication_type: thesis\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "publication_type must be one of"):
                process_request(request, root, lambda _: fixture)

            self.assertFalse((root / "content/publications").exists())

    def test_year_only_date_is_not_fabricated_as_january_first(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["published-print"] = {"date-parts": [[2025]]}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "year-only.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            result = process_request(request, root, lambda _: fixture)
            frontmatter = yaml.safe_load(
                (root / result.result_path / "index.md")
                .read_text(encoding="utf-8")
                .split("---", 2)[1]
            )

            self.assertNotIn("date", frontmatter)
            self.assertEqual(frontmatter["publication_date_parts"], [2025])
            self.assertEqual(frontmatter["date_precision"], "year")
            self.assertTrue(frontmatter["requires_correction"])
            self.assertTrue(frontmatter["draft"])

    def test_invalid_crossref_calendar_date_fails_without_output(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["published-print"] = {
            "date-parts": [[2025, 2, 30]]
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "bad-date.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "publication date"):
                process_request(request, root, lambda _: fixture)

            self.assertFalse((root / "content/publications").exists())

    def test_missing_core_metadata_creates_reviewable_unfabricated_draft(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["title"] = []
        fixture["message"]["author"] = []
        fixture["message"].pop("published-print")
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "incomplete.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            result = process_request(request, root, lambda _: fixture)
            frontmatter = yaml.safe_load(
                (root / result.result_path / "index.md")
                .read_text(encoding="utf-8")
                .split("---", 2)[1]
            )

            self.assertNotIn("title", frontmatter)
            self.assertNotIn("authors", frontmatter)
            self.assertNotIn("date", frontmatter)
            self.assertTrue(frontmatter["requires_correction"])
            self.assertGreaterEqual(len(frontmatter["correction_reasons"]), 3)
            self.assertTrue(frontmatter["draft"])

    def test_bibtex_reserved_characters_round_trip_semantically(self):
        title = r"FPGA_50% & {robust #1 $gain$ ~ ^ C:\path"
        author = r"A. Researcher & Collaborator"
        record = {
            "title": title,
            "authors": [author, "me"],
            "publication_date_parts": [2025, 6, 3],
            "publication_types": ["article-journal"],
            "publication": {
                "name": r"Journal_50% & Systems",
                "volume": "12",
                "issue": "3",
                "pages": "10-20",
                "article_number": "e100_1",
                "publisher": "IEEE & ACM",
            },
            "hugoblox": {"ids": {"doi": "10.1109/example_1"}},
        }

        bibtex = render_bibtex(record)
        for escaped in [
            r"\_",
            r"\%",
            r"\&",
            r"\{",
            r"\#",
            r"\$",
            r"\textasciitilde{}",
            r"\textasciicircum{}",
            r"\textbackslash{}",
        ]:
            self.assertIn(escaped, bibtex)
        entry_type, _, fields = parse_generated_bibtex(bibtex)

        self.assertEqual(entry_type, "article")
        self.assertEqual(fields["title"], title)
        self.assertEqual(fields["author"], f"{author} and Sean Longyu Ma")
        self.assertEqual(fields["journal"], r"Journal_50% & Systems")
        self.assertEqual(fields["eid"], "e100_1")
        self.assertEqual(fields["publisher"], "IEEE & ACM")

    def test_bibtex_maps_every_allowed_publication_type(self):
        expected = {
            "article-journal": ("article", "journal"),
            "paper-conference": ("inproceedings", "booktitle"),
            "chapter": ("incollection", "booktitle"),
            "report": ("techreport", "institution"),
            "manuscript": ("unpublished", "note"),
        }
        for publication_type, (expected_entry, venue_field) in expected.items():
            with self.subTest(publication_type=publication_type):
                record = {
                    "title": "A safe title",
                    "authors": ["me"],
                    "publication_date_parts": [2025],
                    "publication_types": [publication_type],
                    "publication": {
                        "name": "Fixture venue",
                        "volume": "7",
                        "issue": "2",
                        "pages": "11-19",
                        "article_number": "e42",
                        "publisher": "Fixture Press",
                    },
                    "hugoblox": {"ids": {"doi": "10.1109/example"}},
                }

                entry_type, _, fields = parse_generated_bibtex(
                    render_bibtex(record)
                )

                self.assertEqual(entry_type, expected_entry)
                self.assertEqual(fields[venue_field], "Fixture venue")
                self.assertEqual(fields["volume"], "7")
                self.assertEqual(fields["number"], "2")
                self.assertEqual(fields["pages"], "11-19")

    def test_maps_crossref_publisher_and_article_number(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"].update(
            publisher="IEEE",
            volume="18",
            issue="4",
            **{"article-number": "e00122"},
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "publisher.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            result = process_request(request, root, lambda _: fixture)
            frontmatter = yaml.safe_load(
                (root / result.result_path / "index.md")
                .read_text(encoding="utf-8")
                .split("---", 2)[1]
            )
            citation = parse_generated_bibtex(
                (root / result.result_path / "cite.bib").read_text(encoding="utf-8")
            )[2]

            self.assertEqual(frontmatter["publication"]["publisher"], "IEEE")
            self.assertEqual(frontmatter["publication"]["article_number"], "e00122")
            self.assertEqual(citation["publisher"], "IEEE")
            self.assertEqual(citation["eid"], "e00122")

    def test_rejects_non_scalar_crossref_publication_fields(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["publisher"] = ["not", "a", "scalar"]
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "bad-publisher.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "publisher must be a scalar"):
                process_request(request, root, lambda _: fixture)

    def test_rejects_non_mapping_crossref_message(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "bad-message.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "message must be a mapping"):
                process_request(request, root, lambda _: {"message": []})

            self.assertFalse((root / "content/publications").exists())

    def test_rejects_non_string_crossref_abstract(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["abstract"] = ["not", "a", "string"]
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "bad-abstract.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "abstract must be a string"):
                process_request(request, root, lambda _: fixture)

    def test_record_mapping_rejects_non_string_crossref_doi(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["message"]
        fixture["DOI"] = ["10.1109/example"]

        with self.assertRaisesRegex(ValueError, "DOI must be a string"):
            record_from_crossref(fixture, {})

    def test_all_pending_continues_after_malformed_yaml(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            malformed = request_dir / "01-malformed.yml"
            malformed.write_text("source: [unterminated\n", encoding="utf-8")
            later = request_dir / "02-later.yml"
            later.write_text(
                "source: 10.1109/example\nstatus: processed\n"
                "result_path: content/publications/existing\n",
                encoding="utf-8",
            )
            visited = []
            real_process_request = publication_importer.process_request

            def recording_process_request(path, repository_root):
                visited.append(path.name)
                return real_process_request(path, repository_root)

            argv = [
                "publication_importer.py",
                "--repo-root",
                str(root),
                "--all-pending",
            ]
            with patch.object(sys, "argv", argv), patch.object(
                publication_importer, "process_request", recording_process_request
            ), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(SystemExit, "1"):
                    main()

            self.assertEqual(visited, ["01-malformed.yml", "02-later.yml"])

    def test_cli_requires_exactly_one_processing_mode(self):
        with patch.object(sys, "argv", ["publication_importer.py"]), redirect_stderr(
            io.StringIO()
        ):
            with self.assertRaisesRegex(SystemExit, "2"):
                main()

    def test_all_pending_syncs_corrected_imported_citation_end_to_end(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["message"]["title"] = []
        fixture["message"]["author"] = []
        fixture["message"].pop("published-print")
        with TemporaryDirectory() as temp:
            root = Path(temp)
            request_dir = root / "data/publication-imports"
            request_dir.mkdir(parents=True)
            request = request_dir / "corrected.yml"
            request.write_text(
                "source: 10.1109/MCSoC67473.2025.00122\nstatus: pending\n",
                encoding="utf-8",
            )
            result = process_request(request, root, lambda _: fixture)
            bundle = root / result.result_path
            index = bundle / "index.md"
            parts = index.read_text(encoding="utf-8").split("---", 2)
            frontmatter = yaml.safe_load(parts[1])
            self.assertEqual(
                frontmatter["publication_importer"]["managed_citation"], True
            )

            frontmatter.update(
                title="Owner Corrected Title & FPGA_Design",
                authors=["me", "Corrected Collaborator"],
                date="2026-03-14T00:00:00Z",
                publication_types=["report"],
                draft=False,
                requires_correction=False,
            )
            frontmatter["publication"]["name"] = "Corrected Research Institute"
            index.write_text(
                "---\n"
                + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
                + "---"
                + parts[2],
                encoding="utf-8",
            )

            argv = [
                "publication_importer.py",
                "--repo-root",
                str(root),
                "--all-pending",
            ]
            with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(SystemExit, "0"):
                    main()

            entry_type, _, fields = parse_generated_bibtex(
                (bundle / "cite.bib").read_text(encoding="utf-8")
            )
            self.assertEqual(entry_type, "techreport")
            self.assertEqual(fields["title"], "Owner Corrected Title & FPGA_Design")
            self.assertEqual(
                fields["author"], "Sean Longyu Ma and Corrected Collaborator"
            )
            self.assertEqual(fields["year"], "2026")
            self.assertEqual(fields["institution"], "Corrected Research Institute")
            self.assertEqual(list(bundle.glob(".citation-sync-*")), [])

    def test_citation_sync_does_not_touch_legacy_bundle(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "content/publications/legacy"
            bundle.mkdir(parents=True)
            index_text = (
                "---\ntitle: Legacy publication\nauthors: [me]\n"
                "date: '2020-01-01T00:00:00Z'\n"
                "publication_types: [article-journal]\n"
                "publication: {name: Legacy Journal}\n"
                "hugoblox: {ids: {doi: 10.1109/legacy}}\n---\n"
            )
            citation_text = "@article{legacy,\n  title = {Do not replace me},\n}\n"
            bundle.joinpath("index.md").write_text(index_text, encoding="utf-8")
            bundle.joinpath("cite.bib").write_text(citation_text, encoding="utf-8")

            publication_importer.sync_imported_citations(root)

            self.assertEqual(bundle.joinpath("index.md").read_text(), index_text)
            self.assertEqual(bundle.joinpath("cite.bib").read_text(), citation_text)

    def test_incomplete_managed_record_is_forced_back_to_draft_by_sync(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "content/publications/managed"
            bundle.mkdir(parents=True)
            bundle.joinpath("index.md").write_text(
                "---\n"
                "publication_importer: {managed_citation: true}\n"
                "publication_types: [article-journal]\n"
                "publication: {name: Fixture Journal}\n"
                "hugoblox: {ids: {doi: 10.1109/example}}\n"
                "draft: false\nrequires_correction: false\n"
                "---\n",
                encoding="utf-8",
            )

            publication_importer.sync_imported_citations(root)

            frontmatter = yaml.safe_load(
                bundle.joinpath("index.md").read_text().split("---", 2)[1]
            )
            self.assertTrue(frontmatter["draft"])
            self.assertTrue(frontmatter["requires_correction"])
            self.assertGreaterEqual(len(frontmatter["correction_reasons"]), 3)

    def test_managed_record_still_marked_for_correction_cannot_publish(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "content/publications/managed"
            bundle.mkdir(parents=True)
            bundle.joinpath("index.md").write_text(
                "---\n"
                "publication_importer: {managed_citation: true}\n"
                "title: Complete title\nauthors: [me]\n"
                "date: '2026-01-02T00:00:00Z'\n"
                "publication_types: [article-journal]\n"
                "publication: {name: Fixture Journal}\n"
                "hugoblox: {ids: {doi: 10.1109/example}}\n"
                "draft: false\nrequires_correction: true\n"
                "correction_reasons: [Owner review still required]\n"
                "---\n",
                encoding="utf-8",
            )

            publication_importer.sync_imported_citations(root)

            frontmatter = yaml.safe_load(
                bundle.joinpath("index.md").read_text().split("---", 2)[1]
            )
            self.assertTrue(frontmatter["draft"])
            self.assertTrue(frontmatter["requires_correction"])

    def test_managed_citation_requires_a_doi_not_an_ieee_document_url(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "content/publications/managed"
            bundle.mkdir(parents=True)
            bundle.joinpath("index.md").write_text(
                "---\n"
                "publication_importer: {managed_citation: true}\n"
                "title: Complete title\nauthors: [me]\n"
                "date: '2026-01-02T00:00:00Z'\n"
                "publication_types: [article-journal]\n"
                "publication: {name: Fixture Journal}\n"
                "hugoblox: {ids: {doi: 'https://ieeexplore.ieee.org/document/11310955'}}\n"
                "draft: false\nrequires_correction: false\n"
                "---\n",
                encoding="utf-8",
            )

            publication_importer.sync_imported_citations(root)

            frontmatter = yaml.safe_load(
                bundle.joinpath("index.md").read_text().split("---", 2)[1]
            )
            self.assertTrue(frontmatter["draft"])
            self.assertTrue(frontmatter["requires_correction"])
            self.assertIn("DOI", " ".join(frontmatter["correction_reasons"]))

    def test_unhashable_publication_type_shapes_are_isolated_and_forced_draft(self):
        invalid_values = [{"bad": "type"}, ["bad"]]
        for position, invalid_value in enumerate(invalid_values):
            with self.subTest(position=position), TemporaryDirectory() as temp:
                root = Path(temp)
                bad = root / "content/publications/00-bad"
                good = root / "content/publications/99-good"
                bad.mkdir(parents=True)
                good.mkdir(parents=True)
                bad_frontmatter = {
                    "publication_importer": {"managed_citation": True},
                    "title": "Bad record",
                    "authors": ["me"],
                    "date": "2026-01-02T00:00:00Z",
                    "publication_types": [invalid_value],
                    "publication": {"name": "Bad Venue"},
                    "hugoblox": {"ids": {"doi": "10.1109/bad"}},
                    "draft": False,
                    "requires_correction": False,
                }
                bad.joinpath("index.md").write_text(
                    "---\n"
                    + yaml.safe_dump(bad_frontmatter, sort_keys=False)
                    + "---\n",
                    encoding="utf-8",
                )
                good.joinpath("index.md").write_text(
                    "---\npublication_importer: {managed_citation: true}\n"
                    "title: Later valid title\nauthors: [me]\n"
                    "date: '2026-02-03T00:00:00Z'\n"
                    "publication_types: [article-journal]\n"
                    "publication: {name: Later Journal}\n"
                    "hugoblox: {ids: {doi: 10.1109/later}}\n"
                    "draft: false\nrequires_correction: false\n---\n",
                    encoding="utf-8",
                )
                good.joinpath("cite.bib").write_text("stale\n", encoding="utf-8")

                publication_importer.sync_imported_citations(root)

                updated_bad = yaml.safe_load(
                    bad.joinpath("index.md").read_text().split("---", 2)[1]
                )
                self.assertTrue(updated_bad["draft"])
                self.assertTrue(updated_bad["requires_correction"])
                later_fields = parse_generated_bibtex(
                    good.joinpath("cite.bib").read_text()
                )[2]
                self.assertEqual(later_fields["title"], "Later valid title")

    def test_malformed_unmarked_legacy_does_not_block_later_managed_sync(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = root / "content/publications/00-legacy"
            managed = root / "content/publications/99-managed"
            legacy.mkdir(parents=True)
            managed.mkdir(parents=True)
            legacy_text = "---\ntitle: [unterminated\n---\nlegacy body\n"
            legacy_cite = "legacy citation bytes\n"
            legacy.joinpath("index.md").write_text(legacy_text, encoding="utf-8")
            legacy.joinpath("cite.bib").write_text(legacy_cite, encoding="utf-8")
            managed.joinpath("index.md").write_text(
                "---\npublication_importer: {managed_citation: true}\n"
                "title: Managed after legacy\nauthors: [me]\n"
                "date: '2026-03-04T00:00:00Z'\n"
                "publication_types: [article-journal]\n"
                "publication: {name: Managed Journal}\n"
                "hugoblox: {ids: {doi: 10.1109/managed}}\n"
                "draft: false\nrequires_correction: false\n---\n",
                encoding="utf-8",
            )
            managed.joinpath("cite.bib").write_text("stale\n", encoding="utf-8")

            publication_importer.sync_imported_citations(root)

            self.assertEqual(legacy.joinpath("index.md").read_text(), legacy_text)
            self.assertEqual(legacy.joinpath("cite.bib").read_text(), legacy_cite)
            fields = parse_generated_bibtex(managed.joinpath("cite.bib").read_text())[2]
            self.assertEqual(fields["title"], "Managed after legacy")

    def test_citation_sync_strips_authors_and_restores_spaced_owner_id(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "content/publications/managed"
            bundle.mkdir(parents=True)
            bundle.joinpath("index.md").write_text(
                "---\npublication_importer: {managed_citation: true}\n"
                "title: Normalized authors\nauthors: [' me ', ' Alice ']\n"
                "date: '2026-05-06T00:00:00Z'\n"
                "publication_types: [article-journal]\n"
                "publication: {name: Identity Journal}\n"
                "hugoblox: {ids: {doi: 10.1109/identity}}\n"
                "draft: false\nrequires_correction: false\n---\n",
                encoding="utf-8",
            )
            bundle.joinpath("cite.bib").write_text("stale\n", encoding="utf-8")

            publication_importer.sync_imported_citations(root)

            frontmatter = yaml.safe_load(
                bundle.joinpath("index.md").read_text().split("---", 2)[1]
            )
            fields = parse_generated_bibtex(bundle.joinpath("cite.bib").read_text())[2]
            self.assertEqual(frontmatter["authors"], ["me", "Alice"])
            self.assertEqual(fields["author"], "Sean Longyu Ma and Alice")

    def test_citation_pair_rolls_back_on_each_final_replacement_failure(self):
        for failed_name in ("index.md", "cite.bib"):
            with self.subTest(failed_name=failed_name), TemporaryDirectory() as temp:
                root = Path(temp)
                bundle = root / "content/publications/managed"
                bundle.mkdir(parents=True)
                old_index = (
                    "---\npublication_importer: {managed_citation: true}\n"
                    "title: Transaction title\nauthors: [me]\n"
                    "date: '2026-04-05T00:00:00Z'\n"
                    "publication_types: [article-journal]\n"
                    "publication: {name: Transaction Journal}\n"
                    "hugoblox: {ids: {doi: 10.1109/transaction}}\n"
                    "draft: false\nrequires_correction: false\n"
                    "correction_reasons: [stale reason]\n"
                    "publication_date_parts: []\ndate_precision: missing\n"
                    "---\nbody\n"
                )
                old_citation = "@article{old,\n  title = {Old citation},\n}\n"
                index = bundle / "index.md"
                citation = bundle / "cite.bib"
                index.write_text(old_index, encoding="utf-8")
                citation.write_text(old_citation, encoding="utf-8")
                old_index_bytes = index.read_bytes()
                old_citation_bytes = citation.read_bytes()
                failed = False

                def fail_once(source, destination):
                    nonlocal failed
                    if destination.name == failed_name and not failed:
                        failed = True
                        raise OSError(f"injected {failed_name} replacement failure")
                    source.replace(destination)

                with patch.object(
                    publication_importer,
                    "replace_file",
                    fail_once,
                    create=True,
                ):
                    with self.assertRaisesRegex(RuntimeError, "replacement failure"):
                        publication_importer.sync_imported_citations(root)

                self.assertEqual(index.read_bytes(), old_index_bytes)
                self.assertEqual(citation.read_bytes(), old_citation_bytes)
                self.assertEqual(list(bundle.glob(".citation-sync-*")), [])

        with patch.object(
            sys,
            "argv",
            ["publication_importer.py", "--all-pending", "request.yml"],
        ), redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "2"):
                main()


if __name__ == "__main__":
    unittest.main()

from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import io
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_sync_gate():
    path = ROOT / "scripts/check_publication_sync.py"
    if not path.is_file():
        raise AssertionError(f"missing publication sync gate: {path}")
    spec = importlib.util.spec_from_file_location("check_publication_sync", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PublicationSyncGateTests(unittest.TestCase):
    def test_cli_runs_from_repository_root(self):
        with TemporaryDirectory() as temp:
            repository = Path(temp)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            result = subprocess.run(
                [
                    "python",
                    "scripts/check_publication_sync.py",
                    "--repo-root",
                    str(repository),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("synchronized and committed", result.stdout)

    def test_missing_managed_citation_is_untracked_and_fails_closed(self):
        gate = load_sync_gate()
        with TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "content/publications/managed"
            bundle.mkdir(parents=True)
            bundle.joinpath("index.md").write_text(
                "---\n"
                "publication_importer: {managed_citation: true}\n"
                "title: Complete publication\nauthors: [me]\n"
                "date: '2026-01-02T00:00:00Z'\n"
                "publication_types: [article-journal]\n"
                "publication: {name: Fixture Journal}\n"
                "hugoblox: {ids: {doi: 10.1109/example}}\n"
                "draft: false\nrequires_correction: false\n"
                "correction_reasons: []\n"
                "date_precision: day\npublication_date_parts: [2026, 1, 2]\n"
                "---\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "fixture@example.test"],
                cwd=root,
                check=True,
            )
            subprocess.run(["git", "add", "content/publications"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=root, check=True)

            with redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as raised:
                gate.main(["--repo-root", str(root)])

            self.assertEqual(raised.exception.code, 1)
            self.assertIn("?? content/publications/managed/cite.bib", output.getvalue())


if __name__ == "__main__":
    unittest.main()

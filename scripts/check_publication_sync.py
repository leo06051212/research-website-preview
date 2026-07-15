from pathlib import Path
import argparse
import subprocess
import sys

if __package__:
    from .publication_importer import sync_imported_citations
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from publication_importer import sync_imported_citations


PUBLICATION_PATH = "content/publications"


def publication_status(root: Path) -> str:
    sync_imported_citations(root)
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            PUBLICATION_PATH,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    changes = publication_status(root)
    if changes:
        print("Managed publication sync produced uncommitted changes:")
        print(changes, end="" if changes.endswith("\n") else "\n")
        diff = subprocess.run(
            ["git", "diff", "--", PUBLICATION_PATH],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if diff.stdout:
            print(diff.stdout, end="" if diff.stdout.endswith("\n") else "\n")
        raise SystemExit(1)
    print("Managed publication content is synchronized and committed")


if __name__ == "__main__":
    main()

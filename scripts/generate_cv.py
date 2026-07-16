from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from scripts.cv_data import load_cv_document, write_publication_review
from scripts.cv_pdf import render_cv_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the website Academic CV")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--portrait", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-report", type=Path, required=True)
    parser.add_argument("--generated-on", type=date.fromisoformat)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    portrait = args.portrait if args.portrait.is_absolute() else root / args.portrait
    output = args.output if args.output.is_absolute() else root / args.output
    review = (
        args.review_report
        if args.review_report.is_absolute()
        else root / args.review_report
    )
    document = load_cv_document(root)
    write_publication_review(document, review)
    result = render_cv_pdf(
        document,
        portrait,
        output,
        generated_on=args.generated_on or date.today(),
    )
    print(
        f"CV_PAGES={result.page_count} CV_BYTES={result.byte_count} "
        f"CV_PUBLICATIONS={len(document.publications)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

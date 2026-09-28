"""Extract text from a PDF one page at a time."""

from pathlib import Path

import pymupdf


def parse_pdf(pdf_path: str | Path) -> list[dict[str, int | str]]:
    """Return each PDF page's extracted text with a 1-based page number.

    Example result::

        [
            {"page": 1, "text": "Text from the first page"},
            {"page": 2, "text": "Text from the second page"},
        ]
    """
    pages: list[dict[str, int | str]] = []

    with pymupdf.open(str(pdf_path)) as document:
        for page_number, page in enumerate(document, start=1):
            pages.append({"page": page_number, "text": page.get_text()})

    return pages

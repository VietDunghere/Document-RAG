"""A small runnable test for :func:`src.parser.parse_pdf`."""

import json
from pathlib import Path

from src.parser import parse_pdf


def test_parse_pdf() -> None:
    """Parse a PDF from data/ and print its first two pages."""
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    pdf_files = sorted(
        path for path in data_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )
    if not pdf_files:
        raise FileNotFoundError(f"Không tìm thấy file PDF nào trong {data_dir}")

    pdf_path = pdf_files[0]
    print(f"Reading: {pdf_path.name}")

    result = parse_pdf(pdf_path)
    first_two_pages = result[:2]
    print(json.dumps(first_two_pages, ensure_ascii=False, indent=4))

    assert len(first_two_pages) == 2
    assert [page["page"] for page in first_two_pages] == [1, 2]
    assert all(isinstance(page["text"], str) for page in first_two_pages)


if __name__ == "__main__":
    test_parse_pdf()
    print("Parser test passed.")

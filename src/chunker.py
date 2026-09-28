"""Recursively split PDF text into overlapping, token-sized JSON chunks."""

from __future__ import annotations

import json
import re
from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Any

import tiktoken

from src.parser import parse_pdf


CHUNK_MIN_TOKENS = 500
CHUNK_MAX_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 100
TOKEN_ENCODING = "cl100k_base"


def _find_recursive_cut(
    text: str,
    token_offsets: list[int],
    start: int,
    min_end: int,
    max_end: int,
) -> int:
    """Prefer paragraph, line, sentence, then word boundaries for a split."""
    min_char = token_offsets[min_end - 1]
    max_char = token_offsets[max_end] if max_end < len(token_offsets) else len(text)

    # This separator order is the recursive split priority: broad text
    # boundaries first, then progressively smaller boundaries.
    for separator in ("\n\n", "\n", ". ", " "):
        position = text.rfind(separator, min_char, max_char)
        if position == -1:
            continue

        boundary_char = position + len(separator)
        token_end = bisect_left(token_offsets, boundary_char, min_end, max_end + 1)
        if min_end <= token_end <= max_end:
            return token_end

    # A long unbroken string has no useful separator, so split at the limit.
    return max_end


def _recursive_token_spans(
    text: str,
    tokens: list[int],
    token_offsets: list[int],
    start: int = 0,
) -> list[tuple[int, int]]:
    """Return token ranges, recursively splitting oversized text with overlap."""
    spans: list[tuple[int, int]] = []
    while start < len(tokens):
        remaining = len(tokens) - start
        if remaining <= CHUNK_MAX_TOKENS:
            spans.append((start, len(tokens)))
            break

        min_end = start + CHUNK_MIN_TOKENS
        max_end = min(start + CHUNK_MAX_TOKENS, len(tokens))
        end = _find_recursive_cut(text, token_offsets, start, min_end, max_end)
        spans.append((start, end))
        start = end - CHUNK_OVERLAP_TOKENS

    return spans


def _safe_name(value: str) -> str:
    """Convert a relative document path into a filesystem-safe identifier."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "document"


def chunk_pdf(
    pdf_path: str | Path,
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/processed",
) -> list[dict[str, Any]]:
    """Chunk one PDF and save each chunk as an individual JSON file.

    The ``page`` field is the first page represented in that chunk. Chunks may
    continue across a page boundary so that they can reach the requested size.
    """
    pdf_path = Path(pdf_path)
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    encoding = tiktoken.get_encoding(TOKEN_ENCODING)

    pages = parse_pdf(pdf_path)
    page_texts = [str(page["text"]) for page in pages]
    text_parts: list[str] = []
    page_char_starts: list[tuple[int, int]] = []
    char_offset = 0

    for page_number, page_text in enumerate(page_texts, start=1):
        if page_number > 1:
            text_parts.append("\n\n")
            char_offset += 2
        page_char_starts.append((char_offset, page_number))
        text_parts.append(page_text)
        char_offset += len(page_text)

    full_text = "".join(text_parts)
    tokens = encoding.encode(full_text)
    if not tokens:
        return []

    decoded_text, token_offsets = encoding.decode_with_offsets(tokens)
    spans = _recursive_token_spans(decoded_text, tokens, token_offsets)
    page_token_starts = [
        (bisect_left(token_offsets, page_start), page_number)
        for page_start, page_number in page_char_starts
    ]

    try:
        document_name = pdf_path.resolve().relative_to(data_dir.resolve()).as_posix()
    except ValueError:
        document_name = pdf_path.name

    document_key = _safe_name(document_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[dict[str, Any]] = []

    for chunk_number, (start, end) in enumerate(spans, start=1):
        page_index = bisect_right(page_token_starts, (start, float("inf"))) - 1
        page_number = page_token_starts[max(page_index, 0)][1]
        chunk = {
            "chunk_id": f"{document_key}__p{page_number:04d}__c{chunk_number:05d}",
            "page": page_number,
            "text": encoding.decode(tokens[start:end]),
            "document": document_name,
        }
        chunks.append(chunk)

        output_path = output_dir / f"{chunk['chunk_id']}.json"
        with output_path.open("w", encoding="utf-8") as json_file:
            json.dump(chunk, json_file, ensure_ascii=False, indent=2)

    return chunks


def process_data_directory(
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/processed",
) -> list[dict[str, Any]]:
    """Chunk every PDF under ``data_dir``, excluding the output directory."""
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_resolved = output_dir.resolve()
    pdf_files = sorted(
        path
        for path in data_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() == ".pdf"
        and output_resolved not in path.resolve().parents
    )

    all_chunks: list[dict[str, Any]] = []
    for pdf_path in pdf_files:
        all_chunks.extend(chunk_pdf(pdf_path, data_dir, output_dir))
    return all_chunks


if __name__ == "__main__":
    chunks = process_data_directory()
    print(f"Saved {len(chunks)} chunks to data/processed/")

from __future__ import annotations

import re

import pymupdf


def pdf_page_texts(file_path: str) -> list[tuple[int, str]]:
    """Extract text from each page of a PDF.

    Returns a list of (page_number, text) tuples. Raises ValueError
    when the PDF contains no extractable text (likely a scanned PDF).
    """
    doc = pymupdf.open(file_path)
    pages: list[tuple[int, str]] = []

    page_count = len(doc)
    for page_num in range(page_count):
        page = doc[page_num]
        text = page.get_text()
        text = normalize_whitespace(text)
        pages.append((page.number + 1, text))

    doc.close()

    total = sum(len(page_text) for _, page_text in pages)
    if total == 0:
        raise ValueError("PDF does not contain extractable text (likely a scanned PDF without OCR).")

    return pages


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace (including tabs and non-breaking spaces) and strip edges."""
    text = text.replace("\u3000", " ")  # full-width space
    text = text.replace("\xa0", " ")    # non-breaking space
    # Replace runs of whitespace (including tabs, newlines) with a single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs using consecutive newline boundaries.

    This is a basic split: treats one or more empty lines as paragraph
    separator.  MVP-005 will refine this with cleaner rules.
    """
    # Normalise newlines then split on blank lines
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalised)
    return [block.strip() for block in blocks if block.strip()]


def split_sentences(text: str) -> list[str]:
    """Split a text block into sentences.

    Recognises Chinese sentence-final punctuation (。！？；) and
    English sentence-end punctuation (.?!;).  Each sentence retains
    its delimiter.

    Returns only non-empty sentences after stripping whitespace.
    """
    if not text:
        return []

    # Chinese sentence-final punctuation
    chinese_break = re.compile(r"(?<=[。！？；])")

    # English sentence-end punctuation (sequence of . ! ? ; followed by space or end)
    # We split on .!?; that are followed by whitespace, start-of-string, or end-of-string.
    english_break = re.compile(r"(?<=[.?!;])(?=\s|$)")

    # First pass: split by Chinese breaks
    parts = chinese_break.split(text)

    # Second pass: split each part by English breaks
    sentences: list[str] = []
    for part in parts:
        subs = english_break.split(part)
        for sub in subs:
            stripped = sub.strip()
            if stripped:
                sentences.append(stripped)

    return sentences

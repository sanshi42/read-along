from __future__ import annotations

import re

import pymupdf

# --- Regex patterns ---

# Common noise patterns: short navigational labels, social share buttons,
# comment section headers, page-turn prompts, etc.
_NOISE_LINE_PATTERNS = [
    re.compile(r"^\s*(上一篇|下一篇|下一章|下一节|返回目录|回顶部|返回首页)\s*$"),
    re.compile(r"^\s*(分享|收藏|点赞|评论|举报|投诉|赞赏|打赏|关注)\s*$"),
    re.compile(r"^\s*(网友评论|用户留言|精选留言|全部留言|最新评论|热门评论)\s*$"),
    re.compile(r"^\s*(登录|注册|退出|设置|搜索|扫码|手机看|APP看)\s*$"),
    re.compile(r"^\s*(更多|加载更多|展开全文|收起)\s*$"),
    re.compile(r"^\s*(Copyright|©|版权所有|All Rights Reserved|隐私政策|用户协议).*\s*$"),
    # Single character or purely symbolic lines
    re.compile(r"^\s*[^\w\u4e00-\u9fff]+\s*$"),
    # Very short lines (1 character)
    re.compile(r"^\s*\w\s*$"),
]

# Full-width space, non-breaking space
_SPACE_REPLACEMENTS = {"\u3000": " ", "\xa0": " "}


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
    for old, new in _SPACE_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Remove common noise patterns from extracted text.

    Strips lines matching known noise patterns (navigation, social
    buttons, comment headers, copyright notices, etc.) and removes
    duplicate consecutive lines.
    """
    lines = text.split("\n")
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Preserve blank lines as paragraph separators
            if filtered and filtered[-1] != "":
                filtered.append("")
            continue
        if _is_noise_line(stripped):
            continue
        filtered.append(stripped)

    # Remove trailing blank lines
    while filtered and filtered[-1] == "":
        filtered.pop()

    return "\n".join(filtered)


def _is_noise_line(line: str) -> bool:
    """Check if a single line is a known noise pattern."""
    for pattern in _NOISE_LINE_PATTERNS:
        if pattern.match(line):
            return True
    return False


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs using consecutive newline boundaries.

    Treats one or more blank lines as paragraph separators.
    """
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalised)
    return [block.strip() for block in blocks if block.strip()]


def split_sentences(text: str, *, max_length: int = 120) -> list[str]:
    """Split a text block into sentences with noise filtering.

    Recognises Chinese sentence-final punctuation (。！？；) and
    English sentence-end punctuation (.?!;).  Filters overly short
    noise sentences and splits overly long sentences at Chinese comma
    positions.
    """
    if not text:
        return []

    chinese_break = re.compile(r"(?<=[。！？；])")
    english_break = re.compile(r"(?<=[.?!;])(?=\s|$)")

    parts = chinese_break.split(text)

    sentences: list[str] = []
    for part in parts:
        subs = english_break.split(part)
        for sub in subs:
            stripped = sub.strip()
            if not stripped:
                continue
            if len(stripped) > max_length and _contains_cjk(stripped):
                split = _split_long_sentence(stripped, max_length)
                sentences.extend(split)
            else:
                sentences.append(stripped)

    # Filter noise sentences
    return [s for s in sentences if not _is_noise_sentence(s)]


def _contains_cjk(text: str) -> bool:
    """Check if text contains any CJK characters."""
    return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))


def _split_long_sentence(text: str, max_length: int) -> list[str]:
    """Split an overly long sentence at Chinese comma (，) positions.

    Each resulting segment is at least 20 characters long where possible.
    """
    # Split at Chinese commas
    parts = re.split(r"(?<=，)", text)
    result: list[str] = []
    buf = ""

    for part in parts:
        if len(buf) + len(part) <= max_length:
            buf += part
        else:
            if buf:
                result.append(buf.strip())
            buf = part

    if buf.strip():
        result.append(buf.strip())

    return result if result else [text]


def _is_noise_sentence(sentence: str) -> bool:
    """Check if a sentence is noise (too short, pure symbols, known patterns)."""
    stripped = sentence.strip()
    if not stripped:
        return True

    # Pure punctuation/symbols (no CJK, no ASCII letters/numbers)
    has_content = re.search(r"[\u4e00-\u9fff\w]", stripped)
    if not has_content:
        return True

    # Match known noise patterns
    if _is_noise_line(stripped):
        return True

    # Single CJK character (possibly with punctuation) is likely noise
    no_punct = re.sub(r"[。！？；，…、.?!;,\s]+", "", stripped)
    if len(no_punct) <= 1 and re.search(r"[\u4e00-\u9fff]", no_punct):
        return True

    return False


def structure_text(text: str) -> list[list[str]]:
    """Structure raw text into paragraphs and sentences.

    Pipeline: clean noise → split into paragraphs → split each
    paragraph into sentences.

    Returns a list of paragraphs, each paragraph being a list of
    sentence strings.
    """
    cleaned = clean_text(text)
    paragraphs = split_paragraphs(cleaned)
    return [split_sentences(para) for para in paragraphs if para.strip()]

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from read_along.extractors import (
    normalize_whitespace,
    pdf_page_texts,
    split_paragraphs,
    split_sentences,
)


def _create_pdf(tmp_path: Path, text: str, file_name: str = "test.pdf") -> str:
    """Create a single-page text PDF for testing."""
    file_path = tmp_path / file_name
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=12)
    doc.save(str(file_path))
    doc.close()
    return str(file_path)


class TestNormalizeWhitespace:
    def test_collapse_multiple_spaces(self) -> None:
        assert normalize_whitespace("hello    world") == "hello world"

    def test_strip_edges(self) -> None:
        assert normalize_whitespace("  hello  ") == "hello"

    def test_fullwidth_space_to_ascii(self) -> None:
        assert normalize_whitespace("hello\u3000world") == "hello world"

    def test_non_breaking_space_to_ascii(self) -> None:
        assert normalize_whitespace("hello\xa0world") == "hello world"

    def test_newlines_collapsed(self) -> None:
        assert normalize_whitespace("hello\n\nworld") == "hello world"


class TestSplitParagraphs:
    def test_single_paragraph(self) -> None:
        assert split_paragraphs("One paragraph.") == ["One paragraph."]

    def test_two_paragraphs_by_double_newline(self) -> None:
        text = "First paragraph.\n\nSecond paragraph."
        result = split_paragraphs(text)
        assert result == ["First paragraph.", "Second paragraph."]

    def test_multiple_blank_lines_as_single_separator(self) -> None:
        text = "A\n\n\nB\n\nC"
        result = split_paragraphs(text)
        assert result == ["A", "B", "C"]

    def test_empty_input(self) -> None:
        assert split_paragraphs("") == []

    def test_only_whitespace_input(self) -> None:
        assert split_paragraphs("   \n\n  ") == []

    def test_crlf_handled(self) -> None:
        text = "First.\r\n\r\nSecond."
        result = split_paragraphs(text)
        assert result == ["First.", "Second."]


class TestSplitSentences:
    def test_chinese_single_sentence(self) -> None:
        result = split_sentences("这是一句话。")
        assert result == ["这是一句话。"]

    def test_chinese_multiple_sentences(self) -> None:
        result = split_sentences("第一句。第二句和第三句。最后一句。")
        assert result == ["第一句。", "第二句和第三句。", "最后一句。"]

    def test_chinese_with_exclamation_and_question(self) -> None:
        result = split_sentences("你好！真的吗？是的。")
        assert result == ["你好！", "真的吗？", "是的。"]

    def test_chinese_with_semicolon(self) -> None:
        result = split_sentences("A；B；C。")
        assert result == ["A；", "B；", "C。"]

    def test_english_sentences(self) -> None:
        result = split_sentences("Hello. World! Is it? Yes; no.")
        assert result == ["Hello.", "World!", "Is it?", "Yes;", "no."]

    def test_mixed_chinese_english(self) -> None:
        result = split_sentences("你好。Hello world. 是的。")
        assert result == ["你好。", "Hello world.", "是的。"]

    def test_empty_input(self) -> None:
        assert split_sentences("") == []

    def test_whitespace_only(self) -> None:
        assert split_sentences("   ") == []


class TestPdfPageTexts:
    def test_extracts_text_from_single_page(self, tmp_path: Path) -> None:
        path = _create_pdf(tmp_path, "Hello, PDF world.")
        pages = pdf_page_texts(path)
        assert len(pages) == 1
        pagenum, text = pages[0]
        assert pagenum == 1
        assert "Hello, PDF world." in text

    def test_empty_pdf_raises_value_error(self, tmp_path: Path) -> None:
        path = _create_pdf(tmp_path, "")
        with pytest.raises(ValueError, match="extractable text"):
            pdf_page_texts(path)

    def test_multiple_pages(self, tmp_path: Path) -> None:
        """Create a two-page PDF and verify both pages are extracted."""
        file_path = tmp_path / "two_page.pdf"
        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Page one text.", fontsize=12)
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page two text.", fontsize=12)
        doc.save(str(file_path))
        doc.close()

        pages = pdf_page_texts(str(file_path))
        assert len(pages) == 2
        assert pages[0][0] == 1
        assert "Page one text." in pages[0][1]
        assert pages[1][0] == 2
        assert "Page two text." in pages[1][1]

    def test_page_numbers_start_at_one(self, tmp_path: Path) -> None:
        path = _create_pdf(tmp_path, "Page 1.")
        pages = pdf_page_texts(path)
        assert pages[0][0] == 1

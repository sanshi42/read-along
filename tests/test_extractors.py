from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from read_along.extractors import (
    _split_long_sentence,
    clean_text,
    normalize_whitespace,
    pdf_page_texts,
    split_paragraphs,
    split_sentences,
    structure_text,
)


def _create_pdf(tmp_path: Path, text: str, file_name: str = 'test.pdf') -> str:
    """创建用于测试的单页文本型 PDF。"""
    file_path = tmp_path / file_name
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=12)
    doc.save(str(file_path))
    doc.close()
    return str(file_path)


class TestNormalizeWhitespace:
    def test_collapse_multiple_spaces(self) -> None:
        assert normalize_whitespace('hello    world') == 'hello world'

    def test_strip_edges(self) -> None:
        assert normalize_whitespace('  hello  ') == 'hello'

    def test_fullwidth_space_to_ascii(self) -> None:
        assert normalize_whitespace('hello\u3000world') == 'hello world'

    def test_non_breaking_space_to_ascii(self) -> None:
        assert normalize_whitespace('hello\xa0world') == 'hello world'

    def test_newlines_collapsed(self) -> None:
        assert normalize_whitespace('hello\n\nworld') == 'hello world'


class TestSplitParagraphs:
    def test_single_paragraph(self) -> None:
        assert split_paragraphs('One paragraph.') == ['One paragraph.']

    def test_two_paragraphs_by_double_newline(self) -> None:
        text = 'First paragraph.\n\nSecond paragraph.'
        result = split_paragraphs(text)
        assert result == ['First paragraph.', 'Second paragraph.']

    def test_multiple_blank_lines_as_single_separator(self) -> None:
        text = 'A\n\n\nB\n\nC'
        result = split_paragraphs(text)
        assert result == ['A', 'B', 'C']

    def test_empty_input(self) -> None:
        assert split_paragraphs('') == []

    def test_only_whitespace_input(self) -> None:
        assert split_paragraphs('   \n\n  ') == []

    def test_crlf_handled(self) -> None:
        text = 'First.\r\n\r\nSecond.'
        result = split_paragraphs(text)
        assert result == ['First.', 'Second.']


class TestSplitSentences:
    def test_chinese_single_sentence(self) -> None:
        result = split_sentences('这是一句话。')
        assert result == ['这是一句话。']

    def test_chinese_multiple_sentences(self) -> None:
        result = split_sentences('第一句。第二句和第三句。最后一句。')
        assert result == ['第一句。', '第二句和第三句。', '最后一句。']

    def test_chinese_with_exclamation_and_question(self) -> None:
        result = split_sentences('你好！真的吗？是的。')
        assert result == ['你好！', '真的吗？', '是的。']

    def test_chinese_with_semicolon(self) -> None:
        result = split_sentences('A；B；C。')
        assert result == ['A；', 'B；', 'C。']

    def test_english_sentences(self) -> None:
        result = split_sentences('Hello. World! Is it? Yes; no.')
        assert result == ['Hello.', 'World!', 'Is it?', 'Yes;', 'no.']

    def test_mixed_chinese_english(self) -> None:
        result = split_sentences('你好。Hello world. 是的。')
        assert result == ['你好。', 'Hello world.', '是的。']

    def test_empty_input(self) -> None:
        assert split_sentences('') == []

    def test_whitespace_only(self) -> None:
        assert split_sentences('   ') == []


class TestPdfPageTexts:
    def test_extracts_text_from_single_page(self, tmp_path: Path) -> None:
        path = _create_pdf(tmp_path, 'Hello, PDF world.')
        pages = pdf_page_texts(path)
        assert len(pages) == 1
        pagenum, text = pages[0]
        assert pagenum == 1
        assert 'Hello, PDF world.' in text

    def test_empty_pdf_raises_value_error(self, tmp_path: Path) -> None:
        path = _create_pdf(tmp_path, '')
        with pytest.raises(ValueError, match='不包含可提取文本'):
            pdf_page_texts(path)

    def test_multiple_pages(self, tmp_path: Path) -> None:
        """创建两页 PDF 并验证两页文本均被提取。"""
        file_path = tmp_path / 'two_page.pdf'
        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((50, 50), 'Page one text.', fontsize=12)
        page2 = doc.new_page()
        page2.insert_text((50, 50), 'Page two text.', fontsize=12)
        doc.save(str(file_path))
        doc.close()

        pages = pdf_page_texts(str(file_path))
        assert len(pages) == 2
        assert pages[0][0] == 1
        assert 'Page one text.' in pages[0][1]
        assert pages[1][0] == 2
        assert 'Page two text.' in pages[1][1]

    def test_page_numbers_start_at_one(self, tmp_path: Path) -> None:
        path = _create_pdf(tmp_path, 'Page 1.')
        pages = pdf_page_texts(path)
        assert pages[0][0] == 1


class TestCleanText:
    def test_preserves_normal_text(self) -> None:
        text = '这是一段正常的文本。\n这是第二行。'
        result = clean_text(text)
        assert '这是一段正常的文本。' in result
        assert '这是第二行。' in result

    def test_removes_prev_next_navigation(self) -> None:
        text = '正文内容。\n上一篇\n下一篇\n更多内容。'
        result = clean_text(text)
        assert '上一篇' not in result
        assert '下一篇' not in result
        assert '正文内容。' in result
        assert '更多内容。' in result

    def test_removes_share_like_comment(self) -> None:
        for noise in ['分享', '收藏', '点赞', '评论', '举报']:
            result = clean_text(f'Hello.\n{noise}\nWorld.')
            assert noise not in result

    def test_removes_comment_section_headers(self) -> None:
        text = '文章内容。\n网友评论\n精选留言\n继续。'
        result = clean_text(text)
        assert '网友评论' not in result
        assert '精选留言' not in result
        assert '文章内容。' in result

    def test_removes_copyright_notice(self) -> None:
        text = '正文。\nCopyright 2024 Test Inc.\n结束。'
        result = clean_text(text)
        assert 'Copyright' not in result

    def test_removes_single_char_lines(self) -> None:
        text = '正常文本。\nA\n正常文本。\n1\n正常文本。'
        result = clean_text(text)
        assert 'A' not in result
        assert '1' not in result

    def test_removes_purely_symbolic_lines(self) -> None:
        text = 'Content.\n---\n***\nMore content.'
        result = clean_text(text)
        assert '---' not in result
        assert '***' not in result

    def test_preserves_blank_lines_as_separators(self) -> None:
        text = 'Para 1.\n\nPara 2.'
        result = clean_text(text)
        # 应继续保留段落分隔
        assert 'Para 1.' in result
        assert 'Para 2.' in result
        # 应保留双换行分隔符
        assert '\n\n' in result


class TestSplitSentencesNoise:
    def test_filters_single_cjk_character(self) -> None:
        result = split_sentences('你好。的。世界。')
        assert '的' not in result
        assert len(result) == 2
        assert result == ['你好。', '世界。']

    def test_filters_pure_punctuation(self) -> None:
        result = split_sentences('Hello. ... World.')
        # ... 是纯标点，应被过滤
        assert '...' not in result

    def test_long_sentence_split_at_comma(self) -> None:
        # 构造包含逗号且长度超过 120 个字符的句子
        base = '这是一个很长的句子，' * 8
        # 每次重复约 10 个字符，8 * 13 = 104
        text = base + '这是最后的结束。'
        result = split_sentences(text, max_length=60)
        # 应被拆分为多个片段
        assert len(result) >= 2

    def test_short_sentences_preserved(self) -> None:
        result = split_sentences('Ok. Yes. Good.')
        assert result == ['Ok.', 'Yes.', 'Good.']


class TestStructureText:
    def test_simple_pipeline(self) -> None:
        result = structure_text('第一段。\n\n第二段。')
        assert len(result) == 2
        assert result[0] == ['第一段。']
        assert result[1] == ['第二段。']

    def test_noise_filtered_in_pipeline(self) -> None:
        text = '正文。\n\n上一篇\n\n结束。'
        result = structure_text(text)
        # 应过滤“上一篇”段落
        assert all('上一篇' not in ' '.join(sentences) for sentences in result)
        # 应保留“正文。”和“结束。”两个段落
        assert len(result) == 2

    def test_empty_text(self) -> None:
        assert structure_text('') == []

    def test_only_noise_text(self) -> None:
        assert structure_text('上一篇\n\n分享\n\n收藏') == []


class TestLongSentenceSplit:
    def test_no_split_for_short_sentence(self) -> None:
        result = _split_long_sentence('短句，还是短句。', max_length=100)
        assert result == ['短句，还是短句。']

    def test_split_at_comma_when_exceeds_max(self) -> None:
        long_text = 'A' * 50 + '，' + 'B' * 50 + '，' + 'C' * 50
        result = _split_long_sentence(long_text, max_length=70)
        assert len(result) >= 2

    def test_returns_single_if_no_comma(self) -> None:
        long_text = 'A' * 200
        result = _split_long_sentence(long_text, max_length=100)
        assert len(result) == 1
        assert result[0] == long_text

from __future__ import annotations

from pathlib import Path
import pymupdf
import pytest

from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.importers import UrlImportError, WebPageContent, import_pdf, import_url
from read_along.material_library import MaterialLibrary
from read_along.models import MaterialDetail, SourceType
from read_along.storage import StoragePaths


def _create_text_pdf(tmp_path: Path, text: str, file_name: str = "test.pdf") -> str:
    """在指定路径创建单页文本型 PDF。"""
    file_path = tmp_path / file_name
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=12)
    doc.save(str(file_path))
    doc.close()
    return str(file_path)


def _library(tmp_path: Path) -> MaterialLibrary:
    """创建用于测试的材料库。"""
    home = tmp_path / "data"
    paths = StoragePaths.from_config(AppConfig(home=home))
    initialize_database(paths)
    return MaterialLibrary(paths)


class TestImportPdf:
    def test_basic_import(self, tmp_path: Path) -> None:
        _create_text_pdf(tmp_path, "Hello world. This is sentence two.")
        library = _library(tmp_path)

        result = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            library=library,
        )

        assert isinstance(result, MaterialDetail)
        assert result.primary_source.source_type == SourceType.PDF
        assert result.primary_source.source_uri == "test.pdf"
        assert result.paragraphs
        assert len(result.paragraphs) == 1

        para = result.paragraphs[0]
        assert para.index == 1
        assert para.source_label == "第 1 页，第 1 段"
        assert para.sentences
        assert len(para.sentences) == 2
        assert para.sentences[0].text == "Hello world."
        assert para.sentences[0].index == 1
        assert para.sentences[1].text == "This is sentence two."
        assert para.sentences[1].index == 2

    def test_multi_page_import(self, tmp_path: Path) -> None:
        """验证两页 PDF 生成两个段落。"""
        file_path = tmp_path / "two_page.pdf"
        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Page one.", fontsize=12)
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page two.", fontsize=12)
        doc.save(str(file_path))
        doc.close()

        library = _library(tmp_path)

        result = import_pdf(
            file_path=file_path,
            filename="two_page.pdf",
            library=library,
        )

        assert len(result.paragraphs) == 2
        assert result.paragraphs[0].source_label == "第 1 页，第 1 段"
        assert result.paragraphs[1].source_label == "第 2 页，第 1 段"
        assert "Page one." in result.paragraphs[0].text
        assert "Page two." in result.paragraphs[1].text

    def test_material_persists_in_material_library(self, tmp_path: Path) -> None:
        _create_text_pdf(tmp_path, "Hello PDF.")
        library = _library(tmp_path)

        result = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            library=library,
        )

        refreshed = MaterialLibrary(library.storage_paths).get(result.id)
        assert refreshed.title == "test.pdf"
        assert refreshed.primary_source.source_type == SourceType.PDF
        assert len(refreshed.paragraphs) == 1
        assert refreshed.paragraphs[0].sentences[0].text == "Hello PDF."

    def test_uploaded_file_copied_to_uploads(self, tmp_path: Path) -> None:
        _create_text_pdf(tmp_path, "Content.")
        library = _library(tmp_path)

        result = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            library=library,
        )

        assert result.primary_source.source_path is not None
        expected_copy = Path(result.primary_source.source_path)
        assert expected_copy.is_file()
        assert expected_copy.stat().st_size > 0

    def test_empty_pdf_raises_value_error(self, tmp_path: Path) -> None:
        """没有文本的 PDF 应抛出 ValueError。"""
        _create_text_pdf(tmp_path, "", file_name="empty.pdf")
        library = _library(tmp_path)

        with pytest.raises(ValueError, match="不包含可提取文本"):
            import_pdf(
                file_path=tmp_path / "empty.pdf",
                filename="empty.pdf",
                library=library,
            )

    def test_idempotent_material_id(self, tmp_path: Path) -> None:
        """重复导入同名 PDF 应生成相同的 material_id。"""
        _create_text_pdf(tmp_path, "Some text.")
        library1 = _library(tmp_path / "r1")

        result1 = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            library=library1,
        )

        library2 = _library(tmp_path / "r2")
        result2 = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            library=library2,
        )

        assert result1.id == result2.id

    def test_sentences_extracted_in_order(self, tmp_path: Path) -> None:
        """页面上的多个文本块应按顺序生成句子。"""
        file_path = tmp_path / "ordered.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "First sentence.", fontsize=12)
        page.insert_text((50, 80), "Second sentence.", fontsize=12)
        doc.save(str(file_path))
        doc.close()

        library = _library(tmp_path)

        result = import_pdf(
            file_path=file_path,
            filename="ordered.pdf",
            library=library,
        )

        # 句子应保持原有顺序
        all_sentences = [s.text for p in result.paragraphs for s in p.sentences]
        assert "First sentence." in all_sentences
        assert "Second sentence." in all_sentences

    def test_noise_lines_filtered(self, tmp_path: Path) -> None:
        """导入文本时应过滤“上一篇”等噪声行。"""
        file_path = tmp_path / "noise.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Real content.", fontsize=12)
        page.insert_text((50, 70), "上一篇", fontsize=12)
        page.insert_text((50, 90), "More content.", fontsize=12)
        doc.save(str(file_path))
        doc.close()

        library = _library(tmp_path)

        result = import_pdf(
            file_path=file_path,
            filename="noise.pdf",
            library=library,
        )

        # 应已过滤“上一篇”
        all_text = " ".join(s.text for p in result.paragraphs for s in p.sentences)
        assert "上一篇" not in all_text
        assert "Real content." in all_text
        assert "More content." in all_text


class TestImportUrl:
    def test_basic_import(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """公开网页正文应结构化后保存为 URL 来源材料。"""
        library = _library(tmp_path)

        def fake_fetch(url: str) -> WebPageContent:
            assert url == "https://example.com/article"
            return WebPageContent(
                title="示例网页",
                url=url,
                text=(
                    "分享\n"
                    "第一段正文讲述一个值得阅读的公开网页内容。第二句继续补充信息。\n\n"
                    "最新评论\n"
                    "第二段正文提供后续细节。"
                ),
            )

        monkeypatch.setattr("read_along.importers.fetch_webpage", fake_fetch)

        result = import_url(
            url="https://example.com/article",
            library=library,
        )

        assert result.primary_source.source_type == SourceType.URL
        assert result.primary_source.source_uri == "https://example.com/article"
        assert result.title == "示例网页"
        assert len(result.paragraphs) == 2
        assert result.paragraphs[0].source_label == "网页正文，第 1 段"
        all_text = " ".join(sentence.text for paragraph in result.paragraphs for sentence in paragraph.sentences)
        assert "分享" not in all_text
        assert "最新评论" not in all_text
        assert "第一段正文" in all_text

    def test_empty_body_raises_url_import_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """正文为空或只有噪声时应返回网页导入错误。"""
        library = _library(tmp_path)

        monkeypatch.setattr(
            "read_along.importers.fetch_webpage",
            lambda url: WebPageContent(title="空网页", url=url, text="分享\n评论\n上一篇"),
        )

        with pytest.raises(UrlImportError, match="网页正文为空"):
            import_url(
                url="https://example.com/empty",
                library=library,
            )

    def test_rejects_unsupported_mode(self, tmp_path: Path) -> None:
        library = _library(tmp_path)

        with pytest.raises(UrlImportError, match="仅支持公开网页自动导入"):
            import_url(
                url="https://example.com/article",
                mode="chrome",
                library=library,
            )

    def test_rejects_non_http_url(self, tmp_path: Path) -> None:
        library = _library(tmp_path)

        with pytest.raises(UrlImportError, match="HTTP 或 HTTPS"):
            import_url(
                url="file:///tmp/article.html",
                library=library,
            )

    def test_dedao_url_uses_dedao_cleaning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """得到 URL 应在结构化前应用得到专用清洗规则。"""
        target_url = "https://www.dedao.cn/course/article?id=obyrmnqGdwxkXWMa0VelBz2D5ZO8aN"
        library = _library(tmp_path)

        def fake_fetch(url: str) -> WebPageContent:
            assert url == target_url
            return WebPageContent(
                title="得到单篇",
                url=target_url,
                text=(
                    "得到\n"
                    "课程目录\n"
                    "这是一段来自得到单篇的正文内容。它应该进入阅读材料。\n\n"
                    "下一讲\n"
                    "写留言\n"
                    "第二段正文继续说明课程里的关键观点。"
                ),
            )

        monkeypatch.setattr("read_along.importers.fetch_webpage", fake_fetch)

        result = import_url(
            url=target_url,
            library=library,
        )

        all_text = " ".join(sentence.text for paragraph in result.paragraphs for sentence in paragraph.sentences)
        assert result.primary_source.source_uri == target_url
        assert "课程目录" not in all_text
        assert "下一讲" not in all_text
        assert "写留言" not in all_text
        assert "得到单篇的正文内容" in all_text
        assert "第二段正文" in all_text

    def test_empty_dedao_body_returns_specific_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """得到 URL 直抓无正文时应说明登录态或动态渲染边界。"""
        target_url = "https://www.dedao.cn/course/article?id=obyrmnqGdwxkXWMa0VelBz2D5ZO8aN"
        library = _library(tmp_path)

        monkeypatch.setattr(
            "read_along.importers.fetch_webpage",
            lambda url: WebPageContent(title="得到", url=target_url, text=""),
        )

        with pytest.raises(UrlImportError, match="登录态或动态渲染"):
            import_url(
                url=target_url,
                library=library,
            )

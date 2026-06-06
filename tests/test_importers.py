from __future__ import annotations

from pathlib import Path
import pymupdf
import pytest

from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.importers import import_pdf
from read_along.models import MaterialDetail, MaterialStatus, SourceType
from read_along.repository import Repository
from read_along.storage import StoragePaths



def _create_text_pdf(tmp_path: Path, text: str, file_name: str = "test.pdf") -> str:
    """Create a single-page text PDF at the given path."""
    file_path = tmp_path / file_name
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=12)
    doc.save(str(file_path))
    doc.close()
    return str(file_path)


def _repo_and_uploads(tmp_path: Path) -> tuple[Repository, Path]:
    """Create a Repository and uploads directory for testing."""
    home = tmp_path / "data"
    paths = StoragePaths.from_config(AppConfig(home=home))
    initialize_database(paths)
    repo = Repository(paths.database)
    return repo, paths.uploads


class TestImportPdf:
    def test_basic_import(self, tmp_path: Path) -> None:
        _create_text_pdf(tmp_path, "Hello world. This is sentence two.")
        repo, uploads_dir = _repo_and_uploads(tmp_path)

        result = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            repo=repo,
            uploads_dir=uploads_dir,
        )

        assert isinstance(result, MaterialDetail)
        assert result.source_type == SourceType.PDF
        assert result.source_uri == "test.pdf"
        assert result.status == MaterialStatus.READY
        assert result.paragraphs
        assert len(result.paragraphs) == 1

        para = result.paragraphs[0]
        assert para.index == 1
        assert para.source_label == "Page 1, Block 1"
        assert para.sentences
        assert len(para.sentences) == 2
        assert para.sentences[0].text == "Hello world."
        assert para.sentences[0].index == 1
        assert para.sentences[1].text == "This is sentence two."
        assert para.sentences[1].index == 2

    def test_multi_page_import(self, tmp_path: Path) -> None:
        """Verify a two-page PDF produces two paragraphs."""
        file_path = tmp_path / "two_page.pdf"
        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Page one.", fontsize=12)
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page two.", fontsize=12)
        doc.save(str(file_path))
        doc.close()

        repo, uploads_dir = _repo_and_uploads(tmp_path)

        result = import_pdf(
            file_path=file_path,
            filename="two_page.pdf",
            repo=repo,
            uploads_dir=uploads_dir,
        )

        assert len(result.paragraphs) == 2
        assert result.paragraphs[0].source_label == "Page 1, Block 1"
        assert result.paragraphs[1].source_label == "Page 2, Block 1"
        assert "Page one." in result.paragraphs[0].text
        assert "Page two." in result.paragraphs[1].text

    def test_material_persists_in_repository(self, tmp_path: Path) -> None:
        _create_text_pdf(tmp_path, "Hello PDF.")
        repo, uploads_dir = _repo_and_uploads(tmp_path)

        result = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            repo=repo,
            uploads_dir=uploads_dir,
        )

        # Open a fresh repository against the same database
        refreshed = Repository(repo.database)
        material = refreshed.get_material(result.id)
        assert material is not None
        assert material.title == "test.pdf"
        assert material.source_type == SourceType.PDF

        paragraphs = refreshed.list_paragraphs(result.id)
        assert len(paragraphs) == 1
        assert "Hello PDF." in paragraphs[0].text

        sentences = refreshed.list_sentences(result.id)
        assert len(sentences) == 1
        assert "Hello PDF." == sentences[0].text

    def test_uploaded_file_copied_to_uploads(self, tmp_path: Path) -> None:
        _create_text_pdf(tmp_path, "Content.")
        repo, uploads_dir = _repo_and_uploads(tmp_path)

        result = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            repo=repo,
            uploads_dir=uploads_dir,
        )

        expected_copy = uploads_dir / f"{result.id}.pdf"
        assert expected_copy.exists()
        assert expected_copy.stat().st_size > 0

    def test_empty_pdf_raises_value_error(self, tmp_path: Path) -> None:
        """A PDF with no text should raise ValueError."""
        _create_text_pdf(tmp_path, "", file_name="empty.pdf")
        repo, uploads_dir = _repo_and_uploads(tmp_path)

        with pytest.raises(ValueError, match="extractable text"):
            import_pdf(
                file_path=tmp_path / "empty.pdf",
                filename="empty.pdf",
                repo=repo,
                uploads_dir=uploads_dir,
            )

    def test_idempotent_material_id(self, tmp_path: Path) -> None:
        """Re-importing the same PDF name should produce the same material_id."""
        _create_text_pdf(tmp_path, "Some text.")
        repo1, uploads_dir1 = _repo_and_uploads(tmp_path / "r1")

        result1 = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            repo=repo1,
            uploads_dir=uploads_dir1,
        )

        repo2, uploads_dir2 = _repo_and_uploads(tmp_path / "r2")
        result2 = import_pdf(
            file_path=tmp_path / "test.pdf",
            filename="test.pdf",
            repo=repo2,
            uploads_dir=uploads_dir2,
        )

        assert result1.id == result2.id

    def test_sentences_extracted_in_order(self, tmp_path: Path) -> None:
        """Multiple text blocks on a page should produce sentences in order."""
        file_path = tmp_path / "ordered.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "First sentence.", fontsize=12)
        page.insert_text((50, 80), "Second sentence.", fontsize=12)
        doc.save(str(file_path))
        doc.close()

        repo, uploads_dir = _repo_and_uploads(tmp_path)

        result = import_pdf(
            file_path=file_path,
            filename="ordered.pdf",
            repo=repo,
            uploads_dir=uploads_dir,
        )

        # Sentences should be in order
        all_sentences = [s.text for p in result.paragraphs for s in p.sentences]
        assert "First sentence." in all_sentences
        assert "Second sentence." in all_sentences


    def test_noise_lines_filtered(self, tmp_path: Path) -> None:
        """Noise lines like '上一篇' should be filtered from the imported text."""
        file_path = tmp_path / "noise.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Real content.", fontsize=12)
        page.insert_text((50, 70), "上一篇", fontsize=12)
        page.insert_text((50, 90), "More content.", fontsize=12)
        doc.save(str(file_path))
        doc.close()

        repo, uploads_dir = _repo_and_uploads(tmp_path)

        result = import_pdf(
            file_path=file_path,
            filename="noise.pdf",
            repo=repo,
            uploads_dir=uploads_dir,
        )

        # Should have filtered out "上一篇"
        all_text = " ".join(s.text for p in result.paragraphs for s in p.sentences)
        assert "上一篇" not in all_text
        assert "Real content." in all_text
        assert "More content." in all_text

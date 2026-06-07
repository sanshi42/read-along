from __future__ import annotations

from pathlib import Path

from read_along.extractors import pdf_page_texts, structure_text
from read_along.material_library import MaterialLibrary
from read_along.models import (
    MaterialDetail,
    ReadingMaterialDraft,
    ReadingMaterialDraftParagraph,
    SourceType,
)


def import_pdf(
    *,
    file_path: Path,
    filename: str,
    library: MaterialLibrary,
) -> MaterialDetail:
    """将文本型 PDF 提取为 Draft，并保存到材料库。"""
    paragraphs: list[ReadingMaterialDraftParagraph] = []
    for page_number, page_text in pdf_page_texts(str(file_path)):
        for block_number, sentences in enumerate(structure_text(page_text), start=1):
            paragraphs.append(
                ReadingMaterialDraftParagraph(
                    text=" ".join(sentences),
                    source_label=f"第 {page_number} 页，第 {block_number} 段",
                    sentences=sentences,
                )
            )

    return library.save(
        ReadingMaterialDraft(
            source_type=SourceType.PDF,
            source_uri=filename,
            title=filename,
            source_file=file_path,
            paragraphs=paragraphs,
        )
    )

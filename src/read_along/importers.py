from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from read_along.extractors import pdf_page_texts, split_sentences
from read_along.ids import generate_material_id, generate_paragraph_id, generate_sentence_id
from read_along.models import (
    AudioStatus,
    MaterialDetail,
    MaterialStatus,
    ParagraphDetail,
    Sentence,
    SourceType,
)
from read_along.repository import Repository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def import_pdf(
    *,
    file_path: Path,
    filename: str,
    repo: Repository,
    uploads_dir: Path,
) -> MaterialDetail:
    """Import a text PDF file into the reading material library.

    1. Extract text from each page.
    2. Create the material record.
    3. Create one paragraph per page.
    4. Split each paragraph into sentences and store them.
    5. Return the full MaterialDetail.
    """
    # --- Page extraction ---
    pages = pdf_page_texts(str(file_path))

    # --- Material ---
    material_id = generate_material_id("pdf", filename)
    full_text = "\n\n".join(text for _, text in pages)
    content_hash = _content_hash(full_text)
    now = _now_iso()

    repo.create_material(
        material_id=material_id,
        source_type=SourceType.PDF.value,
        source_uri=filename,
        title=filename,
        status=MaterialStatus.READY.value,
        content_hash=content_hash,
        error_message=None,
        created_at=now,
        updated_at=now,
    )

    # --- Paragraphs & sentences ---
    paragraph_details: list[ParagraphDetail] = []
    sentence_index = 0

    for page_number, page_text in pages:
        paragraph_index = page_number  # 1-based page number
        paragraph_id = generate_paragraph_id(material_id, paragraph_index)

        repo.add_paragraph(
            paragraph_id=paragraph_id,
            material_id=material_id,
            index=paragraph_index,
            text=page_text,
            source_label=f"Page {page_number}",
        )

        sentences_data = split_sentences(page_text)
        sentence_models: list[Sentence] = []

        for sent_text in sentences_data:
            sentence_index += 1
            sentence_id = generate_sentence_id(material_id, sentence_index)

            repo.add_sentence(
                sentence_id=sentence_id,
                material_id=material_id,
                paragraph_id=paragraph_id,
                index=sentence_index,
                text=sent_text,
                audio_status=AudioStatus.PENDING.value,
                audio_path=None,
                error_message=None,
            )

            sentence_models.append(
                Sentence(
                    id=sentence_id,
                    material_id=material_id,
                    paragraph_id=paragraph_id,
                    index=sentence_index,
                    text=sent_text,
                    audio_status=AudioStatus.PENDING,
                    audio_path=None,
                    error_message=None,
                )
            )

        paragraph_details.append(
            ParagraphDetail(
                id=paragraph_id,
                material_id=material_id,
                index=paragraph_index,
                text=page_text,
                source_label=f"Page {page_number}",
                sentences=sentence_models,
            )
        )

    # --- Copy uploaded file into uploads/ for preservation ---
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = uploads_dir / f"{material_id}.pdf"
    shutil.copy2(file_path, dest)

    # --- Assemble result ---
    material = repo.get_material(material_id)
    assert material is not None

    return MaterialDetail(
        id=material.id,
        source_type=material.source_type,
        source_uri=material.source_uri,
        title=material.title,
        status=material.status,
        content_hash=material.content_hash,
        error_message=material.error_message,
        created_at=material.created_at,
        updated_at=material.updated_at,
        progress=None,
        paragraphs=paragraph_details,
    )

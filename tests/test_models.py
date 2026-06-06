import pytest
from pydantic import ValidationError

from read_along.models import (
    AudioStatus,
    Material,
    MaterialDetail,
    MaterialStatus,
    ParagraphDetail,
    ReadingProgress,
    Sentence,
    SourceType,
)


def material_data() -> dict[str, object]:
    return {
        "id": "mat-1",
        "source_type": "pdf",
        "source_uri": "example.pdf",
        "title": "Example",
        "status": "ready",
        "content_hash": "hash-1",
        "error_message": None,
        "created_at": "2026-06-06T00:00:00Z",
        "updated_at": "2026-06-06T01:00:00Z",
    }


def sentence_data() -> dict[str, object]:
    return {
        "id": "sentence-1",
        "material_id": "mat-1",
        "paragraph_id": "paragraph-1",
        "index": 1,
        "text": "Sentence.",
        "audio_status": "pending",
        "audio_path": None,
        "error_message": None,
    }


def test_core_models_validate_schema_rows_and_serialize_to_json_data() -> None:
    material = Material.model_validate(material_data())
    sentence = Sentence.model_validate(sentence_data())

    assert material.source_type is SourceType.PDF
    assert material.status is MaterialStatus.READY
    assert sentence.audio_status is AudioStatus.PENDING
    assert material.model_dump(mode="json")["created_at"] == "2026-06-06T00:00:00Z"


@pytest.mark.parametrize(
    ("model", "data", "field", "invalid_value"),
    [
        (Material, material_data(), "source_type", "epub"),
        (Material, material_data(), "status", "deleted"),
        (Sentence, sentence_data(), "audio_status", "missing"),
    ],
)
def test_core_models_reject_invalid_schema_status_values(
    model: type[Material] | type[Sentence],
    data: dict[str, object],
    field: str,
    invalid_value: str,
) -> None:
    data[field] = invalid_value

    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_reading_progress_requires_positive_playback_rate() -> None:
    with pytest.raises(ValidationError):
        ReadingProgress.model_validate(
            {
                "material_id": "mat-1",
                "sentence_id": "sentence-1",
                "playback_rate": 0,
                "updated_at": "2026-06-06T00:00:00Z",
            }
        )


def test_material_detail_expresses_sentences_nested_by_paragraph() -> None:
    detail = MaterialDetail.model_validate(
        {
            **material_data(),
            "progress": None,
            "paragraphs": [
                ParagraphDetail(
                    id="paragraph-1",
                    material_id="mat-1",
                    index=1,
                    text="Paragraph.",
                    source_label="Page 1",
                    sentences=[Sentence.model_validate(sentence_data())],
                )
            ],
        }
    )

    assert detail.progress is None
    assert detail.paragraphs[0].sentences[0].id == "sentence-1"

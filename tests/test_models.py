import pytest
from pydantic import ValidationError

from read_along.models import (
    AudioStatus,
    ImportOutcome,
    Material,
    MaterialDetail,
    MaterialDetailResponse,
    MaterialImportResponse,
    MaterialImportResult,
    MaterialSource,
    ParagraphDetail,
    ReadingMaterialDraft,
    ReadingMaterialDraftParagraph,
    ReadingProgress,
    Sentence,
    SourceType,
)


def material_data() -> dict[str, object]:
    return {
        'id': 'mat-1',
        'title': 'Example',
        'content_hash': 'hash-1',
        'created_at': '2026-06-06T00:00:00Z',
        'updated_at': '2026-06-06T01:00:00Z',
    }


def source_data() -> dict[str, object]:
    return {
        'id': 'source-1',
        'material_id': 'mat-1',
        'source_type': 'pdf',
        'source_key': 'hash-source',
        'source_uri': 'example.pdf',
        'source_path': None,
        'is_primary': True,
        'created_at': '2026-06-06T00:00:00Z',
    }


def sentence_data() -> dict[str, object]:
    return {
        'id': 'sentence-1',
        'material_id': 'mat-1',
        'paragraph_id': 'paragraph-1',
        'index': 1,
        'text': 'Sentence.',
        'audio_status': 'pending',
        'audio_path': None,
        'error_message': None,
    }


def test_core_models_validate_schema_rows_and_serialize_to_json_data() -> None:
    material = Material.model_validate(material_data())
    source = MaterialSource.model_validate(source_data())
    sentence = Sentence.model_validate(sentence_data())

    assert source.source_type is SourceType.PDF
    assert sentence.audio_status is AudioStatus.PENDING
    assert material.model_dump(mode='json')['created_at'] == '2026-06-06T00:00:00Z'


@pytest.mark.parametrize(
    ('model', 'data', 'field', 'invalid_value'),
    [
        (MaterialSource, source_data(), 'source_type', 'epub'),
        (Sentence, sentence_data(), 'audio_status', 'missing'),
    ],
)
def test_core_models_reject_invalid_enum_values(
    model: type[MaterialSource] | type[Sentence],
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
                'material_id': 'mat-1',
                'sentence_id': 'sentence-1',
                'playback_rate': 0,
                'updated_at': '2026-06-06T00:00:00Z',
            }
        )


def test_material_detail_expresses_sentences_nested_by_paragraph() -> None:
    detail = MaterialDetail.model_validate(
        {
            **material_data(),
            'primary_source': source_data(),
            'sources': [source_data()],
            'progress': None,
            'paragraphs': [
                ParagraphDetail(
                    id='paragraph-1',
                    material_id='mat-1',
                    index=1,
                    text='Paragraph.',
                    source_label='Page 1',
                    sentences=[Sentence.model_validate(sentence_data())],
                )
            ],
        }
    )

    assert detail.progress is None
    assert detail.paragraphs[0].sentences[0].id == 'sentence-1'


def test_material_import_result_expresses_outcome_and_material() -> None:
    detail = MaterialDetail.model_validate(
        {
            **material_data(),
            'primary_source': source_data(),
            'sources': [source_data()],
            'progress': None,
            'paragraphs': [],
        }
    )

    result = MaterialImportResult(outcome=ImportOutcome.REUSED_SOURCE, material=detail)

    assert result.outcome is ImportOutcome.REUSED_SOURCE
    assert result.material.id == 'mat-1'
    assert result.model_dump(mode='json')['outcome'] == 'reused_source'


def test_api_material_responses_exclude_internal_audio_path() -> None:
    sentence = sentence_data()
    sentence['audio_status'] = 'failed'
    sentence['audio_path'] = 'mat-1/sentence-1.wav'
    sentence['error_message'] = '生成失败。'
    detail = MaterialDetail.model_validate(
        {
            **material_data(),
            'primary_source': source_data(),
            'sources': [source_data()],
            'progress': None,
            'paragraphs': [
                {
                    'id': 'paragraph-1',
                    'material_id': 'mat-1',
                    'index': 1,
                    'text': 'Paragraph.',
                    'source_label': None,
                    'sentences': [sentence],
                }
            ],
        }
    )
    result = MaterialImportResult(outcome=ImportOutcome.CREATED, material=detail)

    detail_data = MaterialDetailResponse.from_detail(detail).model_dump(mode='json')
    result_data = MaterialImportResponse.from_result(result).model_dump(mode='json')

    public_sentence = detail_data['paragraphs'][0]['sentences'][0]
    assert 'audio_path' not in public_sentence
    assert public_sentence['audio_status'] == 'failed'
    assert public_sentence['error_message'] == '生成失败。'
    assert result_data['material'] == detail_data


def test_reading_material_draft_excludes_persistence_fields() -> None:
    draft = ReadingMaterialDraft(
        source_type=SourceType.URL,
        source_uri='https://example.com/article',
        title='示例',
        paragraphs=[
            ReadingMaterialDraftParagraph(
                text='第一句。',
                sentences=['第一句。'],
            )
        ],
    )

    assert draft.source_file is None
    assert 'content_hash' not in draft.model_dump()

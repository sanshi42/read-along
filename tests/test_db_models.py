from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import class_mapper
from sqlmodel import SQLModel

from read_along.db_models import (
    MaterialRow,
)
from read_along.db_types import UTCDateTime

EXPECTED_TABLES = {
    'import_jobs',
    'material_sources',
    'materials',
    'paragraphs',
    'reading_progress',
    'sentences',
}


def constraint_names(table_name: str, constraint_type: type) -> set[str]:
    table = SQLModel.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type) and constraint.name is not None
    }


def index_names(table_name: str) -> set[str]:
    return {index.name for index in SQLModel.metadata.tables[table_name].indexes if index.name is not None}


def test_sqlmodel_metadata_contains_baseline_tables() -> None:
    assert set(SQLModel.metadata.tables) == EXPECTED_TABLES


def test_sqlmodel_metadata_uses_utc_datetime_for_all_time_columns() -> None:
    time_columns = {
        'materials': {'created_at', 'updated_at'},
        'material_sources': {'created_at'},
        'reading_progress': {'updated_at'},
        'import_jobs': {'created_at', 'updated_at'},
    }

    for table_name, column_names in time_columns.items():
        table = SQLModel.metadata.tables[table_name]
        assert all(isinstance(table.c[column_name].type, UTCDateTime) for column_name in column_names)


def test_sqlmodel_metadata_declares_named_database_invariants() -> None:
    assert constraint_names('materials', UniqueConstraint) == {'uq_materials_content_hash'}
    assert constraint_names('material_sources', UniqueConstraint) == {'uq_material_sources_identity'}
    assert constraint_names('paragraphs', UniqueConstraint) == {
        'uq_paragraphs_identity',
        'uq_paragraphs_material_index',
    }
    assert constraint_names('sentences', UniqueConstraint) == {
        'uq_sentences_identity',
        'uq_sentences_material_index',
    }
    assert constraint_names('material_sources', CheckConstraint) == {
        'ck_material_sources_is_primary',
        'ck_material_sources_source_type',
    }
    assert constraint_names('sentences', CheckConstraint) == {
        'ck_sentences_audio_duration_seconds',
        'ck_sentences_audio_status',
    }
    assert constraint_names('reading_progress', CheckConstraint) == {
        'ck_reading_progress_playback_completed',
        'ck_reading_progress_playback_rate',
        'ck_reading_progress_sentence_offset_seconds',
    }
    assert constraint_names('import_jobs', CheckConstraint) == {'ck_import_jobs_status'}


def test_sqlmodel_metadata_declares_composite_foreign_keys_and_partial_index() -> None:
    assert 'fk_sentences_paragraph_material' in constraint_names('sentences', ForeignKeyConstraint)
    assert 'fk_reading_progress_sentence_material' in constraint_names('reading_progress', ForeignKeyConstraint)
    assert index_names('material_sources') == {
        'ix_material_sources_material_id',
        'ix_material_sources_one_primary',
    }
    assert index_names('sentences') == {'ix_sentences_paragraph_id'}

    primary_index = next(
        index
        for index in SQLModel.metadata.tables['material_sources'].indexes
        if index.name == 'ix_material_sources_one_primary'
    )
    assert isinstance(primary_index, Index)
    assert primary_index.unique
    assert primary_index.dialect_options['sqlite']['where'] is not None


def test_material_relationships_use_passive_database_deletes() -> None:
    relationships = class_mapper(MaterialRow).relationships

    assert all(relationships[name].passive_deletes for name in ('sources', 'paragraphs', 'sentences', 'progress'))
    assert not relationships['progress'].uselist

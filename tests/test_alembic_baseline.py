from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session, SQLModel

from alembic import command
from read_along.db_models import MaterialRow

PROJECT_ROOT = Path(__file__).parents[1]
BUSINESS_TABLES = {
    'import_jobs',
    'material_sources',
    'materials',
    'paragraphs',
    'reading_progress',
    'sentences',
}


def upgrade_to_head(database: Path) -> None:
    config = Config(PROJECT_ROOT / 'alembic.ini')
    config.set_main_option('script_location', str(PROJECT_ROOT / 'alembic'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database}')
    command.upgrade(config, 'head')


def test_alembic_baseline_creates_empty_database(tmp_path: Path) -> None:
    database = tmp_path / 'baseline.sqlite3'

    upgrade_to_head(database)

    engine = create_engine(f'sqlite:///{database}')
    assert set(inspect(engine).get_table_names()) == BUSINESS_TABLES | {'alembic_version'}
    with engine.connect() as connection:
        revision = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    assert revision == '0001_sqlmodel_baseline'


def test_alembic_baseline_matches_sqlmodel_metadata(tmp_path: Path) -> None:
    database = tmp_path / 'baseline.sqlite3'
    upgrade_to_head(database)
    engine = create_engine(f'sqlite:///{database}')

    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={'compare_type': True})
        differences = compare_metadata(context, SQLModel.metadata)

    assert differences == []


def test_alembic_baseline_creates_special_sqlite_constraints(tmp_path: Path) -> None:
    database = tmp_path / 'baseline.sqlite3'
    upgrade_to_head(database)
    inspector = inspect(create_engine(f'sqlite:///{database}'))

    sentence_foreign_keys = {
        foreign_key['name']: foreign_key for foreign_key in inspector.get_foreign_keys('sentences')
    }
    progress_foreign_keys = {
        foreign_key['name']: foreign_key for foreign_key in inspector.get_foreign_keys('reading_progress')
    }
    primary_indexes = {index['name']: index for index in inspector.get_indexes('material_sources')}
    source_checks = {constraint['name'] for constraint in inspector.get_check_constraints('material_sources')}
    sentence_checks = {constraint['name'] for constraint in inspector.get_check_constraints('sentences')}
    progress_checks = {constraint['name'] for constraint in inspector.get_check_constraints('reading_progress')}
    job_checks = {constraint['name'] for constraint in inspector.get_check_constraints('import_jobs')}

    assert sentence_foreign_keys['fk_sentences_paragraph_material']['constrained_columns'] == [
        'paragraph_id',
        'material_id',
    ]
    assert progress_foreign_keys['fk_reading_progress_sentence_material']['constrained_columns'] == [
        'sentence_id',
        'material_id',
    ]
    assert primary_indexes['ix_material_sources_one_primary']['unique'] == 1
    assert primary_indexes['ix_material_sources_one_primary']['dialect_options']['sqlite_where'] is not None
    assert source_checks == {'ck_material_sources_is_primary', 'ck_material_sources_source_type'}
    assert sentence_checks == {'ck_sentences_audio_status'}
    assert progress_checks == {
        'ck_reading_progress_playback_completed',
        'ck_reading_progress_playback_rate',
    }
    assert job_checks == {'ck_import_jobs_status'}
    assert sentence_foreign_keys['fk_sentences_paragraph_material']['options']['ondelete'] == 'CASCADE'
    assert progress_foreign_keys['fk_reading_progress_sentence_material']['options']['ondelete'] == 'CASCADE'


def test_utc_datetime_survives_cross_session_round_trip(tmp_path: Path) -> None:
    database = tmp_path / 'baseline.sqlite3'
    upgrade_to_head(database)
    engine = create_engine(f'sqlite:///{database}')
    source_time = datetime(2026, 6, 10, 8, 0, tzinfo=timezone(timedelta(hours=8)))

    with Session(engine) as session:
        session.add(
            MaterialRow(
                id='mat-utc',
                title='UTC 时间',
                content_hash='a' * 64,
                created_at=source_time,
                updated_at=source_time,
            )
        )
        session.commit()

    with Session(engine) as session:
        material = session.get(MaterialRow, 'mat-utc')

    assert material is not None
    assert material.created_at == datetime(2026, 6, 10, 0, 0, tzinfo=timezone.utc)
    assert material.created_at.tzinfo is timezone.utc

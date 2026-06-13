"""建立 SQLModel baseline schema。"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0001_sqlmodel_baseline'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 SQLModel baseline schema。"""
    op.create_table(
        'materials',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('content_hash', name='uq_materials_content_hash'),
    )
    op.create_table(
        'material_sources',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('material_id', sa.String(length=64), nullable=False),
        sa.Column('source_type', sa.String(length=16), nullable=False),
        sa.Column('source_key', sa.Text(), nullable=False),
        sa.Column('source_uri', sa.Text(), nullable=False),
        sa.Column('source_path', sa.Text(), nullable=True),
        sa.Column('is_primary', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('is_primary IN (0, 1)', name='ck_material_sources_is_primary'),
        sa.CheckConstraint("source_type IN ('url', 'pdf')", name='ck_material_sources_source_type'),
        sa.ForeignKeyConstraint(
            ['material_id'],
            ['materials.id'],
            name='fk_material_sources_material_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_type', 'source_key', name='uq_material_sources_identity'),
    )
    op.create_index('ix_material_sources_material_id', 'material_sources', ['material_id'], unique=False)
    op.create_index(
        'ix_material_sources_one_primary',
        'material_sources',
        ['material_id'],
        unique=True,
        sqlite_where=sa.text('is_primary = 1'),
    )
    op.create_table(
        'paragraphs',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('material_id', sa.String(length=64), nullable=False),
        sa.Column('index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('source_label', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ['material_id'],
            ['materials.id'],
            name='fk_paragraphs_material_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'material_id', name='uq_paragraphs_identity'),
        sa.UniqueConstraint('material_id', 'index', name='uq_paragraphs_material_index'),
    )
    op.create_table(
        'sentences',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('material_id', sa.String(length=64), nullable=False),
        sa.Column('paragraph_id', sa.String(length=64), nullable=False),
        sa.Column('index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('audio_status', sa.String(length=16), nullable=False),
        sa.Column('audio_path', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "audio_status IN ('pending', 'ready', 'failed')",
            name='ck_sentences_audio_status',
        ),
        sa.ForeignKeyConstraint(
            ['material_id'],
            ['materials.id'],
            name='fk_sentences_material_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['paragraph_id', 'material_id'],
            ['paragraphs.id', 'paragraphs.material_id'],
            name='fk_sentences_paragraph_material',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'material_id', name='uq_sentences_identity'),
        sa.UniqueConstraint('material_id', 'index', name='uq_sentences_material_index'),
    )
    op.create_index('ix_sentences_paragraph_id', 'sentences', ['paragraph_id'], unique=False)
    op.create_table(
        'reading_progress',
        sa.Column('material_id', sa.String(length=64), nullable=False),
        sa.Column('sentence_id', sa.String(length=64), nullable=False),
        sa.Column('playback_rate', sa.Float(), nullable=False),
        sa.Column('playback_completed', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            'playback_completed IN (0, 1)',
            name='ck_reading_progress_playback_completed',
        ),
        sa.CheckConstraint('playback_rate > 0', name='ck_reading_progress_playback_rate'),
        sa.ForeignKeyConstraint(
            ['material_id'],
            ['materials.id'],
            name='fk_reading_progress_material_id',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['sentence_id', 'material_id'],
            ['sentences.id', 'sentences.material_id'],
            name='fk_reading_progress_sentence_material',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('material_id'),
    )
    op.create_table(
        'import_jobs',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('material_id', sa.String(length=64), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')",
            name='ck_import_jobs_status',
        ),
        sa.ForeignKeyConstraint(
            ['material_id'],
            ['materials.id'],
            name='fk_import_jobs_material_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """删除 SQLModel baseline schema。"""
    op.drop_table('import_jobs')
    op.drop_table('reading_progress')
    op.drop_index('ix_sentences_paragraph_id', table_name='sentences')
    op.drop_table('sentences')
    op.drop_table('paragraphs')
    op.drop_index('ix_material_sources_one_primary', table_name='material_sources')
    op.drop_index('ix_material_sources_material_id', table_name='material_sources')
    op.drop_table('material_sources')
    op.drop_table('materials')

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from read_along.storage import StoragePaths


SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (source_type IN ('url', 'pdf')),
    source_uri TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('importing', 'ready', 'failed')),
    content_hash TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_materials_source_uri
ON materials (source_uri);

CREATE INDEX IF NOT EXISTS idx_materials_content_hash
ON materials (content_hash);

CREATE TABLE IF NOT EXISTS paragraphs (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials (id) ON DELETE CASCADE,
    "index" INTEGER NOT NULL,
    text TEXT NOT NULL,
    source_label TEXT,
    UNIQUE (material_id, "index"),
    UNIQUE (id, material_id)
);

CREATE TABLE IF NOT EXISTS sentences (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials (id) ON DELETE CASCADE,
    paragraph_id TEXT NOT NULL,
    "index" INTEGER NOT NULL,
    text TEXT NOT NULL,
    audio_status TEXT NOT NULL CHECK (audio_status IN ('pending', 'ready', 'failed')),
    audio_path TEXT,
    error_message TEXT,
    UNIQUE (material_id, "index"),
    UNIQUE (id, material_id),
    FOREIGN KEY (paragraph_id, material_id)
        REFERENCES paragraphs (id, material_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sentences_paragraph_id
ON sentences (paragraph_id);

CREATE TABLE IF NOT EXISTS reading_progress (
    material_id TEXT PRIMARY KEY REFERENCES materials (id) ON DELETE CASCADE,
    sentence_id TEXT NOT NULL,
    playback_rate REAL NOT NULL CHECK (playback_rate > 0),
    updated_at TEXT NOT NULL,
    FOREIGN KEY (sentence_id, material_id)
        REFERENCES sentences (id, material_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS import_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    material_id TEXT REFERENCES materials (id) ON DELETE SET NULL,
    message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def connect_database(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(paths: StoragePaths) -> None:
    paths.ensure_directories()
    with closing(connect_database(paths.database)) as connection:
        connection.executescript(SCHEMA)

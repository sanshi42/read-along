import sqlite3
from contextlib import closing

from read_along.database_schema import CURRENT_SCHEMA_SQL, SchemaSupport, classify_schema


def memory_database(schema_sql: str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    if schema_sql is not None:
        connection.executescript(schema_sql)
    return connection


def previous_time_navigation_schema() -> str:
    duration_column = (
        '    audio_duration_seconds REAL CHECK (audio_duration_seconds IS NULL OR audio_duration_seconds >= 0),\n'
    )
    offset_column = '    sentence_offset_seconds REAL NOT NULL DEFAULT 0 CHECK (sentence_offset_seconds >= 0),\n'
    return CURRENT_SCHEMA_SQL.replace(duration_column, '').replace(offset_column, '')


def test_schema_policy_classifies_current_schema() -> None:
    with closing(memory_database(CURRENT_SCHEMA_SQL)) as connection:
        assert classify_schema(connection) is SchemaSupport.CURRENT


def test_schema_policy_classifies_previous_time_navigation_schema() -> None:
    with closing(memory_database(previous_time_navigation_schema())) as connection:
        assert classify_schema(connection) is SchemaSupport.PREVIOUS_TIME_NAVIGATION


def test_schema_policy_rejects_unknown_schema() -> None:
    with closing(memory_database()) as connection:
        connection.execute('CREATE TABLE unexpected (id TEXT PRIMARY KEY)')

        assert classify_schema(connection) is SchemaSupport.UNSUPPORTED

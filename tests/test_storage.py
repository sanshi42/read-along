from pathlib import Path

from read_along.config import AppConfig
from read_along.storage import StoragePaths


def test_storage_paths_are_derived_from_configured_home(tmp_path: Path) -> None:
    paths = StoragePaths.from_config(AppConfig(home=tmp_path / 'data'))

    assert paths.home == tmp_path / 'data'
    assert paths.database == tmp_path / 'data' / 'read-along.sqlite3'
    assert paths.uploads == tmp_path / 'data' / 'uploads'
    assert paths.audio == tmp_path / 'data' / 'audio'
    assert paths.models == tmp_path / 'data' / 'models'
    assert paths.logs == tmp_path / 'data' / 'logs'


def test_ensure_directories_is_idempotent_without_creating_database(tmp_path: Path) -> None:
    paths = StoragePaths.from_config(AppConfig(home=tmp_path / 'data'))

    paths.ensure_directories()
    paths.ensure_directories()

    assert paths.home.is_dir()
    assert paths.uploads.is_dir()
    assert paths.audio.is_dir()
    assert paths.models.is_dir()
    assert paths.logs.is_dir()
    assert not paths.database.exists()

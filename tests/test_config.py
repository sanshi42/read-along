from pathlib import Path

import pytest

from read_along.config import load_config


def test_load_config_uses_default_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('READ_ALONG_HOME', raising=False)

    config = load_config()

    assert config.home == Path.home() / '.local' / 'share' / 'read-along'


def test_load_config_uses_expanded_environment_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('READ_ALONG_HOME', '~/read-along-data')

    config = load_config()

    assert config.home == tmp_path / 'read-along-data'


def test_load_config_does_not_create_configured_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured_home = tmp_path / 'missing'
    monkeypatch.setenv('READ_ALONG_HOME', str(configured_home))

    config = load_config()

    assert config.home == configured_home
    assert not configured_home.exists()

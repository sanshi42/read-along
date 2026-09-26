from pathlib import Path

import pytest

from read_along.config import load_config
from read_along.tts.config import TTSConfigurationError

PROFILE_ID = 'kokoro-multi-lang-v1_1-int8'
REQUIRED_TTS_SETTINGS = (
    'READ_ALONG_TTS_MODEL',
    'READ_ALONG_TTS_VOICE_ID',
    'READ_ALONG_TTS_PROVIDER',
    'READ_ALONG_TTS_NUM_THREADS',
    'READ_ALONG_TTS_SPEED',
)


@pytest.fixture(autouse=True)
def clear_tts_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in REQUIRED_TTS_SETTINGS:
        monkeypatch.delenv(name, raising=False)


def write_config(root: Path, **overrides: str) -> None:
    values = {
        'READ_ALONG_TTS_MODEL': PROFILE_ID,
        'READ_ALONG_TTS_VOICE_ID': '3',
        'READ_ALONG_TTS_PROVIDER': 'cpu',
        'READ_ALONG_TTS_NUM_THREADS': '2',
        'READ_ALONG_TTS_SPEED': '1.0',
    }
    values.update(overrides)
    (root / '.env').write_text(
        '\n'.join(f'{name}={value}' for name, value in values.items()),
        encoding='utf-8',
    )


def test_load_config_reads_required_tts_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('READ_ALONG_HOME', raising=False)

    config = load_config()

    assert config.home == Path.home() / '.local' / 'share' / 'read-along'
    assert config.tts is not None
    assert config.tts.model == PROFILE_ID
    assert config.tts.voice_id == 3
    assert config.tts.provider == 'cpu'
    assert config.tts.num_threads == 2
    assert config.tts.speed == 1.0


def test_load_config_uses_process_environment_over_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    write_config(tmp_path, READ_ALONG_TTS_NUM_THREADS='2')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('READ_ALONG_HOME', '~/read-along-data')
    monkeypatch.setenv('READ_ALONG_TTS_NUM_THREADS', '4')

    config = load_config()

    assert config.home == Path.home() / 'read-along-data'
    assert config.tts is not None
    assert config.tts.num_threads == 4


def test_read_along_home_is_not_loaded_from_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_config(tmp_path, READ_ALONG_HOME=str(tmp_path / 'from-dotenv'))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('READ_ALONG_HOME', raising=False)

    config = load_config()

    assert config.home == Path.home() / '.local' / 'share' / 'read-along'


def test_load_config_rejects_missing_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(TTSConfigurationError, match='READ_ALONG_TTS_MODEL'):
        load_config()


@pytest.mark.parametrize(
    'missing_name',
    REQUIRED_TTS_SETTINGS,
)
def test_load_config_rejects_missing_tts_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    missing_name: str,
) -> None:
    write_config(tmp_path)
    lines = [
        line
        for line in (tmp_path / '.env').read_text(encoding='utf-8').splitlines()
        if not line.startswith(missing_name)
    ]
    (tmp_path / '.env').write_text('\n'.join(lines), encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(missing_name, raising=False)

    with pytest.raises(TTSConfigurationError, match=missing_name):
        load_config()


def test_load_config_rejects_empty_tts_setting(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_config(tmp_path, READ_ALONG_TTS_MODEL='')
    monkeypatch.chdir(tmp_path)

    with pytest.raises(TTSConfigurationError, match='READ_ALONG_TTS_MODEL'):
        load_config()


def test_load_config_rejects_unknown_model_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_config(tmp_path, READ_ALONG_TTS_MODEL='unknown-model')
    monkeypatch.chdir(tmp_path)

    with pytest.raises(TTSConfigurationError, match='unknown-model'):
        load_config()


@pytest.mark.parametrize(
    ('name', 'value'),
    [
        ('READ_ALONG_TTS_VOICE_ID', '-1'),
        ('READ_ALONG_TTS_VOICE_ID', 'not-an-int'),
        ('READ_ALONG_TTS_PROVIDER', 'metal'),
        ('READ_ALONG_TTS_NUM_THREADS', '0'),
        ('READ_ALONG_TTS_SPEED', '0'),
    ],
)
def test_load_config_rejects_invalid_tts_setting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    name: str,
    value: str,
) -> None:
    write_config(tmp_path, **{name: value})
    monkeypatch.chdir(tmp_path)

    with pytest.raises(TTSConfigurationError, match=name):
        load_config()


def test_load_config_ignores_removed_tts_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_config(
        tmp_path,
        READ_ALONG_TTS_ENGINE='openai_tts',
        READ_ALONG_TTS_OPENAI_API_KEY='obsolete-secret',
    )
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.tts is not None
    assert config.tts.model == PROFILE_ID

from pathlib import Path

import pytest

from read_along.config import load_config
from read_along.tts.config import TTSConfigurationError


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


def test_load_config_reads_project_dotenv_without_overriding_process_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / '.env'
    env_home = tmp_path / 'from-env-file'
    process_home = tmp_path / 'from-process'
    env_file.write_text(
        '\n'.join(
            [
                f'READ_ALONG_HOME={env_home}',
                'READ_ALONG_TTS_ENGINE=openai_tts',
                'READ_ALONG_TTS_OPENAI_MODEL=from-dotenv',
                'READ_ALONG_TTS_OPENAI_FORMAT=mp3',
            ]
        ),
        encoding='utf-8',
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('READ_ALONG_HOME', str(process_home))
    monkeypatch.setenv('READ_ALONG_TTS_OPENAI_MODEL', 'from-process')

    config = load_config()

    assert config.home == process_home
    assert config.tts.engine == 'openai_tts'
    assert config.tts.openai.model == 'from-process'
    assert config.tts.openai.audio_format == 'mp3'


def test_load_config_defaults_to_local_sherpa_kokoro(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for name in (
        'READ_ALONG_TTS_ENGINE',
        'READ_ALONG_TTS_SHERPA_MODEL_TYPE',
        'READ_ALONG_TTS_SHERPA_PROVIDER',
        'READ_ALONG_TTS_SHERPA_NUM_THREADS',
        'READ_ALONG_TTS_SHERPA_SPEED',
        'READ_ALONG_TTS_SHERPA_SID',
    ):
        monkeypatch.delenv(name, raising=False)

    config = load_config()

    assert config.tts.engine == 'sherpa_onnx_tts'
    assert config.tts.sherpa.model_type == 'kokoro'
    assert config.tts.sherpa.provider == 'cpu'
    assert config.tts.sherpa.num_threads == 2
    assert config.tts.sherpa.speed == 1.0
    assert config.tts.sherpa.sid == 0


def test_load_config_rejects_unsupported_openai_audio_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('READ_ALONG_TTS_ENGINE', 'openai_tts')
    monkeypatch.setenv('READ_ALONG_TTS_OPENAI_FORMAT', 'flac')

    with pytest.raises(TTSConfigurationError, match='READ_ALONG_TTS_OPENAI_FORMAT'):
        load_config()

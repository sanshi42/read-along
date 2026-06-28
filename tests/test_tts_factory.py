from __future__ import annotations

from pathlib import Path

import pytest

from read_along.tts import GeneratedAudio, TTSGenerationError, create_tts_backend
from read_along.tts.adapters.edge import EdgeTTSBackend
from read_along.tts.adapters.http_api import GPTSoVITSTTSBackend
from read_along.tts.adapters.openai_compatible import OpenAICompatibleTTSBackend
from read_along.tts.adapters.piper import PiperTTSBackend
from read_along.tts.config import GenericTTSConfig, OpenAITTSConfig, SherpaOnnxTTSConfig, TTSConfig

ALL_ENGINES = [
    'azure_tts',
    'bark_tts',
    'cartesia_tts',
    'coqui_tts',
    'cosyvoice_tts',
    'cosyvoice2_tts',
    'edge_tts',
    'elevenlabs_tts',
    'fish_api_tts',
    'gpt_sovits_tts',
    'melo_tts',
    'minimax_tts',
    'openai_tts',
    'piper_tts',
    'pyttsx3_tts',
    'siliconflow_tts',
    'spark_tts',
    'x_tts',
]


def tts_config(engine: str, values: dict[str, str] | None = None) -> TTSConfig:
    return TTSConfig(
        engine=engine,  # type: ignore[arg-type]
        sherpa=SherpaOnnxTTSConfig(),
        openai=OpenAITTSConfig(),
        generic=GenericTTSConfig(values=values or {}),
    )


@pytest.mark.parametrize('engine', ALL_ENGINES)
def test_factory_creates_non_default_backends_without_importing_optional_dependencies(engine: str) -> None:
    backend = create_tts_backend(tts_config(engine))

    assert backend.engine_id == engine
    assert backend.audio_format in {'wav', 'mp3'}
    assert isinstance(backend.fingerprint_parts(), tuple)


def test_edge_tts_backend_saves_original_text(tmp_path: Path) -> None:
    class FakeCommunicate:
        calls: list[tuple[str, str, Path]] = []

        def __init__(self, text: str, voice: str) -> None:
            self.text = text
            self.voice = voice

        def save_sync(self, file_name: str) -> None:
            path = Path(file_name)
            self.calls.append((self.text, self.voice, path))
            path.write_bytes(b'ID3edge')

    fake_module = type('FakeEdgeModule', (), {'Communicate': FakeCommunicate})
    backend = EdgeTTSBackend(voice='zh-CN-XiaoxiaoNeural', edge_module=fake_module)
    output_path = tmp_path / 'sentence.mp3'

    result = backend.generate('“原文” + emoji 😊', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='mp3', media_type='audio/mpeg')
    assert FakeCommunicate.calls == [('“原文” + emoji 😊', 'zh-CN-XiaoxiaoNeural', output_path)]


def test_optional_backend_reports_missing_dependency(tmp_path: Path) -> None:
    backend = create_tts_backend(tts_config('azure_tts'))

    with pytest.raises(TTSGenerationError, match='azure-cognitiveservices-speech'):
        backend.generate('正文。', tmp_path / 'sentence.wav')


def test_factory_uses_openai_compatible_backend() -> None:
    config = tts_config('openai_tts')

    backend = create_tts_backend(config)

    assert isinstance(backend, OpenAICompatibleTTSBackend)
    assert backend.audio_format == 'mp3'


def test_factory_uses_gpt_sovits_http_backend() -> None:
    config = tts_config('gpt_sovits_tts')

    backend = create_tts_backend(config)

    assert isinstance(backend, GPTSoVITSTTSBackend)
    assert backend.audio_format == 'wav'


def test_factory_uses_piper_backend() -> None:
    config = tts_config('piper_tts')

    backend = create_tts_backend(config)

    assert isinstance(backend, PiperTTSBackend)

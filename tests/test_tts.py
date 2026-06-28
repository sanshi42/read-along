from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from read_along.tts import TTSGenerationError
from read_along.tts.adapters.sherpa import SherpaOnnxTTSBackend
from read_along.tts.config import SherpaOnnxTTSConfig, TTSConfigurationError


@dataclass
class FakeGeneratedAudio:
    samples: list[float]
    sample_rate: int


class FakeOfflineTts:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.calls: list[tuple[str, int, float]] = []

    def generate(self, text: str, *, sid: int, speed: float) -> FakeGeneratedAudio:
        self.calls.append((text, sid, speed))
        return FakeGeneratedAudio(samples=[0.0, 0.1, -0.1], sample_rate=24000)


class FakeSherpaModule:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.created_tts: FakeOfflineTts | None = None

    class OfflineTtsKokoroModelConfig(SimpleNamespace):
        pass

    class OfflineTtsVitsModelConfig(SimpleNamespace):
        pass

    class OfflineTtsModelConfig(SimpleNamespace):
        pass

    class OfflineTtsConfig:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)
            self.model: Any = kwargs['model']
            self.max_num_sentences: object = kwargs['max_num_sentences']

        def validate(self) -> bool:
            return self.model.sherpa_module.valid

    def OfflineTts(self, config: Any) -> FakeOfflineTts:  # noqa: N802 - mirrors sherpa_onnx API
        self.created_tts = FakeOfflineTts(config)
        return self.created_tts


class FakeSoundFileModule:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, list[float], int, str]] = []

    def write(self, file: Path, data: list[float], *, samplerate: int, subtype: str) -> None:
        self.calls.append((file, data, samplerate, subtype))
        file.write_bytes(b'RIFFfake-wave')


def configured_sherpa(tmp_path: Path) -> SherpaOnnxTTSConfig:
    model = tmp_path / 'model.onnx'
    voices = tmp_path / 'voices.bin'
    tokens = tmp_path / 'tokens.txt'
    lexicon_us_en = tmp_path / 'lexicon-us-en.txt'
    lexicon_zh = tmp_path / 'lexicon-zh.txt'
    data_dir = tmp_path / 'espeak-ng-data'
    for path in (model, voices, tokens, lexicon_us_en, lexicon_zh):
        path.write_text('ok', encoding='utf-8')
    data_dir.mkdir()
    return SherpaOnnxTTSConfig(
        model_type='kokoro',
        kokoro_model=model,
        kokoro_voices=voices,
        kokoro_tokens=tokens,
        kokoro_data_dir=data_dir,
        sid=7,
        provider='cpu',
        num_threads=3,
        speed=0.85,
        debug=True,
    )


def test_sherpa_kokoro_generates_wav_from_original_sentence(tmp_path: Path) -> None:
    sherpa = FakeSherpaModule()
    soundfile = FakeSoundFileModule()
    config = configured_sherpa(tmp_path)
    output_path = tmp_path / 'sentence.wav'

    backend = SherpaOnnxTTSBackend(config, sherpa_module=sherpa, soundfile_module=soundfile)
    result = backend.generate('“事实判断”和 emoji 😊 都要原样朗读。', output_path)

    assert result.path == output_path
    assert result.audio_format == 'wav'
    assert result.media_type == 'audio/wav'
    assert output_path.read_bytes() == b'RIFFfake-wave'
    assert sherpa.created_tts is not None
    assert sherpa.created_tts.calls == [('“事实判断”和 emoji 😊 都要原样朗读。', 7, 0.85)]
    assert soundfile.calls == [(output_path, [0.0, 0.1, -0.1], 24000, 'PCM_16')]


def test_sherpa_kokoro_builds_expected_offline_config(tmp_path: Path) -> None:
    sherpa = FakeSherpaModule()
    config = configured_sherpa(tmp_path)

    SherpaOnnxTTSBackend(config, sherpa_module=sherpa, soundfile_module=FakeSoundFileModule())

    assert sherpa.created_tts is not None
    offline_config = sherpa.created_tts.config
    model_config = offline_config.model
    kokoro_config = model_config.kokoro
    assert kokoro_config.model == str(config.kokoro_model)
    assert kokoro_config.voices == str(config.kokoro_voices)
    assert kokoro_config.tokens == str(config.kokoro_tokens)
    assert kokoro_config.data_dir == str(config.kokoro_data_dir)
    assert kokoro_config.lexicon == (f'{tmp_path / "lexicon-us-en.txt"},{tmp_path / "lexicon-zh.txt"}')
    assert kokoro_config.length_scale == pytest.approx(1 / config.speed)
    assert model_config.provider == 'cpu'
    assert model_config.num_threads == 3
    assert model_config.debug is True
    assert offline_config.max_num_sentences == 1


def test_sherpa_kokoro_requires_model_paths(tmp_path: Path) -> None:
    with pytest.raises(TTSConfigurationError, match='READ_ALONG_TTS_SHERPA_KOKORO_MODEL'):
        SherpaOnnxTTSBackend(SherpaOnnxTTSConfig(kokoro_model=tmp_path / 'missing.onnx'))


def test_sherpa_kokoro_requires_multilingual_lexicons(tmp_path: Path) -> None:
    config = configured_sherpa(tmp_path)
    (tmp_path / 'lexicon-zh.txt').unlink()

    with pytest.raises(TTSConfigurationError, match='lexicon-zh.txt'):
        SherpaOnnxTTSBackend(
            config,
            sherpa_module=FakeSherpaModule(),
            soundfile_module=FakeSoundFileModule(),
        )


def test_sherpa_rejects_invalid_runtime_config(tmp_path: Path) -> None:
    sherpa = FakeSherpaModule(valid=False)

    with pytest.raises(TTSConfigurationError, match='Sherpa ONNX TTS 配置无效'):
        SherpaOnnxTTSBackend(configured_sherpa(tmp_path), sherpa_module=sherpa, soundfile_module=FakeSoundFileModule())


def test_sherpa_reports_empty_audio(tmp_path: Path) -> None:
    class EmptyOfflineTts(FakeOfflineTts):
        def generate(self, text: str, *, sid: int, speed: float) -> FakeGeneratedAudio:
            return FakeGeneratedAudio(samples=[], sample_rate=24000)

    class EmptySherpa(FakeSherpaModule):
        def OfflineTts(self, config: object) -> FakeOfflineTts:  # noqa: N802
            self.created_tts = EmptyOfflineTts(config)
            return self.created_tts

    backend = SherpaOnnxTTSBackend(
        configured_sherpa(tmp_path),
        sherpa_module=EmptySherpa(),
        soundfile_module=FakeSoundFileModule(),
    )

    with pytest.raises(TTSGenerationError, match='未生成可播放音频'):
        backend.generate('正文。', tmp_path / 'sentence.wav')

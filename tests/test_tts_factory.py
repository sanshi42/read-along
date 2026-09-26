from pathlib import Path

import pytest

from read_along.tts.adapters.sherpa import SherpaOnnxTTSBackend
from read_along.tts.config import TTSConfig
from read_along.tts.download import KokoroModelPaths
from read_along.tts.factory import create_tts_backend


def test_factory_creates_sherpa_backend_from_selected_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_dir = tmp_path / 'kokoro-multi-lang-v1_1'
    model_dir.mkdir()
    for name in ('model.int8.onnx', 'voices.bin', 'tokens.txt', 'lexicon-us-en.txt', 'lexicon-zh.txt'):
        (model_dir / name).write_text('ok', encoding='utf-8')
    (model_dir / 'espeak-ng-data').mkdir()
    paths = KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.int8.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )
    monkeypatch.setattr(SherpaOnnxTTSBackend, '_build_tts', lambda self: object())

    backend = create_tts_backend(
        TTSConfig(
            model='kokoro-multi-lang-v1_1-int8',
            voice_id=3,
            provider='cpu',
            num_threads=2,
            speed=1.0,
        ),
        paths,
    )

    assert isinstance(backend, SherpaOnnxTTSBackend)
    assert backend.config.profile == 'kokoro-multi-lang-v1_1-int8'
    assert backend.config.voice_id == 3

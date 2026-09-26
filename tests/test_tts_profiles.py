from pathlib import Path
from typing import cast

import pytest

from read_along.tts import profiles
from read_along.tts.download import DownloadProgress, KokoroModelPaths
from read_along.tts.profiles import MODEL_PROFILE_ID, UnsupportedModelProfileError


def test_model_profile_resolves_installed_kokoro_paths(tmp_path: Path) -> None:
    paths = profiles.installed_model_paths(MODEL_PROFILE_ID, tmp_path)

    assert paths.model_dir == tmp_path / 'kokoro-multi-lang-v1_1'
    assert paths.model_path == paths.model_dir / 'model.int8.onnx'


def test_model_profile_ensures_kokoro_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    expected = KokoroModelPaths(
        model_dir=tmp_path / 'kokoro-multi-lang-v1_1',
        model_path=tmp_path / 'kokoro-multi-lang-v1_1' / 'model.int8.onnx',
        voices_path=tmp_path / 'kokoro-multi-lang-v1_1' / 'voices.bin',
        tokens_path=tmp_path / 'kokoro-multi-lang-v1_1' / 'tokens.txt',
        data_dir=tmp_path / 'kokoro-multi-lang-v1_1' / 'espeak-ng-data',
    )
    calls: list[tuple[Path, bool, object | None]] = []

    def fake_download(target_dir: Path, *, restart: bool, progress: object | None) -> KokoroModelPaths:
        calls.append((target_dir, restart, progress))
        return expected

    monkeypatch.setattr(profiles, 'download_kokoro_model', fake_download)
    reporter = cast(DownloadProgress, object())

    result = profiles.ensure_model(MODEL_PROFILE_ID, tmp_path, restart=True, progress=reporter)

    assert result == expected
    assert calls == [(tmp_path, True, reporter)]


def test_model_profile_rejects_unknown_profile(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedModelProfileError, match='unknown-model'):
        profiles.ensure_model('unknown-model', tmp_path)

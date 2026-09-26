from __future__ import annotations

from pathlib import Path

from read_along.tts.download import DownloadProgress, KokoroModelPaths, download_kokoro_model

MODEL_PROFILE_ID = 'kokoro-multi-lang-v1_1-int8'
_KOKORO_INSTALL_DIR = 'kokoro-multi-lang-v1_1'
_KOKORO_MAX_VOICE_ID = 102


class UnsupportedModelProfileError(ValueError):
    """朗读模型 profile 不受支持。"""


def require_supported_profile(profile: str) -> None:
    """验证朗读模型 profile。"""
    if profile != MODEL_PROFILE_ID:
        raise UnsupportedModelProfileError(f'不支持的朗读模型 profile：{profile}')


def validate_voice_id(profile: str, voice_id: int) -> None:
    """验证 profile 支持的朗读声音编号。"""
    require_supported_profile(profile)
    if not 0 <= voice_id <= _KOKORO_MAX_VOICE_ID:
        raise ValueError(f'朗读声音编号必须在 0 到 {_KOKORO_MAX_VOICE_ID} 之间。')


def installed_model_paths(profile: str, models_root: Path) -> KokoroModelPaths:
    """返回已登记 profile 的固定本地资源路径。"""
    require_supported_profile(profile)
    model_dir = Path(models_root) / _KOKORO_INSTALL_DIR
    return KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.int8.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )


def ensure_model(
    profile: str,
    models_root: Path,
    *,
    restart: bool = False,
    progress: DownloadProgress | None = None,
) -> KokoroModelPaths:
    """确保已登记 profile 下载并安装到固定目录。"""
    require_supported_profile(profile)
    return download_kokoro_model(Path(models_root), restart=restart, progress=progress)

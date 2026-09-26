from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

from read_along.tts.profiles import UnsupportedModelProfileError, require_supported_profile, validate_voice_id

TTSProvider = Literal['cpu', 'cuda', 'coreml']


class TTSConfigurationError(ValueError):
    """朗读引擎配置无效。"""


@dataclass(frozen=True)
class TTSConfig:
    """用户可配置的朗读模型与运行参数。"""

    model: str
    voice_id: int
    provider: TTSProvider
    num_threads: int
    speed: float


@dataclass(frozen=True)
class SherpaOnnxTTSConfig:
    """Sherpa ONNX Kokoro 运行配置。"""

    profile: str
    model: Path
    voices: Path
    tokens: Path
    data_dir: Path
    voice_id: int
    provider: TTSProvider
    num_threads: int
    speed: float
    debug: bool = False


def load_tts_config(*, project_root: Path | None = None, environ: Mapping[str, str] | None = None) -> TTSConfig:
    """从项目根目录 `.env` 和进程环境加载必填朗读配置。"""
    root = project_root or Path.cwd()
    source = _read_dotenv(root / '.env')
    source.update(os.environ if environ is None else environ)

    model = _required(source, 'READ_ALONG_TTS_MODEL')
    try:
        require_supported_profile(model)
    except UnsupportedModelProfileError as exc:
        raise TTSConfigurationError(str(exc)) from exc

    voice_id = _required_int(source, 'READ_ALONG_TTS_VOICE_ID')
    try:
        validate_voice_id(model, voice_id)
    except ValueError as exc:
        raise TTSConfigurationError(f'READ_ALONG_TTS_VOICE_ID 无效：{exc}') from exc

    provider = _required(source, 'READ_ALONG_TTS_PROVIDER')
    if provider not in {'cpu', 'cuda', 'coreml'}:
        raise TTSConfigurationError(f'READ_ALONG_TTS_PROVIDER 不支持：{provider}')

    num_threads = _required_int(source, 'READ_ALONG_TTS_NUM_THREADS')
    if num_threads <= 0:
        raise TTSConfigurationError('READ_ALONG_TTS_NUM_THREADS 必须大于 0。')

    speed = _required_float(source, 'READ_ALONG_TTS_SPEED')
    if speed <= 0:
        raise TTSConfigurationError('READ_ALONG_TTS_SPEED 必须大于 0。')

    return TTSConfig(
        model=model,
        voice_id=voice_id,
        provider=provider,  # type: ignore[arg-type]
        num_threads=num_threads,
        speed=speed,
    )


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key:
            values[key] = _unquote(value.strip())
    return values


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _required(source: Mapping[str, str], name: str) -> str:
    value = source.get(name, '').strip()
    if not value:
        raise TTSConfigurationError(f'{name} 未配置或为空。')
    return value


def _required_int(source: Mapping[str, str], name: str) -> int:
    value = _required(source, name)
    try:
        return int(value)
    except ValueError as exc:
        raise TTSConfigurationError(f'{name} 必须是整数。') from exc


def _required_float(source: Mapping[str, str], name: str) -> float:
    value = _required(source, name)
    try:
        return float(value)
    except ValueError as exc:
        raise TTSConfigurationError(f'{name} 必须是数字。') from exc

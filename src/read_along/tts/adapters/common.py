from __future__ import annotations

import importlib
from pathlib import Path
from shutil import copyfile
from typing import Any

from read_along.tts.base import AudioFormat, TTSGenerationError

_SUPPORTED_FORMATS = {'wav', 'mp3'}


def optional_import(module_name: str, package_name: str) -> Any:
    """延迟导入可选 TTS 依赖。"""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise TTSGenerationError(f'缺少 TTS 依赖 `{package_name}`，请安装对应 optional extra 后重试。') from exc


def value(values: dict[str, str], name: str, default: str) -> str:
    """读取字符串配置。"""
    return values.get(f'READ_ALONG_TTS_{name}', default)


def required_value(values: dict[str, str], name: str) -> str:
    """读取必须配置的字符串。"""
    env_name = f'READ_ALONG_TTS_{name}'
    found = values.get(env_name)
    if found is None or found == '':
        raise TTSGenerationError(f'缺少 TTS 配置 `{env_name}`。')
    return found


def bool_value(values: dict[str, str], name: str, default: bool = False) -> bool:
    """读取布尔配置。"""
    raw_value = values.get(f'READ_ALONG_TTS_{name}')
    if raw_value is None or raw_value == '':
        return default
    return raw_value.lower() in {'1', 'true', 'yes', 'on'}


def int_value(values: dict[str, str], name: str, default: int) -> int:
    """读取整数配置。"""
    raw_value = values.get(f'READ_ALONG_TTS_{name}')
    if raw_value is None or raw_value == '':
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise TTSGenerationError(f'READ_ALONG_TTS_{name} 必须是整数。') from exc


def float_value(values: dict[str, str], name: str, default: float) -> float:
    """读取浮点数配置。"""
    raw_value = values.get(f'READ_ALONG_TTS_{name}')
    if raw_value is None or raw_value == '':
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise TTSGenerationError(f'READ_ALONG_TTS_{name} 必须是数字。') from exc


def audio_format_value(values: dict[str, str], name: str, default: AudioFormat) -> AudioFormat:
    """读取缓存可接受的音频格式。"""
    raw_value = value(values, name, default)
    if raw_value not in _SUPPORTED_FORMATS:
        raise TTSGenerationError(f'READ_ALONG_TTS_{name} 仅支持 wav 或 mp3：{raw_value}')
    return raw_value  # type: ignore[return-value]


def media_type_for(audio_format: AudioFormat) -> str:
    """返回音频格式对应的 HTTP media type。"""
    if audio_format == 'wav':
        return 'audio/wav'
    return 'audio/mpeg'


def fingerprint(engine_id: str, audio_format: AudioFormat, values: dict[str, str]) -> tuple[str, ...]:
    """生成包含后端配置的缓存指纹。"""
    serialized_values = tuple(f'{key}={values[key]}' for key in sorted(values))
    return (engine_id, audio_format, *serialized_values)


def copy_generated_file(source_path: str | Path, output_path: Path) -> None:
    """复制外部 TTS 服务返回的临时音频文件。"""
    source = Path(source_path)
    if not source.is_file():
        raise TTSGenerationError(f'TTS 服务没有生成音频文件：{source}')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    copyfile(source, output_path)

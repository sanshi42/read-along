from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

from read_along.tts.base import AudioFormat

TTSEngine = Literal[
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
    'sherpa_onnx_tts',
    'siliconflow_tts',
    'spark_tts',
    'x_tts',
]

_SUPPORTED_ENGINES = set(TTSEngine.__args__)  # type: ignore[attr-defined]
_SUPPORTED_FORMATS = {'wav', 'mp3'}


class TTSConfigurationError(ValueError):
    """朗读引擎配置无效。"""


@dataclass(frozen=True)
class SherpaOnnxTTSConfig:
    """Sherpa ONNX 朗读引擎配置。"""

    model_type: Literal['kokoro', 'vits'] = 'kokoro'
    kokoro_model: Path | None = None
    kokoro_voices: Path | None = None
    kokoro_tokens: Path | None = None
    kokoro_data_dir: Path | None = None
    vits_model: Path | None = None
    vits_lexicon: Path | None = None
    vits_tokens: Path | None = None
    vits_data_dir: Path | None = None
    vits_dict_dir: Path | None = None
    tts_rule_fsts: str | None = None
    sid: int = 0
    provider: Literal['cpu', 'cuda', 'coreml'] = 'cpu'
    num_threads: int = 2
    speed: float = 1.0
    debug: bool = False


@dataclass(frozen=True)
class OpenAITTSConfig:
    """OpenAI-compatible 朗读引擎配置。"""

    base_url: str = 'http://127.0.0.1:8880/v1'
    api_key: str = 'not-needed'
    model: str = 'kokoro'
    voice: str = 'af_sky'
    audio_format: AudioFormat = 'mp3'
    speed: float = 1.0


@dataclass(frozen=True)
class GenericTTSConfig:
    """非默认后端的原始环境变量配置。"""

    values: Mapping[str, str]


@dataclass(frozen=True)
class TTSConfig:
    """Read Along 朗读引擎配置。"""

    engine: TTSEngine
    sherpa: SherpaOnnxTTSConfig
    openai: OpenAITTSConfig
    generic: GenericTTSConfig


def load_tts_config(*, project_root: Path | None = None, environ: Mapping[str, str] | None = None) -> TTSConfig:
    """从进程环境变量和项目根目录 `.env` 加载朗读引擎配置。"""
    root = project_root or Path.cwd()
    values = _read_dotenv(root / '.env')
    source = dict(values)
    source.update(os.environ if environ is None else environ)

    engine = _engine(source.get('READ_ALONG_TTS_ENGINE', 'sherpa_onnx_tts'))
    return TTSConfig(
        engine=engine,
        sherpa=_sherpa_config(source),
        openai=_openai_config(source),
        generic=GenericTTSConfig(values=_prefixed_values(source)),
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
        if not key:
            continue
        values[key] = _unquote(value.strip())
    return values


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _engine(value: str) -> TTSEngine:
    if value not in _SUPPORTED_ENGINES:
        raise TTSConfigurationError(f'READ_ALONG_TTS_ENGINE 不支持：{value}')
    return value  # type: ignore[return-value]


def _sherpa_config(source: Mapping[str, str]) -> SherpaOnnxTTSConfig:
    model_type = source.get('READ_ALONG_TTS_SHERPA_MODEL_TYPE', 'kokoro')
    if model_type not in {'kokoro', 'vits'}:
        raise TTSConfigurationError(f'READ_ALONG_TTS_SHERPA_MODEL_TYPE 不支持：{model_type}')
    provider = source.get('READ_ALONG_TTS_SHERPA_PROVIDER', 'cpu')
    if provider not in {'cpu', 'cuda', 'coreml'}:
        raise TTSConfigurationError(f'READ_ALONG_TTS_SHERPA_PROVIDER 不支持：{provider}')
    return SherpaOnnxTTSConfig(
        model_type=model_type,  # type: ignore[arg-type]
        kokoro_model=_optional_path(source.get('READ_ALONG_TTS_SHERPA_KOKORO_MODEL')),
        kokoro_voices=_optional_path(source.get('READ_ALONG_TTS_SHERPA_KOKORO_VOICES')),
        kokoro_tokens=_optional_path(source.get('READ_ALONG_TTS_SHERPA_KOKORO_TOKENS')),
        kokoro_data_dir=_optional_path(source.get('READ_ALONG_TTS_SHERPA_KOKORO_DATA_DIR')),
        vits_model=_optional_path(source.get('READ_ALONG_TTS_SHERPA_VITS_MODEL')),
        vits_lexicon=_optional_path(source.get('READ_ALONG_TTS_SHERPA_VITS_LEXICON')),
        vits_tokens=_optional_path(source.get('READ_ALONG_TTS_SHERPA_VITS_TOKENS')),
        vits_data_dir=_optional_path(source.get('READ_ALONG_TTS_SHERPA_VITS_DATA_DIR')),
        vits_dict_dir=_optional_path(source.get('READ_ALONG_TTS_SHERPA_VITS_DICT_DIR')),
        tts_rule_fsts=_optional_text(source.get('READ_ALONG_TTS_SHERPA_RULE_FSTS')),
        sid=_int_value(source, 'READ_ALONG_TTS_SHERPA_SID', 0),
        provider=provider,  # type: ignore[arg-type]
        num_threads=_int_value(source, 'READ_ALONG_TTS_SHERPA_NUM_THREADS', 2),
        speed=_float_value(source, 'READ_ALONG_TTS_SHERPA_SPEED', 1.0),
        debug=_bool_value(source.get('READ_ALONG_TTS_SHERPA_DEBUG'), False),
    )


def _openai_config(source: Mapping[str, str]) -> OpenAITTSConfig:
    audio_format = source.get('READ_ALONG_TTS_OPENAI_FORMAT', 'mp3')
    if audio_format not in _SUPPORTED_FORMATS:
        raise TTSConfigurationError(f'READ_ALONG_TTS_OPENAI_FORMAT 仅支持 wav 或 mp3：{audio_format}')
    return OpenAITTSConfig(
        base_url=source.get('READ_ALONG_TTS_OPENAI_BASE_URL', 'http://127.0.0.1:8880/v1'),
        api_key=source.get('READ_ALONG_TTS_OPENAI_API_KEY', 'not-needed'),
        model=source.get('READ_ALONG_TTS_OPENAI_MODEL', 'kokoro'),
        voice=source.get('READ_ALONG_TTS_OPENAI_VOICE', 'af_sky'),
        audio_format=audio_format,  # type: ignore[arg-type]
        speed=_float_value(source, 'READ_ALONG_TTS_OPENAI_SPEED', 1.0),
    )


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser()


def _optional_text(value: str | None) -> str | None:
    return value or None


def _int_value(source: Mapping[str, str], name: str, default: int) -> int:
    value = source.get(name)
    if value is None or value == '':
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise TTSConfigurationError(f'{name} 必须是整数。') from exc


def _float_value(source: Mapping[str, str], name: str, default: float) -> float:
    value = source.get(name)
    if value is None or value == '':
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise TTSConfigurationError(f'{name} 必须是数字。') from exc


def _bool_value(value: str | None, default: bool) -> bool:
    if value is None or value == '':
        return default
    return value.lower() in {'1', 'true', 'yes', 'on'}


def _prefixed_values(source: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in source.items() if key.startswith('READ_ALONG_TTS_')}

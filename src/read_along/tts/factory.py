from __future__ import annotations

from pathlib import Path

from read_along.tts.adapters.sherpa import SherpaOnnxTTSBackend
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSBackend, TTSGenerationError
from read_along.tts.config import SherpaOnnxTTSConfig, TTSConfig, TTSConfigurationError
from read_along.tts.download import KokoroModelPaths
from read_along.tts.profiles import installed_model_paths


class LazyConfiguredTTSBackend:
    """首次生成音频时按当前配置创建 Sherpa ONNX 朗读引擎。"""

    engine_id = 'configured_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(self) -> None:
        self._backend: TTSBackend | None = None

    def _resolved(self) -> TTSBackend:
        if self._backend is None:
            from read_along.config import load_config
            from read_along.storage import StoragePaths

            config = load_config()
            if config.tts is None:
                raise TTSConfigurationError('朗读配置未加载。')
            models_root = StoragePaths.from_config(config).models / 'tts'
            self._backend = create_tts_backend(config.tts, installed_model_paths(config.tts.model, models_root))
            self.engine_id = self._backend.engine_id
            self.audio_format = self._backend.audio_format
            self.media_type = self._backend.media_type
        return self._backend

    def fingerprint_parts(self) -> tuple[str, ...]:
        return self._resolved().fingerprint_parts()

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        return self._resolved().generate(text, output_path)


def create_tts_backend(config: TTSConfig, paths: KokoroModelPaths) -> TTSBackend:
    """根据已登记 profile 的资源创建 Sherpa ONNX 朗读引擎。"""
    return SherpaOnnxTTSBackend(
        SherpaOnnxTTSConfig(
            profile=config.model,
            model=paths.model_path,
            voices=paths.voices_path,
            tokens=paths.tokens_path,
            data_dir=paths.data_dir,
            voice_id=config.voice_id,
            provider=config.provider,
            num_threads=config.num_threads,
            speed=config.speed,
        )
    )


def create_default_tts_backend() -> TTSBackend:
    """返回延迟加载的默认朗读引擎。"""
    return LazyConfiguredTTSBackend()


def normalize_tts_error(exc: Exception) -> TTSGenerationError:
    """把配置错误包装为音频生成错误。"""
    if isinstance(exc, TTSGenerationError):
        return exc
    if isinstance(exc, TTSConfigurationError):
        return TTSGenerationError(str(exc))
    return TTSGenerationError(str(exc))

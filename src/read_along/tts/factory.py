from __future__ import annotations

from pathlib import Path

from read_along.tts.adapters.azure import AzureSpeechTTSBackend
from read_along.tts.adapters.cloud_sdks import CartesiaTTSBackend, ElevenLabsTTSBackend, FishAudioTTSBackend
from read_along.tts.adapters.edge import EdgeTTSBackend
from read_along.tts.adapters.gradio import CosyVoice2TTSBackend, CosyVoiceTTSBackend, SparkTTSBackend
from read_along.tts.adapters.http_api import GPTSoVITSTTSBackend, MiniMaxTTSBackend, SiliconFlowTTSBackend, XTTSBackend
from read_along.tts.adapters.local_models import BarkTTSBackend, CoquiTTSBackend, MeloTTSBackend
from read_along.tts.adapters.openai_compatible import OpenAICompatibleTTSBackend
from read_along.tts.adapters.piper import PiperTTSBackend
from read_along.tts.adapters.pyttsx3_backend import Pyttsx3TTSBackend
from read_along.tts.adapters.sherpa import SherpaOnnxTTSBackend
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSBackend, TTSGenerationError
from read_along.tts.config import TTSConfig, TTSConfigurationError


class LazyConfiguredTTSBackend:
    """首次生成音频时按当前配置创建真实朗读引擎。"""

    engine_id = 'configured_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(self) -> None:
        self._backend: TTSBackend | None = None

    def _resolved(self) -> TTSBackend:
        if self._backend is None:
            from read_along.config import load_config

            self._backend = create_tts_backend(load_config().tts)
            self.engine_id = self._backend.engine_id
            self.audio_format = self._backend.audio_format
            self.media_type = self._backend.media_type
        return self._backend

    def fingerprint_parts(self) -> tuple[str, ...]:
        return self._resolved().fingerprint_parts()

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        return self._resolved().generate(text, output_path)


def create_tts_backend(config: TTSConfig) -> TTSBackend:
    """根据配置创建朗读引擎。"""
    if config.engine == 'sherpa_onnx_tts':
        return SherpaOnnxTTSBackend(config.sherpa)
    if config.engine == 'azure_tts':
        return AzureSpeechTTSBackend(values=dict(config.generic.values))
    if config.engine == 'bark_tts':
        return BarkTTSBackend(values=dict(config.generic.values))
    if config.engine == 'cartesia_tts':
        return CartesiaTTSBackend(values=dict(config.generic.values))
    if config.engine == 'coqui_tts':
        return CoquiTTSBackend(values=dict(config.generic.values))
    if config.engine == 'cosyvoice_tts':
        return CosyVoiceTTSBackend(values=dict(config.generic.values))
    if config.engine == 'cosyvoice2_tts':
        return CosyVoice2TTSBackend(values=dict(config.generic.values))
    if config.engine == 'edge_tts':
        return EdgeTTSBackend(voice=config.generic.values.get('READ_ALONG_TTS_EDGE_VOICE', 'zh-CN-XiaoxiaoNeural'))
    if config.engine == 'elevenlabs_tts':
        return ElevenLabsTTSBackend(values=dict(config.generic.values))
    if config.engine == 'fish_api_tts':
        return FishAudioTTSBackend(values=dict(config.generic.values))
    if config.engine == 'melo_tts':
        return MeloTTSBackend(values=dict(config.generic.values))
    if config.engine == 'openai_tts':
        return OpenAICompatibleTTSBackend(config.openai)
    if config.engine == 'gpt_sovits_tts':
        return GPTSoVITSTTSBackend(values=dict(config.generic.values))
    if config.engine == 'piper_tts':
        return PiperTTSBackend(values=dict(config.generic.values))
    if config.engine == 'siliconflow_tts':
        return SiliconFlowTTSBackend(values=dict(config.generic.values))
    if config.engine == 'minimax_tts':
        return MiniMaxTTSBackend(values=dict(config.generic.values))
    if config.engine == 'pyttsx3_tts':
        return Pyttsx3TTSBackend(values=dict(config.generic.values))
    if config.engine == 'spark_tts':
        return SparkTTSBackend(values=dict(config.generic.values))
    if config.engine == 'x_tts':
        return XTTSBackend(values=dict(config.generic.values))
    raise TTSConfigurationError(f'朗读引擎暂未实现：{config.engine}')


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

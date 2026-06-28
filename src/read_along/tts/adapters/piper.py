from __future__ import annotations

import wave
from pathlib import Path
from typing import Any

from read_along.tts.adapters.common import (
    bool_value,
    fingerprint,
    float_value,
    int_value,
    optional_import,
    required_value,
)
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError


class PiperTTSBackend:
    """Piper 本地 TTS 后端。"""

    engine_id = 'piper_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(
        self,
        *,
        values: dict[str, str] | None = None,
        piper_voice_cls: Any | None = None,
        synthesis_config_cls: Any | None = None,
    ) -> None:
        self.values = values or {}
        self._piper_voice_cls = piper_voice_cls
        self._synthesis_config_cls = synthesis_config_cls
        self._voice: Any | None = None
        self._syn_config: Any | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        voice = self._voice_instance()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with wave.open(str(output_path), 'wb') as wav_file:
                voice.synthesize_wav(text, wav_file, syn_config=self._synthesis_config())
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'Piper TTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _voice_instance(self) -> Any:
        if self._voice is None:
            model_path = required_value(self.values, 'PIPER_MODEL_PATH')
            model = Path(model_path).expanduser()
            if not model.is_file():
                raise TTSGenerationError(f'Piper 模型文件不存在：{model}')
            piper_voice_cls = self._piper_voice_cls
            if piper_voice_cls is None:
                piper_module = optional_import('piper', 'piper-tts')
                piper_voice_cls = piper_module.PiperVoice
            self._voice = piper_voice_cls.load(str(model), use_cuda=bool_value(self.values, 'PIPER_USE_CUDA', False))
        return self._voice

    def _synthesis_config(self) -> Any:
        if self._syn_config is None:
            config_cls = self._synthesis_config_cls
            if config_cls is None:
                voice_module = optional_import('piper.voice', 'piper-tts')
                config_cls = voice_module.SynthesisConfig
            self._syn_config = config_cls(
                volume=float_value(self.values, 'PIPER_VOLUME', 1.0),
                length_scale=float_value(self.values, 'PIPER_LENGTH_SCALE', 1.0),
                noise_scale=float_value(self.values, 'PIPER_NOISE_SCALE', 0.667),
                noise_w_scale=float_value(self.values, 'PIPER_NOISE_W', 0.8),
                normalize_audio=bool_value(self.values, 'PIPER_NORMALIZE_AUDIO', True),
                speaker_id=int_value(self.values, 'PIPER_SPEAKER_ID', 0),
            )
        return self._syn_config

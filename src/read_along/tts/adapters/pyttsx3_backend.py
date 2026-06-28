from __future__ import annotations

from pathlib import Path
from typing import Any

from read_along.tts.adapters.common import fingerprint, float_value, int_value, optional_import, value
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError


class Pyttsx3TTSBackend:
    """跨平台系统语音 pyttsx3 后端。"""

    engine_id = 'pyttsx3_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(self, *, values: dict[str, str] | None = None, pyttsx3_module: Any | None = None) -> None:
        self.values = values or {}
        self._pyttsx3_module = pyttsx3_module
        self._engine: Any | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            engine = self._engine_instance()
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'pyttsx3 TTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _engine_instance(self) -> Any:
        if self._engine is None:
            pyttsx3 = self._pyttsx3()
            self._engine = pyttsx3.init()
            rate = int_value(self.values, 'PYTTSX3_RATE', 0)
            volume = float_value(self.values, 'PYTTSX3_VOLUME', -1.0)
            voice = value(self.values, 'PYTTSX3_VOICE', '')
            if rate > 0:
                self._engine.setProperty('rate', rate)
            if volume >= 0:
                self._engine.setProperty('volume', volume)
            if voice:
                self._engine.setProperty('voice', voice)
        return self._engine

    def _pyttsx3(self) -> Any:
        if self._pyttsx3_module is None:
            self._pyttsx3_module = optional_import('pyttsx3', 'pyttsx3')
        return self._pyttsx3_module

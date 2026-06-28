from __future__ import annotations

from pathlib import Path
from typing import Any

from read_along.tts.adapters.common import fingerprint, optional_import, required_value, value
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError


class AzureSpeechTTSBackend:
    """Azure Speech SDK TTS 后端。"""

    engine_id = 'azure_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(self, *, values: dict[str, str] | None = None, speech_module: Any | None = None) -> None:
        self.values = values or {}
        self._speech_module = speech_module

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        speechsdk = self._speechsdk()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=required_value(self.values, 'AZURE_KEY'),
                region=required_value(self.values, 'AZURE_REGION'),
            )
            speech_config.speech_synthesis_voice_name = value(
                self.values,
                'AZURE_VOICE',
                'zh-CN-XiaoxiaoNeural',
            )
            audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output_path))
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            result = synthesizer.speak_text_async(text).get()
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'Azure TTS 生成失败：{exc}') from exc
        expected_reason = getattr(getattr(speechsdk, 'ResultReason', object), 'SynthesizingAudioCompleted', None)
        if expected_reason is not None and getattr(result, 'reason', expected_reason) != expected_reason:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'Azure TTS 生成失败，reason={getattr(result, "reason", None)}')
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _speechsdk(self) -> Any:
        if self._speech_module is None:
            self._speech_module = optional_import('azure.cognitiveservices.speech', 'azure-cognitiveservices-speech')
        return self._speech_module

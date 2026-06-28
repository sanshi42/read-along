from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from read_along.tts.adapters.common import (
    audio_format_value,
    fingerprint,
    float_value,
    media_type_for,
    optional_import,
    required_value,
    value,
)
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError

_ClientFactory = Any


class FishAudioTTSBackend:
    """Fish Audio SDK TTS 后端。"""

    engine_id = 'fish_api_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(self, *, values: dict[str, str] | None = None, fish_module: Any | None = None) -> None:
        self.values = values or {}
        self._fish_module = fish_module
        self._session: Any | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        fish = self._fish()
        request = fish.TTSRequest(
            text=text,
            reference_id=value(self.values, 'FISH_REFERENCE_ID', '7f92f8afb8ec43bf81429cc1c9199cb1'),
            latency=value(self.values, 'FISH_LATENCY', 'balanced'),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with output_path.open('wb') as handle:
                for chunk in self._session_instance().tts(request):
                    handle.write(chunk)
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'Fish Audio TTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _session_instance(self) -> Any:
        if self._session is None:
            fish = self._fish()
            self._session = fish.Session(
                apikey=required_value(self.values, 'FISH_API_KEY'),
                base_url=value(self.values, 'FISH_BASE_URL', 'https://api.fish.audio'),
            )
        return self._session

    def _fish(self) -> Any:
        if self._fish_module is None:
            self._fish_module = optional_import('fish_audio_sdk', 'fish-audio-sdk')
        return self._fish_module


class ElevenLabsTTSBackend:
    """ElevenLabs TTS 后端。"""

    engine_id = 'elevenlabs_tts'

    def __init__(self, *, values: dict[str, str] | None = None, client_factory: _ClientFactory | None = None) -> None:
        self.values = values or {}
        self.audio_format = self._audio_format()
        self.media_type = media_type_for(self.audio_format)
        self._client_factory = client_factory
        self._client: Any | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            audio = self._client_instance().text_to_speech.convert(
                text=text,
                voice_id=required_value(self.values, 'ELEVENLABS_VOICE_ID'),
                model_id=value(self.values, 'ELEVENLABS_MODEL_ID', 'eleven_multilingual_v2'),
                output_format=value(self.values, 'ELEVENLABS_OUTPUT_FORMAT', 'mp3_44100_128'),
                voice_settings={
                    'stability': float_value(self.values, 'ELEVENLABS_STABILITY', 0.5),
                    'similarity_boost': float_value(self.values, 'ELEVENLABS_SIMILARITY_BOOST', 0.5),
                    'style': float_value(self.values, 'ELEVENLABS_STYLE', 0.0),
                    'use_speaker_boost': value(self.values, 'ELEVENLABS_USE_SPEAKER_BOOST', 'true').lower() == 'true',
                },
            )
            _write_chunks(output_path, audio)
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            if isinstance(exc, TTSGenerationError):
                raise
            raise TTSGenerationError(f'ElevenLabs TTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _audio_format(self) -> AudioFormat:
        output_format = value(self.values, 'ELEVENLABS_OUTPUT_FORMAT', 'mp3_44100_128')
        if output_format.startswith('pcm') or output_format.startswith('wav'):
            return 'wav'
        return 'mp3'

    def _client_instance(self) -> Any:
        if self._client is None:
            factory = self._client_factory
            if factory is None:
                factory = optional_import('elevenlabs.client', 'elevenlabs').ElevenLabs
            self._client = factory(api_key=required_value(self.values, 'ELEVENLABS_API_KEY'))
        return self._client


class CartesiaTTSBackend:
    """Cartesia TTS 后端。"""

    engine_id = 'cartesia_tts'

    def __init__(self, *, values: dict[str, str] | None = None, client_factory: _ClientFactory | None = None) -> None:
        self.values = values or {}
        self.audio_format = audio_format_value(self.values, 'CARTESIA_FORMAT', 'wav')
        self.media_type = media_type_for(self.audio_format)
        self._client_factory = client_factory
        self._client: Any | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            audio = self._client_instance().tts.bytes(
                output_format=_cartesia_output_format(self.audio_format),
                model_id=value(self.values, 'CARTESIA_MODEL_ID', 'sonic-3'),
                transcript=text,
                language=value(self.values, 'CARTESIA_LANGUAGE', 'en'),
                generation_config={
                    'volume': float_value(self.values, 'CARTESIA_VOLUME', 1.0),
                    'speed': float_value(self.values, 'CARTESIA_SPEED', 1.0),
                    'emotion': value(self.values, 'CARTESIA_EMOTION', 'neutral'),
                },
                voice={
                    'mode': 'id',
                    'id': value(self.values, 'CARTESIA_VOICE_ID', '6ccbfb76-1fc6-48f7-b71d-91ac6298247b'),
                },
            )
            _write_chunks(output_path, audio)
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'Cartesia TTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _client_instance(self) -> Any:
        if self._client is None:
            factory = self._client_factory
            if factory is None:
                factory = optional_import('cartesia', 'cartesia').Cartesia
            self._client = factory(api_key=required_value(self.values, 'CARTESIA_API_KEY'))
        return self._client


def _write_chunks(output_path: Path, chunks: Iterable[bytes]) -> None:
    with output_path.open('wb') as handle:
        for chunk in chunks:
            handle.write(chunk)


def _cartesia_output_format(audio_format: AudioFormat) -> dict[str, int | str]:
    if audio_format == 'wav':
        return {'container': 'wav', 'sample_rate': 44100, 'encoding': 'pcm_f32le'}
    return {'container': 'mp3', 'sample_rate': 44100, 'bit_rate': 128000}

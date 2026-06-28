from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from read_along.tts.adapters.common import media_type_for, optional_import
from read_along.tts.base import GeneratedAudio, TTSGenerationError
from read_along.tts.config import OpenAITTSConfig


class OpenAIClientFactory(Protocol):
    """OpenAI 客户端工厂。"""

    def __call__(self, **kwargs: object) -> Any: ...


class OpenAICompatibleTTSBackend:
    """OpenAI 兼容 TTS API 后端。"""

    engine_id = 'openai_tts'

    def __init__(self, config: OpenAITTSConfig, *, client_factory: OpenAIClientFactory | None = None) -> None:
        self.config = config
        self.audio_format = config.audio_format
        self.media_type = media_type_for(config.audio_format)
        self._client_factory = client_factory
        self._client: Any | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return (
            self.engine_id,
            self.audio_format,
            f'base_url={self.config.base_url}',
            f'model={self.config.model}',
            f'voice={self.config.voice}',
            f'speed={self.config.speed}',
        )

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        client = self._client_instance()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with client.audio.speech.with_streaming_response.create(
                model=self.config.model,
                voice=self.config.voice,
                input=text,
                response_format=self.audio_format,
                speed=self.config.speed,
            ) as response:
                response.stream_to_file(output_path)
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'OpenAI 兼容 TTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _client_instance(self) -> Any:
        if self._client is None:
            factory = self._client_factory
            if factory is None:
                openai_module = optional_import('openai', 'openai')
                factory = openai_module.OpenAI
            self._client = factory(api_key=self.config.api_key, base_url=self.config.base_url)
        return self._client

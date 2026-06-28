from __future__ import annotations

from pathlib import Path
from typing import Any

from read_along.tts.adapters.common import (
    bool_value,
    copy_generated_file,
    fingerprint,
    float_value,
    int_value,
    optional_import,
    value,
)
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError


class _GradioTTSBackend:
    engine_id: str
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(self, *, values: dict[str, str] | None = None, gradio_module: Any | None = None) -> None:
        self.values = values or {}
        self._gradio_module = gradio_module
        self._client: Any | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        try:
            source_path = self._predict(text)
            copy_generated_file(_first_path(source_path), output_path)
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            if isinstance(exc, TTSGenerationError):
                raise
            raise TTSGenerationError(f'{self.engine_id} 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _predict(self, text: str) -> object:
        raise NotImplementedError

    def _client_instance(self, client_url: str) -> Any:
        if self._client is None:
            self._client = self._gradio().Client(client_url)
        return self._client

    def _gradio(self) -> Any:
        if self._gradio_module is None:
            self._gradio_module = optional_import('gradio_client', 'gradio-client')
        return self._gradio_module


class CosyVoiceTTSBackend(_GradioTTSBackend):
    """CosyVoice Gradio 后端。"""

    engine_id = 'cosyvoice_tts'

    def _predict(self, text: str) -> object:
        gradio = self._gradio()
        client = self._client_instance(value(self.values, 'COSYVOICE_CLIENT_URL', 'http://127.0.0.1:50000/'))
        return client.predict(
            tts_text=text,
            mode_checkbox_group=value(self.values, 'COSYVOICE_MODE', '预训练音色'),
            sft_dropdown=value(self.values, 'COSYVOICE_SFT', '中文女'),
            prompt_text=value(self.values, 'COSYVOICE_PROMPT_TEXT', ''),
            prompt_wav_upload=gradio.file(
                value(
                    self.values,
                    'COSYVOICE_PROMPT_WAV_UPLOAD',
                    'https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav',
                )
            ),
            prompt_wav_record=gradio.file(
                value(
                    self.values,
                    'COSYVOICE_PROMPT_WAV_RECORD',
                    'https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav',
                )
            ),
            instruct_text=value(self.values, 'COSYVOICE_INSTRUCT_TEXT', ''),
            seed=int_value(self.values, 'COSYVOICE_SEED', 0),
            api_name=value(self.values, 'COSYVOICE_API_NAME', '/generate_audio'),
        )


class CosyVoice2TTSBackend(_GradioTTSBackend):
    """CosyVoice2 Gradio 后端。"""

    engine_id = 'cosyvoice2_tts'

    def _predict(self, text: str) -> object:
        gradio = self._gradio()
        client = self._client_instance(value(self.values, 'COSYVOICE2_CLIENT_URL', 'http://127.0.0.1:50000/'))
        handle_file = getattr(gradio, 'handle_file', None) or gradio.file
        return client.predict(
            tts_text=text,
            mode_checkbox_group=value(self.values, 'COSYVOICE2_MODE', '预训练音色'),
            sft_dropdown=value(self.values, 'COSYVOICE2_SFT', '中文女'),
            prompt_text=value(self.values, 'COSYVOICE2_PROMPT_TEXT', ''),
            prompt_wav_upload=handle_file(
                value(
                    self.values,
                    'COSYVOICE2_PROMPT_WAV_UPLOAD',
                    'https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav',
                )
            ),
            prompt_wav_record=handle_file(
                value(
                    self.values,
                    'COSYVOICE2_PROMPT_WAV_RECORD',
                    'https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav',
                )
            ),
            instruct_text=value(self.values, 'COSYVOICE2_INSTRUCT_TEXT', ''),
            stream=bool_value(self.values, 'COSYVOICE2_STREAM', False),
            seed=int_value(self.values, 'COSYVOICE2_SEED', 0),
            speed=float_value(self.values, 'COSYVOICE2_SPEED', 1.0),
            api_name=value(self.values, 'COSYVOICE2_API_NAME', '/generate_audio'),
        )


class SparkTTSBackend(_GradioTTSBackend):
    """Spark TTS Gradio 后端。"""

    engine_id = 'spark_tts'

    def _predict(self, text: str) -> object:
        gradio = self._gradio()
        client = self._client_instance(value(self.values, 'SPARK_API_URL', 'http://127.0.0.1:7860/'))
        api_name = value(self.values, 'SPARK_API_NAME', 'voice_clone')
        if api_name == 'voice_clone':
            return client.predict(
                text=text,
                prompt_text=value(self.values, 'SPARK_PROMPT_TEXT', ''),
                prompt_wav_upload=gradio.file(value(self.values, 'SPARK_PROMPT_WAV_UPLOAD', 'voice_clone/voice.wav')),
                prompt_wav_record=None,
                api_name='/voice_clone',
            )
        if api_name == 'voice_creation':
            return client.predict(
                text=text,
                gender=value(self.values, 'SPARK_GENDER', 'male'),
                pitch=int_value(self.values, 'SPARK_PITCH', 3),
                speed=int_value(self.values, 'SPARK_SPEED', 3),
                api_name='/voice_creation',
            )
        raise TTSGenerationError(f'READ_ALONG_TTS_SPARK_API_NAME 不支持：{api_name}')


def _first_path(result: object) -> str | Path:
    if isinstance(result, str | Path):
        return result
    if isinstance(result, list | tuple) and result:
        return _first_path(result[0])
    raise TTSGenerationError(f'TTS 服务返回了无法识别的音频路径：{result!r}')

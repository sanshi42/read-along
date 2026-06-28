from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from read_along.tts.adapters.common import (
    audio_format_value,
    fingerprint,
    float_value,
    int_value,
    media_type_for,
    optional_import,
    required_value,
    value,
)
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError


class _HTTPBackend:
    engine_id: str

    def __init__(self, *, values: dict[str, str] | None = None, requests_module: Any | None = None) -> None:
        self.values = values or {}
        self._requests_module = requests_module
        self.audio_format = self._audio_format()
        self.media_type = media_type_for(self.audio_format)

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def _audio_format(self) -> AudioFormat:
        return 'wav'

    def _requests(self) -> Any:
        if self._requests_module is None:
            self._requests_module = optional_import('requests', 'requests')
        return self._requests_module

    def _write_response_content(self, response: Any, output_path: Path, *, status_message: str) -> GeneratedAudio:
        if response.status_code != 200:
            details = getattr(response, 'text', '')
            raise TTSGenerationError(f'{status_message}，HTTP {response.status_code}：{details}')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)


class GPTSoVITSTTSBackend(_HTTPBackend):
    """GPT-SoVITS HTTP API 后端。"""

    engine_id = 'gpt_sovits_tts'

    def _audio_format(self) -> AudioFormat:
        return audio_format_value(self.values, 'GPT_SOVITS_MEDIA_TYPE', 'wav')

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        params = {
            'text': text,
            'text_lang': value(self.values, 'GPT_SOVITS_TEXT_LANG', 'zh'),
            'ref_audio_path': value(self.values, 'GPT_SOVITS_REF_AUDIO_PATH', ''),
            'prompt_lang': value(self.values, 'GPT_SOVITS_PROMPT_LANG', 'zh'),
            'prompt_text': value(self.values, 'GPT_SOVITS_PROMPT_TEXT', ''),
            'text_split_method': value(self.values, 'GPT_SOVITS_TEXT_SPLIT_METHOD', 'cut5'),
            'batch_size': value(self.values, 'GPT_SOVITS_BATCH_SIZE', '1'),
            'media_type': self.audio_format,
            'streaming_mode': value(self.values, 'GPT_SOVITS_STREAMING_MODE', 'false'),
        }
        response = self._requests().get(
            value(self.values, 'GPT_SOVITS_API_URL', 'http://127.0.0.1:9880/tts'),
            params=params,
            timeout=int_value(self.values, 'GPT_SOVITS_TIMEOUT_SECONDS', 120),
        )
        return self._write_response_content(response, output_path, status_message='GPT-SoVITS TTS 生成失败')


class XTTSBackend(_HTTPBackend):
    """X-TTS HTTP API 后端。"""

    engine_id = 'x_tts'

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        payload = {
            'text': text,
            'speaker_wav': value(self.values, 'X_TTS_SPEAKER_WAV', 'female'),
            'language': value(self.values, 'X_TTS_LANGUAGE', 'en'),
        }
        response = self._requests().post(
            value(self.values, 'X_TTS_API_URL', 'http://127.0.0.1:8020/tts_to_audio'),
            json=payload,
            timeout=int_value(self.values, 'X_TTS_TIMEOUT_SECONDS', 120),
        )
        return self._write_response_content(response, output_path, status_message='X-TTS 生成失败')


class SiliconFlowTTSBackend(_HTTPBackend):
    """SiliconFlow TTS API 后端。"""

    engine_id = 'siliconflow_tts'

    def _audio_format(self) -> AudioFormat:
        return audio_format_value(self.values, 'SILICONFLOW_FORMAT', 'mp3')

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        payload = {
            'input': text,
            'response_format': self.audio_format,
            'sample_rate': int_value(self.values, 'SILICONFLOW_SAMPLE_RATE', 32000),
            'stream': value(self.values, 'SILICONFLOW_STREAM', 'false').lower() == 'true',
            'speed': float_value(self.values, 'SILICONFLOW_SPEED', 1.0),
            'gain': float_value(self.values, 'SILICONFLOW_GAIN', 0.0),
            'model': value(self.values, 'SILICONFLOW_MODEL', 'FunAudioLLM/CosyVoice2-0.5B'),
            'voice': value(self.values, 'SILICONFLOW_VOICE', 'FunAudioLLM/CosyVoice2-0.5B:alex'),
        }
        headers = {
            'Authorization': f'Bearer {required_value(self.values, "SILICONFLOW_API_KEY")}',
            'Content-Type': 'application/json',
        }
        response = self._requests().request(
            'POST',
            value(self.values, 'SILICONFLOW_API_URL', 'https://api.siliconflow.cn/v1/audio/speech'),
            json=payload,
            headers=headers,
            timeout=int_value(self.values, 'SILICONFLOW_TIMEOUT_SECONDS', 120),
        )
        return self._write_response_content(response, output_path, status_message='SiliconFlow TTS 生成失败')


class MiniMaxTTSBackend(_HTTPBackend):
    """MiniMax TTS API 后端。"""

    engine_id = 'minimax_tts'

    def _audio_format(self) -> AudioFormat:
        return 'mp3'

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        url = f'{value(self.values, "MINIMAX_API_HOST", "https://api.minimax.chat")}/v1/t2a_v2'
        headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'authorization': f'Bearer {required_value(self.values, "MINIMAX_API_KEY")}',
        }
        body = {
            'model': value(self.values, 'MINIMAX_MODEL', 'speech-02-turbo'),
            'text': text,
            'stream': True,
            'voice_setting': {
                'voice_id': value(self.values, 'MINIMAX_VOICE_ID', 'male-qn-qingse'),
                'speed': float_value(self.values, 'MINIMAX_SPEED', 1.0),
                'vol': float_value(self.values, 'MINIMAX_VOLUME', 1.0),
                'pitch': int_value(self.values, 'MINIMAX_PITCH', 0),
            },
            'pronunciation_dict': _json_value(self.values, 'MINIMAX_PRONUNCIATION_DICT', {'tone': []}),
            'audio_setting': {
                'sample_rate': int_value(self.values, 'MINIMAX_SAMPLE_RATE', 32000),
                'bitrate': int_value(self.values, 'MINIMAX_BITRATE', 128000),
                'format': self.audio_format,
                'channel': int_value(self.values, 'MINIMAX_CHANNELS', 1),
            },
        }
        response = self._requests().request(
            'POST',
            url,
            params={'GroupId': required_value(self.values, 'MINIMAX_GROUP_ID')},
            stream=True,
            headers=headers,
            data=json.dumps(body, ensure_ascii=False),
            timeout=int_value(self.values, 'MINIMAX_TIMEOUT_SECONDS', 120),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(_minimax_audio_bytes(response))
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)


def _json_value(values: dict[str, str], name: str, default: object) -> object:
    raw_value = values.get(f'READ_ALONG_TTS_{name}')
    if raw_value is None or raw_value == '':
        return default
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise TTSGenerationError(f'READ_ALONG_TTS_{name} 必须是 JSON。') from exc


def _minimax_audio_bytes(response: Any) -> bytes:
    if getattr(response, 'status_code', 200) >= 400:
        details = getattr(response, 'text', '')
        raise TTSGenerationError(f'MiniMax TTS 生成失败，HTTP {response.status_code}：{details}')
    audio = bytearray()
    for chunk in response.raw:
        if not chunk or not chunk.startswith(b'data:'):
            continue
        try:
            data = json.loads(chunk[5:])
        except json.JSONDecodeError as exc:
            raise TTSGenerationError(f'MiniMax TTS 返回了无效 JSON：{exc}') from exc
        hex_audio = data.get('data', {}).get('audio')
        if hex_audio:
            audio.extend(bytes.fromhex(hex_audio))
    if not audio:
        raise TTSGenerationError('MiniMax TTS 没有返回音频数据。')
    return bytes(audio)

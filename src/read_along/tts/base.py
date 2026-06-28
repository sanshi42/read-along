from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

AudioFormat = Literal['wav', 'mp3']


class TTSGenerationError(RuntimeError):
    """单句音频生成失败。"""


@dataclass(frozen=True)
class GeneratedAudio:
    """朗读引擎生成的本地音频。"""

    path: Path
    audio_format: AudioFormat
    media_type: str


@dataclass(frozen=True)
class CachedAudio:
    """材料库中可播放的缓存音频。"""

    path: Path
    audio_format: AudioFormat
    media_type: str
    duration_seconds: float


class TTSBackend(Protocol):
    """可替换朗读引擎的最小协议。"""

    engine_id: str
    audio_format: AudioFormat
    media_type: str

    def fingerprint_parts(self) -> tuple[str, ...]:
        """返回影响音频输出的稳定配置片段。"""

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        """为单个句子生成本地音频文件。"""

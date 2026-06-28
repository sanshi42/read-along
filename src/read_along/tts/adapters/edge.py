from __future__ import annotations

from pathlib import Path
from typing import Any

from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError


class EdgeTTSBackend:
    """使用 edge-tts 生成 MP3 音频。"""

    engine_id = 'edge_tts'
    audio_format: AudioFormat = 'mp3'
    media_type = 'audio/mpeg'

    def __init__(self, *, voice: str = 'zh-CN-XiaoxiaoNeural', edge_module: Any | None = None) -> None:
        self.voice = voice
        self._edge_module = edge_module

    def fingerprint_parts(self) -> tuple[str, ...]:
        return (self.engine_id, self.voice, self.audio_format)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        output_path = Path(output_path)
        if output_path.suffix.lower() != '.mp3':
            raise TTSGenerationError('Edge TTS 目标音频路径必须使用 .mp3 扩展名。')
        edge_module = self._edge_module or _import_edge_tts()
        try:
            edge_module.Communicate(text, self.voice).save_sync(str(output_path))
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'Edge TTS 生成音频失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)


def _import_edge_tts() -> Any:
    try:
        import edge_tts

        return edge_tts
    except ImportError as exc:
        raise TTSGenerationError('缺少 TTS 依赖 `edge-tts`，请安装 `read-along[edge-tts]` 后重试。') from exc

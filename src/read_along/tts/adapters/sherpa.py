from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError
from read_along.tts.config import SherpaOnnxTTSConfig, TTSConfigurationError


class SherpaOnnxTTSBackend:
    """使用 Sherpa ONNX 在本机生成 WAV 音频。"""

    engine_id = 'sherpa_onnx_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(
        self,
        config: SherpaOnnxTTSConfig,
        *,
        sherpa_module: Any | None = None,
        soundfile_module: Any | None = None,
    ) -> None:
        self.config = config
        self._validate_model_paths()
        self._kokoro_lexicon = _kokoro_lexicon(config)
        self._sherpa = sherpa_module or _import_required('sherpa_onnx', 'sherpa-onnx')
        self._soundfile = soundfile_module or _import_required('soundfile', 'soundfile')
        self._tts = self._build_tts()

    def fingerprint_parts(self) -> tuple[str, ...]:
        return (
            self.engine_id,
            self.config.profile,
            str(self.config.model),
            str(self.config.voices),
            str(self.config.tokens),
            str(self.config.data_dir),
            self._kokoro_lexicon,
            str(self.config.voice_id),
            self.config.provider,
            f'{self.config.speed:g}',
            self.audio_format,
        )

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        output_path = Path(output_path)
        if not text.strip():
            raise TTSGenerationError('句子文本不能为空。')
        if output_path.suffix.lower() != '.wav':
            raise TTSGenerationError('Sherpa ONNX TTS 目标音频路径必须使用 .wav 扩展名。')
        if output_path.exists() or output_path.is_symlink():
            raise TTSGenerationError(f'目标音频已存在：{output_path}')
        if not output_path.parent.is_dir():
            raise TTSGenerationError(f'目标音频父目录不存在或不是目录：{output_path.parent}')

        try:
            audio = self._tts.generate(text, sid=self.config.voice_id, speed=self.config.speed)
        except Exception as exc:
            raise TTSGenerationError(f'Sherpa ONNX TTS 生成音频失败：{exc}') from exc
        if len(audio.samples) == 0:
            raise TTSGenerationError('Sherpa ONNX TTS 未生成可播放音频。')
        try:
            self._soundfile.write(
                output_path,
                audio.samples,
                samplerate=audio.sample_rate,
                subtype='PCM_16',
            )
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError('无法保存 Sherpa ONNX TTS 生成的 WAV 音频。') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _build_tts(self) -> Any:
        offline_config = self._offline_config()
        try:
            valid = offline_config.validate()
        except Exception as exc:
            raise TTSConfigurationError(f'无法校验 Sherpa ONNX TTS 模型：{exc}') from exc
        if not valid:
            raise TTSConfigurationError('Sherpa ONNX TTS 配置无效。')
        try:
            return self._sherpa.OfflineTts(offline_config)
        except Exception as exc:
            raise TTSConfigurationError(f'无法加载 Sherpa ONNX TTS 模型：{exc}') from exc

    def _validate_model_paths(self) -> None:
        _required_path(self.config.model)
        _required_path(self.config.voices)
        _required_path(self.config.tokens)
        _required_path(self.config.data_dir)

    def _offline_config(self) -> Any:
        kokoro_config = self._sherpa.OfflineTtsKokoroModelConfig(
            model=str(_required_path(self.config.model)),
            voices=str(_required_path(self.config.voices)),
            tokens=str(_required_path(self.config.tokens)),
            data_dir=str(_required_path(self.config.data_dir)),
            lexicon=self._kokoro_lexicon,
            length_scale=1 / self.config.speed,
        )
        model_config = self._sherpa.OfflineTtsModelConfig(
            kokoro=kokoro_config,
            provider=self.config.provider,
            num_threads=self.config.num_threads,
            debug=self.config.debug,
        )
        try:
            model_config.sherpa_module = self._sherpa
        except AttributeError:
            pass
        return self._sherpa.OfflineTtsConfig(
            model=model_config,
            max_num_sentences=1,
        )


def _required_path(path: Path) -> Path:
    if not path.exists():
        raise TTSConfigurationError(f'朗读模型资源路径不存在：{path}')
    return path


def _kokoro_lexicon(config: SherpaOnnxTTSConfig) -> str:
    model = _required_path(config.model)
    lexicon_paths = (
        model.parent / 'lexicon-us-en.txt',
        model.parent / 'lexicon-zh.txt',
    )
    for path in lexicon_paths:
        _required_path(path)
    return ','.join(str(path) for path in lexicon_paths)


def _import_required(module_name: str, package_name: str) -> ModuleType:
    try:
        import importlib

        return importlib.import_module(module_name)
    except ImportError as exc:
        raise TTSConfigurationError(f'缺少 TTS 依赖 `{package_name}`，请安装对应依赖后重试。') from exc

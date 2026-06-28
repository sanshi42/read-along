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
        self._kokoro_lexicon = _kokoro_lexicon(config) if config.model_type == 'kokoro' else None
        self._sherpa = sherpa_module or _import_required('sherpa_onnx', 'sherpa-onnx')
        self._soundfile = soundfile_module or _import_required('soundfile', 'soundfile')
        self._tts = self._build_tts()

    def fingerprint_parts(self) -> tuple[str, ...]:
        if self.config.model_type == 'kokoro':
            return (
                self.engine_id,
                'kokoro',
                str(self.config.kokoro_model),
                str(self.config.kokoro_voices),
                str(self.config.kokoro_tokens),
                str(self.config.kokoro_data_dir),
                str(self._kokoro_lexicon),
                str(self.config.sid),
                self.config.provider,
                f'{self.config.speed:g}',
                self.audio_format,
            )
        return (
            self.engine_id,
            'vits',
            str(self.config.vits_model),
            str(self.config.vits_lexicon),
            str(self.config.vits_tokens),
            str(self.config.vits_data_dir),
            str(self.config.vits_dict_dir),
            str(self.config.tts_rule_fsts),
            str(self.config.sid),
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
            audio = self._tts.generate(text, sid=self.config.sid, speed=self.config.speed)
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
        if not offline_config.validate():
            raise TTSConfigurationError('Sherpa ONNX TTS 配置无效。')
        return self._sherpa.OfflineTts(offline_config)

    def _validate_model_paths(self) -> None:
        if self.config.model_type == 'kokoro':
            _required_path(self.config.kokoro_model, 'READ_ALONG_TTS_SHERPA_KOKORO_MODEL')
            _required_path(self.config.kokoro_voices, 'READ_ALONG_TTS_SHERPA_KOKORO_VOICES')
            _required_path(self.config.kokoro_tokens, 'READ_ALONG_TTS_SHERPA_KOKORO_TOKENS')
            _required_path(self.config.kokoro_data_dir, 'READ_ALONG_TTS_SHERPA_KOKORO_DATA_DIR')
        else:
            _required_path(self.config.vits_model, 'READ_ALONG_TTS_SHERPA_VITS_MODEL')
            _required_path(self.config.vits_tokens, 'READ_ALONG_TTS_SHERPA_VITS_TOKENS')

    def _offline_config(self) -> Any:
        if self.config.model_type == 'kokoro':
            model = _required_path(self.config.kokoro_model, 'READ_ALONG_TTS_SHERPA_KOKORO_MODEL')
            voices = _required_path(self.config.kokoro_voices, 'READ_ALONG_TTS_SHERPA_KOKORO_VOICES')
            tokens = _required_path(self.config.kokoro_tokens, 'READ_ALONG_TTS_SHERPA_KOKORO_TOKENS')
            data_dir = _required_path(self.config.kokoro_data_dir, 'READ_ALONG_TTS_SHERPA_KOKORO_DATA_DIR')
            kokoro_config = self._sherpa.OfflineTtsKokoroModelConfig(
                model=str(model),
                voices=str(voices),
                tokens=str(tokens),
                data_dir=str(data_dir),
                lexicon=str(self._kokoro_lexicon),
                length_scale=1 / self.config.speed,
            )
            model_config = self._sherpa.OfflineTtsModelConfig(
                kokoro=kokoro_config,
                provider=self.config.provider,
                num_threads=self.config.num_threads,
                debug=self.config.debug,
            )
        else:
            model = _required_path(self.config.vits_model, 'READ_ALONG_TTS_SHERPA_VITS_MODEL')
            tokens = _required_path(self.config.vits_tokens, 'READ_ALONG_TTS_SHERPA_VITS_TOKENS')
            vits_config = self._sherpa.OfflineTtsVitsModelConfig(
                model=str(model),
                lexicon=str(self.config.vits_lexicon or ''),
                tokens=str(tokens),
                data_dir=str(self.config.vits_data_dir or ''),
                dict_dir=str(self.config.vits_dict_dir or ''),
                length_scale=1 / self.config.speed,
            )
            model_config = self._sherpa.OfflineTtsModelConfig(
                vits=vits_config,
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
            rule_fsts=self.config.tts_rule_fsts or '',
            max_num_sentences=1,
        )


def _required_path(path: Path | None, variable_name: str) -> Path:
    if path is None:
        raise TTSConfigurationError(f'{variable_name} 未配置。')
    if not path.exists():
        raise TTSConfigurationError(f'{variable_name} 指向的路径不存在：{path}')
    return path


def _kokoro_lexicon(config: SherpaOnnxTTSConfig) -> str:
    model = _required_path(config.kokoro_model, 'READ_ALONG_TTS_SHERPA_KOKORO_MODEL')
    lexicon_paths = (
        model.parent / 'lexicon-us-en.txt',
        model.parent / 'lexicon-zh.txt',
    )
    for path in lexicon_paths:
        _required_path(path, f'Kokoro 多语种词典 {path.name}')
    return ','.join(str(path) for path in lexicon_paths)


def _import_required(module_name: str, package_name: str) -> ModuleType:
    try:
        import importlib

        return importlib.import_module(module_name)
    except ImportError as exc:
        raise TTSConfigurationError(f'缺少 TTS 依赖 `{package_name}`，请安装对应依赖后重试。') from exc

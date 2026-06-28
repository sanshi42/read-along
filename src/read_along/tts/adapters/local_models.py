from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from read_along.tts.adapters.common import fingerprint, float_value, optional_import, value
from read_along.tts.base import AudioFormat, GeneratedAudio, TTSGenerationError


class _TTSFactory(Protocol):
    def __call__(self, **kwargs: object) -> Any: ...


class BarkTTSBackend:
    """Bark 本地 TTS 后端。"""

    engine_id = 'bark_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(
        self,
        *,
        values: dict[str, str] | None = None,
        bark_module: Any | None = None,
        wavfile_module: Any | None = None,
    ) -> None:
        self.values = values or {}
        self._bark_module = bark_module
        self._wavfile_module = wavfile_module
        self._models_loaded = False

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        bark = self._bark()
        wavfile = self._wavfile()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not self._models_loaded:
                bark.preload_models()
                self._models_loaded = True
            audio = bark.generate_audio(text, history_prompt=value(self.values, 'BARK_VOICE', 'v2/en_speaker_1'))
            wavfile.write(output_path, bark.SAMPLE_RATE, audio)
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'Bark TTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _bark(self) -> Any:
        if self._bark_module is None:
            self._bark_module = optional_import('bark', 'bark')
        return self._bark_module

    def _wavfile(self) -> Any:
        if self._wavfile_module is None:
            self._wavfile_module = optional_import('scipy.io.wavfile', 'scipy')
        return self._wavfile_module


class CoquiTTSBackend:
    """Coqui TTS 本地模型后端。"""

    engine_id = 'coqui_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(self, *, values: dict[str, str] | None = None, tts_factory: _TTSFactory | None = None) -> None:
        self.values = values or {}
        self._tts_factory = tts_factory
        self._model: Any | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            model = self._model_instance()
            speaker_wav = value(self.values, 'COQUI_SPEAKER_WAV', '')
            language = value(self.values, 'COQUI_LANGUAGE', 'en')
            if getattr(model, 'speakers', None) is not None and speaker_wav:
                model.tts_to_file(text=text, speaker_wav=speaker_wav, language=language, file_path=str(output_path))
            else:
                model.tts_to_file(text=text, file_path=str(output_path))
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'Coqui TTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _model_instance(self) -> Any:
        if self._model is None:
            factory = self._tts_factory
            if factory is None:
                factory = optional_import('TTS.api', 'coqui-tts').TTS
            model_name = value(self.values, 'COQUI_MODEL_NAME', '')
            model = factory(model_name=model_name) if model_name else factory()
            device = value(self.values, 'COQUI_DEVICE', 'cpu')
            self._model = model.to(device) if hasattr(model, 'to') else model
        return self._model


class MeloTTSBackend:
    """MeloTTS 本地模型后端。"""

    engine_id = 'melo_tts'
    audio_format: AudioFormat = 'wav'
    media_type = 'audio/wav'

    def __init__(self, *, values: dict[str, str] | None = None, tts_factory: _TTSFactory | None = None) -> None:
        self.values = values or {}
        self._tts_factory = tts_factory
        self._model: Any | None = None
        self._speaker_id: int | None = None

    def fingerprint_parts(self) -> tuple[str, ...]:
        return fingerprint(self.engine_id, self.audio_format, self.values)

    def generate(self, text: str, output_path: Path) -> GeneratedAudio:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            model, speaker_id = self._model_and_speaker()
            model.tts_to_file(text, speaker_id, str(output_path), speed=float_value(self.values, 'MELO_SPEED', 1.0))
        except LookupError as exc:
            raise TTSGenerationError('MeloTTS 缺少 NLTK tagger，请先安装模型后重试。') from exc
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise TTSGenerationError(f'MeloTTS 生成失败：{exc}') from exc
        return GeneratedAudio(path=output_path, audio_format=self.audio_format, media_type=self.media_type)

    def _model_and_speaker(self) -> tuple[Any, int]:
        if self._model is None or self._speaker_id is None:
            factory = self._tts_factory
            if factory is None:
                factory = optional_import('melo.api', 'melotts 或 git+https://github.com/myshell-ai/MeloTTS.git').TTS
            self._model = factory(
                language=value(self.values, 'MELO_LANGUAGE', 'EN'),
                device=value(self.values, 'MELO_DEVICE', 'auto'),
            )
            speaker = value(self.values, 'MELO_SPEAKER', 'EN-Default')
            self._speaker_id = self._model.hps.data.spk2id[speaker]
        return self._model, self._speaker_id

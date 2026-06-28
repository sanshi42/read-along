from __future__ import annotations

from pathlib import Path
from typing import Any

from read_along.tts import GeneratedAudio
from read_along.tts.adapters.azure import AzureSpeechTTSBackend
from read_along.tts.adapters.cloud_sdks import CartesiaTTSBackend, ElevenLabsTTSBackend, FishAudioTTSBackend
from read_along.tts.adapters.gradio import CosyVoiceTTSBackend
from read_along.tts.adapters.http_api import GPTSoVITSTTSBackend
from read_along.tts.adapters.local_models import BarkTTSBackend, CoquiTTSBackend, MeloTTSBackend
from read_along.tts.adapters.openai_compatible import OpenAICompatibleTTSBackend
from read_along.tts.adapters.piper import PiperTTSBackend
from read_along.tts.adapters.pyttsx3_backend import Pyttsx3TTSBackend
from read_along.tts.config import OpenAITTSConfig


def test_openai_compatible_backend_streams_original_text(tmp_path: Path) -> None:
    class FakeStreamingResponse:
        def __enter__(self) -> 'FakeStreamingResponse':
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def stream_to_file(self, output_path: Path) -> None:
            output_path.write_bytes(b'ID3openai')

    class FakeCreate:
        calls: list[dict[str, object]] = []

        def __call__(self, **kwargs: object) -> FakeStreamingResponse:
            self.calls.append(kwargs)
            return FakeStreamingResponse()

    class FakeWithStreamingResponse:
        def __init__(self) -> None:
            self.create = FakeCreate()

    class FakeSpeech:
        def __init__(self) -> None:
            self.with_streaming_response = FakeWithStreamingResponse()

    class FakeAudio:
        def __init__(self) -> None:
            self.speech = FakeSpeech()

    class FakeClient:
        instances: list['FakeClient'] = []

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.audio = FakeAudio()
            self.instances.append(self)

    config = OpenAITTSConfig(
        base_url='http://127.0.0.1:8880/v1',
        api_key='not-needed',
        model='kokoro',
        voice='af_sky',
        audio_format='mp3',
        speed=1.15,
    )
    backend = OpenAICompatibleTTSBackend(config, client_factory=FakeClient)
    output_path = tmp_path / 'sentence.mp3'

    result = backend.generate('保留 [aside] 和 emoji 😊', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='mp3', media_type='audio/mpeg')
    assert FakeClient.instances[0].kwargs == {'api_key': 'not-needed', 'base_url': 'http://127.0.0.1:8880/v1'}
    assert FakeClient.instances[0].audio.speech.with_streaming_response.create.calls == [
        {
            'model': 'kokoro',
            'voice': 'af_sky',
            'input': '保留 [aside] 和 emoji 😊',
            'response_format': 'mp3',
            'speed': 1.15,
        }
    ]


def test_gpt_sovits_backend_sends_original_text_in_query(tmp_path: Path) -> None:
    class FakeResponse:
        status_code = 200
        content = b'RIFFgpt-sovits'
        text = 'ok'

    class FakeRequests:
        calls: list[tuple[str, dict[str, str], int]] = []

        @classmethod
        def get(cls, url: str, *, params: dict[str, str], timeout: int) -> FakeResponse:
            cls.calls.append((url, params, timeout))
            return FakeResponse()

    backend = GPTSoVITSTTSBackend(
        values={
            'READ_ALONG_TTS_GPT_SOVITS_API_URL': 'http://127.0.0.1:9880/tts',
            'READ_ALONG_TTS_GPT_SOVITS_REF_AUDIO_PATH': '/voice/ref.wav',
        },
        requests_module=FakeRequests,
    )
    output_path = tmp_path / 'sentence.wav'

    result = backend.generate('不要删除 [stage direction] 这段', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='wav', media_type='audio/wav')
    assert output_path.read_bytes() == b'RIFFgpt-sovits'
    assert FakeRequests.calls == [
        (
            'http://127.0.0.1:9880/tts',
            {
                'text': '不要删除 [stage direction] 这段',
                'text_lang': 'zh',
                'ref_audio_path': '/voice/ref.wav',
                'prompt_lang': 'zh',
                'prompt_text': '',
                'text_split_method': 'cut5',
                'batch_size': '1',
                'media_type': 'wav',
                'streaming_mode': 'false',
            },
            120,
        )
    ]


def test_piper_backend_synthesizes_original_text(tmp_path: Path) -> None:
    class FakeSynthesisConfig:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeVoice:
        texts: list[str] = []

        def synthesize_wav(self, text: str, wav_file: Any, *, syn_config: FakeSynthesisConfig) -> None:
            self.texts.append(text)
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b'pcm')

    class FakePiperVoice:
        load_calls: list[tuple[str, bool]] = []

        @classmethod
        def load(cls, model_path: str, *, use_cuda: bool) -> FakeVoice:
            cls.load_calls.append((model_path, use_cuda))
            return FakeVoice()

    model_path = tmp_path / 'zh_CN-huayan-medium.onnx'
    model_path.write_bytes(b'model')
    backend = PiperTTSBackend(
        values={'READ_ALONG_TTS_PIPER_MODEL_PATH': str(model_path), 'READ_ALONG_TTS_PIPER_SPEAKER_ID': '2'},
        piper_voice_cls=FakePiperVoice,
        synthesis_config_cls=FakeSynthesisConfig,
    )
    output_path = tmp_path / 'sentence.wav'

    result = backend.generate('原样朗读 <tag> & [aside]', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='wav', media_type='audio/wav')
    assert FakePiperVoice.load_calls == [(str(model_path), False)]
    assert FakeVoice.texts == ['原样朗读 <tag> & [aside]']


def test_azure_backend_speaks_original_text(tmp_path: Path) -> None:
    class FakeResultReason:
        SynthesizingAudioCompleted = 'done'

    class FakeResult:
        reason = FakeResultReason.SynthesizingAudioCompleted

    class FakeFuture:
        def get(self) -> FakeResult:
            return FakeResult()

    class FakeSpeechConfig:
        instances: list['FakeSpeechConfig'] = []

        def __init__(self, *, subscription: str, region: str) -> None:
            self.subscription = subscription
            self.region = region
            self.speech_synthesis_voice_name = ''
            self.instances.append(self)

    class FakeAudioOutputConfig:
        def __init__(self, *, filename: str) -> None:
            self.filename = filename

    class FakeSynthesizer:
        texts: list[str] = []

        def __init__(self, *, speech_config: FakeSpeechConfig, audio_config: FakeAudioOutputConfig) -> None:
            self.audio_config = audio_config

        def speak_text_async(self, text: str) -> FakeFuture:
            self.texts.append(text)
            Path(self.audio_config.filename).write_bytes(b'RIFFazure')
            return FakeFuture()

    fake_audio = type('FakeAudio', (), {'AudioOutputConfig': FakeAudioOutputConfig})
    fake_speech = type(
        'FakeSpeech',
        (),
        {
            'SpeechConfig': FakeSpeechConfig,
            'SpeechSynthesizer': FakeSynthesizer,
            'ResultReason': FakeResultReason,
            'audio': fake_audio,
        },
    )
    backend = AzureSpeechTTSBackend(
        values={
            'READ_ALONG_TTS_AZURE_KEY': 'secret',
            'READ_ALONG_TTS_AZURE_REGION': 'eastasia',
            'READ_ALONG_TTS_AZURE_VOICE': 'zh-CN-XiaoxiaoNeural',
        },
        speech_module=fake_speech,
    )
    output_path = tmp_path / 'sentence.wav'

    result = backend.generate('保留 <xml> & [aside]', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='wav', media_type='audio/wav')
    assert FakeSpeechConfig.instances[0].speech_synthesis_voice_name == 'zh-CN-XiaoxiaoNeural'
    assert FakeSynthesizer.texts == ['保留 <xml> & [aside]']


def test_pyttsx3_backend_saves_original_text(tmp_path: Path) -> None:
    class FakeEngine:
        saved: list[tuple[str, str]] = []

        def setProperty(self, name: str, value: object) -> None:
            return None

        def save_to_file(self, text: str, filename: str) -> None:
            self.saved.append((text, filename))
            Path(filename).write_bytes(b'RIFFpyttsx3')

        def runAndWait(self) -> None:
            return None

    fake_engine = FakeEngine()
    fake_module = type('FakePyttsx3', (), {'init': staticmethod(lambda: fake_engine)})
    backend = Pyttsx3TTSBackend(values={'READ_ALONG_TTS_PYTTSX3_RATE': '180'}, pyttsx3_module=fake_module)
    output_path = tmp_path / 'sentence.wav'

    result = backend.generate('系统语音也不清理 [aside]', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='wav', media_type='audio/wav')
    assert fake_engine.saved == [('系统语音也不清理 [aside]', str(output_path))]


def test_cosyvoice_backend_copies_predicted_audio_and_uses_original_text(tmp_path: Path) -> None:
    source_path = tmp_path / 'service.wav'
    source_path.write_bytes(b'RIFFcosy')

    class FakeClient:
        calls: list[dict[str, object]] = []

        def __init__(self, url: str) -> None:
            self.url = url

        def predict(self, **kwargs: object) -> str:
            self.calls.append(kwargs)
            return str(source_path)

    fake_module = type(
        'FakeGradioClient',
        (),
        {
            'Client': FakeClient,
            'file': staticmethod(lambda path: f'file:{path}'),
            'handle_file': staticmethod(lambda path: f'handle:{path}'),
        },
    )
    backend = CosyVoiceTTSBackend(
        values={'READ_ALONG_TTS_COSYVOICE_CLIENT_URL': 'http://127.0.0.1:50000/'},
        gradio_module=fake_module,
    )
    output_path = tmp_path / 'sentence.wav'

    result = backend.generate('CosyVoice 原样 [aside]', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='wav', media_type='audio/wav')
    assert output_path.read_bytes() == b'RIFFcosy'
    assert FakeClient.calls[0]['tts_text'] == 'CosyVoice 原样 [aside]'


def test_fish_backend_streams_original_text(tmp_path: Path) -> None:
    class FakeTTSRequest:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeSession:
        requests: list[FakeTTSRequest] = []

        def __init__(self, *, apikey: str, base_url: str) -> None:
            self.apikey = apikey
            self.base_url = base_url

        def tts(self, request: FakeTTSRequest) -> list[bytes]:
            self.requests.append(request)
            return [b'RIFF', b'fish']

    fake_module = type('FakeFish', (), {'Session': FakeSession, 'TTSRequest': FakeTTSRequest})
    backend = FishAudioTTSBackend(values={'READ_ALONG_TTS_FISH_API_KEY': 'fish-key'}, fish_module=fake_module)
    output_path = tmp_path / 'sentence.wav'

    result = backend.generate('Fish 原样 <tag>', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='wav', media_type='audio/wav')
    assert output_path.read_bytes() == b'RIFFfish'
    assert FakeSession.requests[0].kwargs['text'] == 'Fish 原样 <tag>'


def test_elevenlabs_backend_converts_original_text(tmp_path: Path) -> None:
    class FakeTextToSpeech:
        calls: list[dict[str, object]] = []

        def convert(self, **kwargs: object) -> list[bytes]:
            self.calls.append(kwargs)
            return [b'ID3', b'eleven']

    class FakeClient:
        instances: list['FakeClient'] = []

        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.text_to_speech = FakeTextToSpeech()
            self.instances.append(self)

    backend = ElevenLabsTTSBackend(
        values={'READ_ALONG_TTS_ELEVENLABS_API_KEY': 'eleven-key', 'READ_ALONG_TTS_ELEVENLABS_VOICE_ID': 'voice'},
        client_factory=FakeClient,
    )
    output_path = tmp_path / 'sentence.mp3'

    result = backend.generate('ElevenLabs 原样 [aside]', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='mp3', media_type='audio/mpeg')
    assert output_path.read_bytes() == b'ID3eleven'
    assert FakeClient.instances[0].text_to_speech.calls[0]['text'] == 'ElevenLabs 原样 [aside]'


def test_cartesia_backend_generates_original_text(tmp_path: Path) -> None:
    class FakeTTS:
        calls: list[dict[str, object]] = []

        def bytes(self, **kwargs: object) -> list[bytes]:
            self.calls.append(kwargs)
            return [b'RIFF', b'cartesia']

    class FakeClient:
        instances: list['FakeClient'] = []

        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.tts = FakeTTS()
            self.instances.append(self)

    backend = CartesiaTTSBackend(values={'READ_ALONG_TTS_CARTESIA_API_KEY': 'cartesia-key'}, client_factory=FakeClient)
    output_path = tmp_path / 'sentence.wav'

    result = backend.generate('Cartesia 原样 <tag>', output_path)

    assert result == GeneratedAudio(path=output_path, audio_format='wav', media_type='audio/wav')
    assert output_path.read_bytes() == b'RIFFcartesia'
    assert FakeClient.instances[0].tts.calls[0]['transcript'] == 'Cartesia 原样 <tag>'


def test_local_model_backends_use_original_text(tmp_path: Path) -> None:
    class FakeWavfile:
        calls: list[tuple[Path, int, list[int]]] = []

        @classmethod
        def write(cls, filename: Path, rate: int, data: list[int]) -> None:
            cls.calls.append((filename, rate, data))
            filename.write_bytes(b'RIFFbark')

    fake_bark = type(
        'FakeBark',
        (),
        {
            'SAMPLE_RATE': 24000,
            'preload_models': staticmethod(lambda: None),
            'generate_audio': staticmethod(lambda text, *, history_prompt: [len(text)]),
        },
    )
    bark_output = tmp_path / 'bark.wav'
    bark = BarkTTSBackend(
        values={'READ_ALONG_TTS_BARK_VOICE': 'voice'},
        bark_module=fake_bark,
        wavfile_module=FakeWavfile,
    )

    assert bark.generate('Bark 原样 [aside]', bark_output).path == bark_output
    assert FakeWavfile.calls == [(bark_output, 24000, [15])]

    class FakeCoquiModel:
        calls: list[dict[str, object]] = []
        speakers = None

        def to(self, device: str) -> 'FakeCoquiModel':
            self.device = device
            return self

        def tts_to_file(self, **kwargs: object) -> None:
            self.calls.append(kwargs)
            Path(str(kwargs['file_path'])).write_bytes(b'RIFFcoqui')

    fake_coqui_model = FakeCoquiModel()
    coqui_output = tmp_path / 'coqui.wav'
    coqui = CoquiTTSBackend(
        values={'READ_ALONG_TTS_COQUI_DEVICE': 'cpu'},
        tts_factory=lambda **_kwargs: fake_coqui_model,
    )

    assert coqui.generate('Coqui 原样 <tag>', coqui_output).path == coqui_output
    assert fake_coqui_model.calls == [{'text': 'Coqui 原样 <tag>', 'file_path': str(coqui_output)}]

    class FakeMeloModel:
        def __init__(self) -> None:
            self.hps = type('Hps', (), {'data': type('Data', (), {'spk2id': {'ZH': 0}})})()
            self.calls: list[tuple[str, int, str, float]] = []

        def tts_to_file(self, text: str, speaker_id: int, output_path: str, *, speed: float) -> None:
            self.calls.append((text, speaker_id, output_path, speed))
            Path(output_path).write_bytes(b'RIFFmelo')

    fake_melo_model = FakeMeloModel()
    melo_output = tmp_path / 'melo.wav'
    melo = MeloTTSBackend(
        values={'READ_ALONG_TTS_MELO_SPEAKER': 'ZH', 'READ_ALONG_TTS_MELO_LANGUAGE': 'ZH'},
        tts_factory=lambda **_kwargs: fake_melo_model,
    )

    assert melo.generate('Melo 原样 [aside]', melo_output).path == melo_output
    assert fake_melo_model.calls == [('Melo 原样 [aside]', 0, str(melo_output), 1.0)]

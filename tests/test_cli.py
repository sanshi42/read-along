from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from read_along import cli
from read_along.cli import app
from read_along.config import AppConfig
from read_along.db import DatabaseSchemaError
from read_along.tts.config import TTSConfig, TTSConfigurationError
from read_along.tts.download import KokoroModelPaths
from read_along.tts.profiles import MODEL_PROFILE_ID


class FakeUvicorn:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, app: str, *, host: str, port: int, reload: bool) -> None:
        self.calls.append(
            {
                'app': app,
                'host': host,
                'port': port,
                'reload': reload,
            }
        )


@pytest.fixture(autouse=True)
def stub_model_runtime_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, 'create_tts_backend', lambda config, paths: object())


def configured_app(home: Path) -> AppConfig:
    return AppConfig(
        home=home,
        tts=TTSConfig(
            model=MODEL_PROFILE_ID,
            voice_id=3,
            provider='cpu',
            num_threads=2,
            speed=1.0,
        ),
    )


def test_root_cli_registers_serve_command() -> None:
    result = CliRunner().invoke(app, ['--help'])

    assert result.exit_code == 0
    assert 'serve' in result.output
    assert 'tts' in result.output
    assert 'diagnose-db' not in result.output


def test_plain_download_progress_logs_when_download_starts() -> None:
    output = StringIO()
    progress = cli.PlainDownloadProgress(Console(file=output, force_terminal=False))

    progress.start(total_bytes=100, completed_bytes=0)
    progress.start(total_bytes=100, completed_bytes=50)

    assert output.getvalue().count('正在下载朗读模型') == 1


def test_serve_uses_default_local_binding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    fake_uvicorn = FakeUvicorn()

    def fake_bind(host: str, port: int) -> None:
        calls['bind'] = (host, port)

    monkeypatch.setattr(cli, '_ensure_bind_available', fake_bind)
    monkeypatch.setattr(cli, '_load_uvicorn', lambda: fake_uvicorn)
    config = configured_app(tmp_path / 'data')
    monkeypatch.setattr(cli, 'load_config', lambda: config)
    runtime_backend = object()
    monkeypatch.setattr(cli, 'create_tts_backend', lambda tts_config, paths: runtime_backend)
    ensured: list[tuple[str, Path]] = []
    model_dir = tmp_path / 'data' / 'models' / 'tts' / 'kokoro-multi-lang-v1_1'
    model_paths = KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.int8.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )

    def fake_ensure(profile: str, root: Path, **_: object) -> KokoroModelPaths:
        ensured.append((profile, root))
        return model_paths

    monkeypatch.setattr(
        cli,
        'ensure_model',
        fake_ensure,
    )
    monkeypatch.setattr('read_along.api._state', None)

    result = CliRunner().invoke(app, ['serve'])

    assert result.exit_code == 0, result.output
    assert calls['bind'] == ('127.0.0.1', 8765)
    assert ensured == [(MODEL_PROFILE_ID, tmp_path / 'data' / 'models' / 'tts')]
    from read_along import api as api_module

    assert api_module._state is not None
    assert api_module._state.material_library.tts is runtime_backend
    assert fake_uvicorn.calls == [
        {
            'app': 'read_along.api:app',
            'host': '127.0.0.1',
            'port': 8765,
            'reload': False,
        }
    ]


def test_serve_reports_bind_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_bind(host: str, port: int) -> None:
        raise RuntimeError(f'无法绑定服务到 {host}:{port}。')

    monkeypatch.setattr(cli, '_ensure_bind_available', fake_bind)

    result = CliRunner().invoke(app, ['serve'])

    assert result.exit_code == 1
    assert 'Read Along 服务启动失败' in result.output
    assert '无法绑定服务到 127.0.0.1:8765' in result.output


def test_serve_reports_database_schema_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_uvicorn = FakeUvicorn()
    monkeypatch.setattr(cli, '_ensure_bind_available', lambda host, port: None)
    monkeypatch.setattr(cli, '_load_uvicorn', lambda: fake_uvicorn)
    monkeypatch.setattr(cli, 'load_config', lambda: configured_app(Path('/tmp/read-along-test-data')))
    monkeypatch.setattr(cli, '_prepare_model', lambda config: object())

    def fail_init_app_state(*, config: AppConfig, tts: object):
        del config, tts
        raise DatabaseSchemaError('不支持当前数据库结构。')

    monkeypatch.setattr('read_along.api.init_app_state', fail_init_app_state)

    result = CliRunner().invoke(app, ['serve'])

    assert result.exit_code == 1
    assert 'Read Along 服务启动失败' in result.output
    assert '不支持当前数据库结构' in result.output
    assert fake_uvicorn.calls == []


def test_serve_reports_model_download_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, '_ensure_bind_available', lambda host, port: None)
    monkeypatch.setattr(cli, '_load_uvicorn', lambda: FakeUvicorn())
    config = configured_app(tmp_path / 'data')
    monkeypatch.setattr(cli, 'load_config', lambda: config)
    monkeypatch.setattr(cli, 'ensure_model', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('下载失败')))
    monkeypatch.setattr('read_along.api._state', None)

    result = CliRunner().invoke(app, ['serve'])

    assert result.exit_code == 1
    assert 'Read Along 服务启动失败' in result.output
    assert '下载失败' in result.output


def test_serve_reports_model_runtime_validation_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_uvicorn = FakeUvicorn()
    monkeypatch.setattr(cli, '_ensure_bind_available', lambda host, port: None)
    monkeypatch.setattr(cli, '_load_uvicorn', lambda: fake_uvicorn)
    config = configured_app(tmp_path / 'data')
    monkeypatch.setattr(cli, 'load_config', lambda: config)
    model_dir = tmp_path / 'data' / 'models' / 'tts' / 'kokoro-multi-lang-v1_1'
    model_paths = KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.int8.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )
    monkeypatch.setattr(cli, 'ensure_model', lambda *args, **kwargs: model_paths)
    monkeypatch.setattr(
        cli,
        'create_tts_backend',
        lambda config, paths: (_ for _ in ()).throw(TTSConfigurationError('模型无法加载')),
    )
    monkeypatch.setattr('read_along.api._state', None)

    result = CliRunner().invoke(app, ['serve'])

    assert result.exit_code == 1
    assert '模型无法加载' in result.output
    assert fake_uvicorn.calls == []


def test_tts_download_model_uses_configured_profile_without_printing_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = configured_app(tmp_path / 'data')
    monkeypatch.setattr(cli, 'load_config', lambda: config)
    model_dir = tmp_path / 'data' / 'models' / 'tts' / 'kokoro-multi-lang-v1_1'
    expected = KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )
    calls: list[tuple[Path, bool]] = []

    def fake_download(
        profile: str,
        target_dir: Path,
        *,
        restart: bool = False,
        progress: object | None = None,
    ) -> KokoroModelPaths:
        assert profile == MODEL_PROFILE_ID
        assert progress is not None
        calls.append((target_dir, restart))
        return expected

    monkeypatch.setattr(cli, 'ensure_model', fake_download)

    result = CliRunner().invoke(app, ['tts', 'download-model'])

    assert result.exit_code == 0, result.output
    assert calls == [(tmp_path / 'data' / 'models' / 'tts', False)]
    assert MODEL_PROFILE_ID in result.output
    assert 'READ_ALONG_TTS_' not in result.output
    assert not (tmp_path / '.env').exists()


def test_tts_download_model_restart_option_discards_partial_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = configured_app(tmp_path / 'data')
    monkeypatch.setattr(cli, 'load_config', lambda: config)
    model_dir = tmp_path / 'data' / 'models' / 'tts' / 'kokoro-multi-lang-v1_1'
    expected = KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )
    calls: list[tuple[Path, bool]] = []

    def fake_download(
        profile: str,
        target_dir: Path,
        *,
        restart: bool = False,
        progress: object | None = None,
    ) -> KokoroModelPaths:
        assert profile == MODEL_PROFILE_ID
        assert progress is not None
        calls.append((target_dir, restart))
        return expected

    monkeypatch.setattr(cli, 'ensure_model', fake_download)

    result = CliRunner().invoke(app, ['tts', 'download-model', '--restart'])

    assert result.exit_code == 0, result.output
    assert calls == [(tmp_path / 'data' / 'models' / 'tts', True)]


def test_tts_download_model_passes_interactive_progress_reporter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = configured_app(tmp_path / 'data')
    monkeypatch.setattr(cli, 'load_config', lambda: config)
    model_dir = tmp_path / 'data' / 'models' / 'tts' / 'kokoro-multi-lang-v1_1'
    expected = KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )
    reporter = object()
    calls: list[object | None] = []

    @contextmanager
    def fake_progress_context():
        yield reporter

    def fake_download(
        profile: str,
        _: Path,
        *,
        restart: bool = False,
        progress: object | None = None,
    ) -> KokoroModelPaths:
        assert profile == MODEL_PROFILE_ID
        assert not restart
        calls.append(progress)
        return expected

    monkeypatch.setattr(cli, '_download_progress_context', fake_progress_context, raising=False)
    monkeypatch.setattr(cli, 'ensure_model', fake_download)

    result = CliRunner().invoke(app, ['tts', 'download-model'])

    assert result.exit_code == 0, result.output
    assert calls == [reporter]

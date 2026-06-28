from contextlib import contextmanager
from pathlib import Path

import pytest
from typer.testing import CliRunner

from read_along import cli
from read_along.cli import app
from read_along.db import DatabaseSchemaError
from read_along.tts.download import KokoroModelPaths


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


def test_root_cli_registers_serve_command() -> None:
    result = CliRunner().invoke(app, ['--help'])

    assert result.exit_code == 0
    assert 'serve' in result.output
    assert 'tts' in result.output
    assert 'diagnose-db' not in result.output


def test_serve_uses_default_local_binding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    fake_uvicorn = FakeUvicorn()

    def fake_bind(host: str, port: int) -> None:
        calls['bind'] = (host, port)

    monkeypatch.setattr(cli, '_ensure_bind_available', fake_bind)
    monkeypatch.setattr(cli, '_load_uvicorn', lambda: fake_uvicorn)
    monkeypatch.setenv('READ_ALONG_HOME', str(tmp_path / 'data'))
    monkeypatch.setattr('read_along.api._state', None)

    result = CliRunner().invoke(app, ['serve'])

    assert result.exit_code == 0, result.output
    assert calls['bind'] == ('127.0.0.1', 8765)
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

    def fail_init_app_state():
        raise DatabaseSchemaError('不支持当前数据库结构。')

    monkeypatch.setattr('read_along.api.init_app_state', fail_init_app_state)

    result = CliRunner().invoke(app, ['serve'])

    assert result.exit_code == 1
    assert 'Read Along 服务启动失败' in result.output
    assert '不支持当前数据库结构' in result.output
    assert fake_uvicorn.calls == []


def test_tts_download_model_prints_env_without_writing_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv('READ_ALONG_HOME', str(tmp_path / 'data'))
    model_dir = tmp_path / 'data' / 'models' / 'tts' / 'kokoro-multi-lang-v1_1'
    expected = KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )
    calls: list[tuple[Path, bool]] = []

    def fake_download(target_dir: Path, *, restart: bool = False, progress: object | None = None) -> KokoroModelPaths:
        assert progress is not None
        calls.append((target_dir, restart))
        return expected

    monkeypatch.setattr(cli, 'download_kokoro_model', fake_download)

    result = CliRunner().invoke(app, ['tts', 'download-model', 'kokoro'])

    assert result.exit_code == 0, result.output
    assert calls == [(tmp_path / 'data' / 'models' / 'tts', False)]
    assert 'READ_ALONG_TTS_ENGINE=sherpa_onnx_tts' in result.output
    assert f'READ_ALONG_TTS_SHERPA_KOKORO_MODEL={expected.model_path}' in result.output
    assert not (tmp_path / '.env').exists()


def test_tts_download_model_restart_option_discards_partial_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv('READ_ALONG_HOME', str(tmp_path / 'data'))
    model_dir = tmp_path / 'data' / 'models' / 'tts' / 'kokoro-multi-lang-v1_1'
    expected = KokoroModelPaths(
        model_dir=model_dir,
        model_path=model_dir / 'model.onnx',
        voices_path=model_dir / 'voices.bin',
        tokens_path=model_dir / 'tokens.txt',
        data_dir=model_dir / 'espeak-ng-data',
    )
    calls: list[tuple[Path, bool]] = []

    def fake_download(target_dir: Path, *, restart: bool = False, progress: object | None = None) -> KokoroModelPaths:
        assert progress is not None
        calls.append((target_dir, restart))
        return expected

    monkeypatch.setattr(cli, 'download_kokoro_model', fake_download)

    result = CliRunner().invoke(app, ['tts', 'download-model', 'kokoro', '--restart'])

    assert result.exit_code == 0, result.output
    assert calls == [(tmp_path / 'data' / 'models' / 'tts', True)]


def test_tts_download_model_passes_interactive_progress_reporter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv('READ_ALONG_HOME', str(tmp_path / 'data'))
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

    def fake_download(_: Path, *, restart: bool = False, progress: object | None = None) -> KokoroModelPaths:
        assert not restart
        calls.append(progress)
        return expected

    monkeypatch.setattr(cli, '_download_progress_context', fake_progress_context, raising=False)
    monkeypatch.setattr(cli, 'download_kokoro_model', fake_download)

    result = CliRunner().invoke(app, ['tts', 'download-model', 'kokoro'])

    assert result.exit_code == 0, result.output
    assert calls == [reporter]

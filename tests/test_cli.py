import pytest
from typer.testing import CliRunner

from read_along import cli
from read_along.cli import app


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


def test_serve_uses_default_local_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    fake_uvicorn = FakeUvicorn()

    def fake_bind(host: str, port: int) -> None:
        calls['bind'] = (host, port)

    monkeypatch.setattr(cli, '_ensure_bind_available', fake_bind)
    monkeypatch.setattr(cli, '_load_uvicorn', lambda: fake_uvicorn)

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

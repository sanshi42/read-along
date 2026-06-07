from __future__ import annotations

import importlib
import socket
from typing import Protocol, cast

import typer
from rich.console import Console


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

app = typer.Typer(help="运行 Read Along 应用。")
console = Console()


class UvicornModule(Protocol):
    def run(self, app: str, *, host: str, port: int, reload: bool) -> None:
        pass


@app.callback()
def main() -> None:
    """Read Along 命令行界面。"""


def _ensure_bind_available(host: str, port: int) -> None:
    try:
        address_infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise RuntimeError(f"无法解析 Read Along 主机 {host!r}：{exc}") from exc

    last_error: OSError | None = None
    for family, socktype, proto, _, sockaddr in address_infos:
        with socket.socket(family, socktype, proto) as candidate:
            try:
                candidate.bind(sockaddr)
            except OSError as exc:
                last_error = exc
                continue
            return

    detail = str(last_error) if last_error else "未找到可绑定的地址"
    raise RuntimeError(f"无法将 Read Along 服务绑定到 {host}:{port}（{detail}）。") from last_error


def _load_uvicorn() -> UvicornModule:
    try:
        return cast(UvicornModule, importlib.import_module("uvicorn"))
    except ImportError as exc:
        raise RuntimeError("缺少 Read Along 服务依赖。请运行 `uv sync --no-editable` 后重试。") from exc


@app.command()
def serve(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="绑定主机。"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", min=1, max=65535, help="绑定端口。"),
    reload: bool = typer.Option(False, "--reload", help="代码变更时重启。"),
) -> None:
    """启动本地 Read Along FastAPI 服务。"""
    try:
        _ensure_bind_available(host, port)
        uvicorn = _load_uvicorn()
    except RuntimeError as exc:
        console.print(f"[red]Read Along 服务启动失败：[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # 启动服务前初始化应用状态（存储路径、数据库和 repository）
    from read_along.api import init_app_state
    app_state = init_app_state()
    console.print(f"[dim]数据目录：{app_state.storage_paths.home}[/dim]")

    console.print(f"[cyan]正在启动 Read Along API：[/cyan] http://{host}:{port}")
    uvicorn.run("read_along.api:app", host=host, port=port, reload=reload)

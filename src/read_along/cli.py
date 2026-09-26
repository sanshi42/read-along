from __future__ import annotations

import importlib
import socket
from contextlib import contextmanager
from typing import Iterator, Protocol, cast

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from read_along.config import AppConfig, load_config
from read_along.storage import StoragePaths
from read_along.tts.base import TTSBackend
from read_along.tts.config import TTSConfigurationError
from read_along.tts.download import DownloadProgress, ModelDownloadError
from read_along.tts.factory import create_tts_backend
from read_along.tts.profiles import ensure_model

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8765

app = typer.Typer(help='运行 Read Along 应用。')
tts_app = typer.Typer(help='管理朗读引擎和本地模型。')
app.add_typer(tts_app, name='tts')
console = Console()


class RichDownloadProgress:
    """在交互终端中显示模型下载状态。"""

    def __init__(self, output: Console) -> None:
        self._console = output
        self._progress = Progress(
            TextColumn('{task.description}'),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=output,
        )
        self._task_id: TaskID | None = None

    def __enter__(self) -> RichDownloadProgress:
        """启动 Rich 进度显示。"""
        self._progress.start()
        return self

    def __exit__(self, *_: object) -> None:
        """停止 Rich 进度显示。"""
        self._progress.stop()

    def start(self, total_bytes: int | None, completed_bytes: int) -> None:
        """创建或重置当前下载任务。"""
        if self._task_id is None:
            self._task_id = self._progress.add_task('正在下载朗读模型', total=total_bytes, completed=completed_bytes)
            return
        self._progress.update(self._task_id, total=total_bytes, completed=completed_bytes)

    def advance(self, completed_bytes: int) -> None:
        """更新已下载字节数。"""
        if self._task_id is not None:
            self._progress.update(self._task_id, completed=completed_bytes)

    def retry(self, retry_number: int, delay_seconds: float, error: Exception) -> None:
        """在进度条上方报告一次网络重试。"""
        self._console.print(f'[yellow]下载中断：{error}；{delay_seconds:g} 秒后进行第 {retry_number} 次重试。[/yellow]')


class PlainDownloadProgress:
    """在非交互输出中仅报告下载重试。"""

    def __init__(self, output: Console) -> None:
        self._console = output
        self._started = False

    def start(self, total_bytes: int | None, completed_bytes: int) -> None:
        """首次收到下载进度时写入日志。"""
        del total_bytes, completed_bytes
        if not self._started:
            self._console.print('正在下载朗读模型。')
            self._started = True

    def advance(self, completed_bytes: int) -> None:
        """忽略静态下载进度。"""
        del completed_bytes

    def retry(self, retry_number: int, delay_seconds: float, error: Exception) -> None:
        """输出重试原因与下一次等待时间。"""
        self._console.print(f'下载中断：{error}；{delay_seconds:g} 秒后进行第 {retry_number} 次重试。')


@contextmanager
def _download_progress_context() -> Iterator[DownloadProgress]:
    if not console.is_terminal:
        yield PlainDownloadProgress(console)
        return
    with RichDownloadProgress(console) as progress:
        yield progress


def _prepare_model(config: AppConfig, *, restart: bool = False) -> TTSBackend:
    if config.tts is None:
        raise TTSConfigurationError('朗读配置未加载。')
    models_root = StoragePaths.from_config(config).models / 'tts'
    console.print(f'[cyan]正在准备朗读模型：[/cyan] {config.tts.model}')
    with _download_progress_context() as progress:
        result = ensure_model(config.tts.model, models_root, restart=restart, progress=progress)
    backend = create_tts_backend(config.tts, result)
    console.print(f'[green]朗读模型已就绪：[/green] {result.model_dir}')
    return backend


class UvicornModule(Protocol):
    """Uvicorn 模块的最小运行协议。"""

    def run(self, app: str, *, host: str, port: int, reload: bool) -> None:
        """启动 ASGI 应用。"""
        pass


@app.callback()
def main() -> None:
    """Read Along 命令行界面。"""


def _ensure_bind_available(host: str, port: int) -> None:
    try:
        address_infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise RuntimeError(f'无法解析 Read Along 主机 {host!r}：{exc}') from exc

    last_error: OSError | None = None
    for family, socktype, proto, _, sockaddr in address_infos:
        with socket.socket(family, socktype, proto) as candidate:
            try:
                candidate.bind(sockaddr)
            except OSError as exc:
                last_error = exc
                continue
            return

    detail = str(last_error) if last_error else '未找到可绑定的地址'
    raise RuntimeError(f'无法将 Read Along 服务绑定到 {host}:{port}（{detail}）。') from last_error


def _load_uvicorn() -> UvicornModule:
    try:
        return cast(UvicornModule, importlib.import_module('uvicorn'))
    except ImportError as exc:
        raise RuntimeError('缺少 Read Along 服务依赖。请运行 `uv sync` 后重试。') from exc


@app.command()
def serve(
    host: str = typer.Option(DEFAULT_HOST, '--host', help='绑定主机。'),
    port: int = typer.Option(DEFAULT_PORT, '--port', '-p', min=1, max=65535, help='绑定端口。'),
    reload: bool = typer.Option(False, '--reload', help='代码变更时重启。'),
) -> None:
    """启动本地 Read Along FastAPI 服务。"""
    try:
        _ensure_bind_available(host, port)
        uvicorn = _load_uvicorn()
        config = load_config()
        tts_backend = _prepare_model(config)

        # 启动服务前初始化应用状态（存储路径、数据库、repository 和已校验的朗读引擎）
        from read_along.api import init_app_state

        app_state = init_app_state(config=config, tts=tts_backend)
    except (RuntimeError, TTSConfigurationError) as exc:
        console.print(f'[red]Read Along 服务启动失败：[/red] {exc}')
        raise typer.Exit(code=1) from exc

    console.print(f'[dim]数据目录：{app_state.storage_paths.home}[/dim]')

    console.print(f'[cyan]正在启动 Read Along API：[/cyan] http://{host}:{port}')
    uvicorn.run('read_along.api:app', host=host, port=port, reload=reload)


@tts_app.command('download-model')
def download_tts_model(
    restart: bool = typer.Option(False, '--restart', help='删除未完成下载并从头下载。'),
) -> None:
    """提前下载或重新下载 `.env` 选择的朗读模型。"""
    try:
        _prepare_model(load_config(), restart=restart)
    except (ModelDownloadError, TTSConfigurationError) as exc:
        console.print(f'[red]TTS 模型下载失败：[/red] {exc}')
        raise typer.Exit(code=1) from exc

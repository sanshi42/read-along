from __future__ import annotations

import importlib
import socket
from typing import Protocol, cast

import typer
from rich.console import Console


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

app = typer.Typer(help="Run the Read Along application.")
console = Console()


class UvicornModule(Protocol):
    def run(self, app: str, *, host: str, port: int, reload: bool) -> None:
        pass


@app.callback()
def main() -> None:
    """Read Along command-line interface."""


def _ensure_bind_available(host: str, port: int) -> None:
    try:
        address_infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise RuntimeError(f"Cannot resolve Read Along host {host!r}: {exc}") from exc

    last_error: OSError | None = None
    for family, socktype, proto, _, sockaddr in address_infos:
        with socket.socket(family, socktype, proto) as candidate:
            try:
                candidate.bind(sockaddr)
            except OSError as exc:
                last_error = exc
                continue
            return

    detail = str(last_error) if last_error else "no bindable address found"
    raise RuntimeError(f"Cannot bind Read Along server to {host}:{port} ({detail}).") from last_error


def _load_uvicorn() -> UvicornModule:
    try:
        return cast(UvicornModule, importlib.import_module("uvicorn"))
    except ImportError as exc:
        raise RuntimeError("Read Along server dependencies are missing. Run `uv sync --no-editable` and try again.") from exc


@app.command()
def serve(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Bind host."),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", min=1, max=65535, help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Restart when code changes."),
) -> None:
    """Start the local Read Along FastAPI service."""
    try:
        _ensure_bind_available(host, port)
        uvicorn = _load_uvicorn()
    except RuntimeError as exc:
        console.print(f"[red]Read Along server startup failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Initialize app state (storage paths, database, repository) before serving
    from read_along.api import init_app_state
    app_state = init_app_state()
    console.print(f"[dim]Data directory: {app_state.storage_paths.home}[/dim]")

    console.print(f"[cyan]Starting Read Along API:[/cyan] http://{host}:{port}")
    uvicorn.run("read_along.api:app", host=host, port=port, reload=reload)

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


READ_ALONG_HOME = "READ_ALONG_HOME"


@dataclass(frozen=True)
class AppConfig:
    home: Path


def default_home() -> Path:
    return Path.home() / ".local" / "share" / "read-along"


def load_config() -> AppConfig:
    configured_home = os.environ.get(READ_ALONG_HOME)
    home = Path(configured_home).expanduser() if configured_home else default_home()
    return AppConfig(home=home)

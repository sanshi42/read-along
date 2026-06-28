from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from read_along.tts.config import TTSConfig, load_tts_config

READ_ALONG_HOME = 'READ_ALONG_HOME'


@dataclass(frozen=True)
class AppConfig:
    """应用运行配置。"""

    home: Path
    tts: TTSConfig = field(default_factory=load_tts_config)


def default_home() -> Path:
    """返回默认本地数据目录。"""
    return Path.home() / '.local' / 'share' / 'read-along'


def load_config() -> AppConfig:
    """从环境变量加载应用配置。"""
    configured_home = os.environ.get(READ_ALONG_HOME)
    home = Path(configured_home).expanduser() if configured_home else default_home()
    return AppConfig(home=home, tts=load_tts_config())

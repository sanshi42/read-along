from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from read_along.config import AppConfig


@dataclass(frozen=True)
class StoragePaths:
    home: Path
    database: Path
    uploads: Path
    audio: Path
    logs: Path

    @classmethod
    def from_config(cls, config: AppConfig) -> StoragePaths:
        return cls(
            home=config.home,
            database=config.home / "read-along.sqlite3",
            uploads=config.home / "uploads",
            audio=config.home / "audio",
            logs=config.home / "logs",
        )

    def ensure_directories(self) -> None:
        for directory in (self.home, self.uploads, self.audio, self.logs):
            directory.mkdir(parents=True, exist_ok=True)

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """在 SQLite 中保存 UTC 时间，并在读取时恢复 UTC 时区。"""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        """验证并规范化写入数据库的时间。"""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('数据库时间必须包含时区')
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        """为数据库读出的 UTC 时间恢复时区。"""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

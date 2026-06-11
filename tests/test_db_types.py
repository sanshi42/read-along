from datetime import datetime, timedelta, timezone

import pytest

from read_along.db_types import UTCDateTime


def test_utc_datetime_rejects_naive_value() -> None:
    column_type = UTCDateTime()

    with pytest.raises(ValueError, match='必须包含时区'):
        column_type.process_bind_param(datetime(2026, 6, 10, 8, 0), None)


def test_utc_datetime_normalizes_value_before_storage() -> None:
    column_type = UTCDateTime()
    value = datetime(2026, 6, 10, 8, 0, tzinfo=timezone(timedelta(hours=8)))

    stored = column_type.process_bind_param(value, None)

    assert stored is not None
    assert stored == datetime(2026, 6, 10, 0, 0)
    assert stored.tzinfo is None


def test_utc_datetime_restores_utc_timezone_after_reading() -> None:
    column_type = UTCDateTime()

    restored = column_type.process_result_value(datetime(2026, 6, 10, 0, 0), None)

    assert restored is not None
    assert restored == datetime(2026, 6, 10, 0, 0, tzinfo=timezone.utc)
    assert restored.tzinfo is timezone.utc

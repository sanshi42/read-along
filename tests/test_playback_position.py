import pytest

from read_along.models import ReadingProgress, Sentence
from read_along.playback_position import playback_time_position


def sentence(
    sentence_id: str,
    index: int,
    text: str,
    *,
    duration: float | None,
) -> Sentence:
    return Sentence.model_validate(
        {
            'id': sentence_id,
            'material_id': 'mat-1',
            'paragraph_id': 'paragraph-1',
            'index': index,
            'text': text,
            'audio_status': 'pending',
            'audio_path': None,
            'audio_duration_seconds': duration,
            'error_message': None,
        }
    )


def progress(
    sentence_id: str,
    *,
    offset: float,
    completed: bool = False,
) -> ReadingProgress:
    return ReadingProgress.model_validate(
        {
            'material_id': 'mat-1',
            'sentence_id': sentence_id,
            'sentence_offset_seconds': offset,
            'playback_rate': 1.0,
            'playback_completed': completed,
            'updated_at': '2026-06-06T00:00:00Z',
        }
    )


def test_playback_time_position_uses_real_durations_and_adaptive_estimates() -> None:
    sentences = [
        sentence('s1', 1, '一二三四', duration=4),
        sentence('s2', 2, '一二三四五六', duration=None),
        sentence('s3', 3, '一二三四五六', duration=6),
    ]

    position = playback_time_position(sentences, progress('s2', offset=2))

    assert position is not None
    assert position.elapsed_seconds == pytest.approx(6)
    assert position.total_seconds == pytest.approx(16)
    assert position.estimated is True


def test_playback_time_position_reports_completed_progress_at_the_end() -> None:
    sentences = [
        sentence('s1', 1, '一二三四', duration=4),
        sentence('s2', 2, '一二三四五六', duration=6),
    ]

    position = playback_time_position(sentences, progress('s2', offset=6, completed=True))

    assert position is not None
    assert position.elapsed_seconds == pytest.approx(10)
    assert position.total_seconds == pytest.approx(10)
    assert position.estimated is False

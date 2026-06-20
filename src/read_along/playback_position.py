from __future__ import annotations

from collections.abc import Sequence

from read_along.models import PlaybackTimePosition, ReadingProgress, Sentence

DEFAULT_SECONDS_PER_CHARACTER = 0.35
MIN_ESTIMATED_SENTENCE_SECONDS = 1.0
MAX_ESTIMATED_SENTENCE_SECONDS = 60.0


def playback_time_position(
    sentences: Sequence[Sentence],
    progress: ReadingProgress | None,
) -> PlaybackTimePosition | None:
    """从句子序列和阅读进度派生时间式朗读位置。"""
    if progress is None or not sentences:
        return None
    durations = _sentence_durations(sentences)
    current_index = next(
        (index for index, sentence in enumerate(sentences) if sentence.id == progress.sentence_id),
        None,
    )
    if current_index is None:
        return None

    total = sum(durations)
    if progress.playback_completed:
        elapsed = total
    else:
        elapsed = sum(durations[:current_index]) + min(progress.sentence_offset_seconds, durations[current_index])
    return PlaybackTimePosition(
        elapsed_seconds=elapsed,
        total_seconds=total,
        estimated=any(sentence.audio_duration_seconds is None for sentence in sentences),
    )


def _sentence_durations(sentences: Sequence[Sentence]) -> list[float]:
    seconds_per_character = _adaptive_seconds_per_character(sentences)
    return [
        sentence.audio_duration_seconds
        if sentence.audio_duration_seconds is not None
        else _estimated_sentence_duration(sentence, seconds_per_character)
        for sentence in sentences
    ]


def _adaptive_seconds_per_character(sentences: Sequence[Sentence]) -> float:
    known = [
        (sentence.audio_duration_seconds, len(sentence.text.strip()))
        for sentence in sentences
        if sentence.audio_duration_seconds is not None and len(sentence.text.strip()) > 0
    ]
    if not known:
        return DEFAULT_SECONDS_PER_CHARACTER
    return sum(duration for duration, _ in known) / sum(length for _, length in known)


def _estimated_sentence_duration(sentence: Sentence, seconds_per_character: float) -> float:
    return max(
        MIN_ESTIMATED_SENTENCE_SECONDS,
        min(MAX_ESTIMATED_SENTENCE_SECONDS, len(sentence.text.strip()) * seconds_per_character),
    )

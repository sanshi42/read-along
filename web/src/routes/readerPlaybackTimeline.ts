export interface TimelineSentence {
  id: string;
  text: string;
  audio_duration_seconds: number | null;
}

export interface TimelineProgress {
  sentence_id: string;
  sentence_offset_seconds: number;
  playback_completed: boolean;
}

export interface PlaybackTimelineItem {
  sentenceId: string;
  startSeconds: number;
  durationSeconds: number;
  estimated: boolean;
}

export interface PlaybackTimeline {
  items: PlaybackTimelineItem[];
  currentSentenceId: string | null;
  currentOffsetSeconds: number;
  elapsedSeconds: number;
  totalSeconds: number;
  estimated: boolean;
}

export interface TimelineSeekResult {
  sentenceId: string;
  offsetSeconds: number;
  completed: boolean;
}

export interface TimelineProgressInput {
  sentence_id: string;
  sentence_offset_seconds: number;
  playback_rate: number;
  playback_completed: boolean;
}

const DEFAULT_SECONDS_PER_CHARACTER = 0.35;
const MIN_ESTIMATED_SENTENCE_SECONDS = 1;
const MAX_ESTIMATED_SENTENCE_SECONDS = 60;

export function buildPlaybackTimeline(
  sentences: TimelineSentence[],
  progress: TimelineProgress | null,
): PlaybackTimeline {
  const secondsPerCharacter = adaptiveSecondsPerCharacter(sentences);
  let cursor = 0;
  const items = sentences.map((sentence) => {
    const realDuration = sentence.audio_duration_seconds;
    const durationSeconds =
      realDuration ?? estimatedSentenceDuration(sentence.text, secondsPerCharacter);
    const item: PlaybackTimelineItem = {
      sentenceId: sentence.id,
      startSeconds: cursor,
      durationSeconds,
      estimated: realDuration === null,
    };
    cursor += durationSeconds;
    return item;
  });

  const totalSeconds = cursor;
  if (items.length === 0) {
    return {
      items,
      currentSentenceId: null,
      currentOffsetSeconds: 0,
      elapsedSeconds: 0,
      totalSeconds: 0,
      estimated: false,
    };
  }

  if (!progress || progress.playback_completed) {
    return {
      items,
      currentSentenceId: items[0].sentenceId,
      currentOffsetSeconds: 0,
      elapsedSeconds: 0,
      totalSeconds,
      estimated: items.some((item) => item.estimated),
    };
  }

  const currentItem = items.find((item) => item.sentenceId === progress.sentence_id) ?? items[0];
  const currentOffsetSeconds = clamp(progress.sentence_offset_seconds, 0, currentItem.durationSeconds);
  return {
    items,
    currentSentenceId: currentItem.sentenceId,
    currentOffsetSeconds,
    elapsedSeconds: currentItem.startSeconds + currentOffsetSeconds,
    totalSeconds,
    estimated: items.some((item) => item.estimated),
  };
}

export function seekTimeline(timeline: PlaybackTimeline, targetSeconds: number): TimelineSeekResult | null {
  if (timeline.items.length === 0) {
    return null;
  }
  if (targetSeconds <= 0) {
    return {
      sentenceId: timeline.items[0].sentenceId,
      offsetSeconds: 0,
      completed: false,
    };
  }
  if (targetSeconds >= timeline.totalSeconds) {
    const last = timeline.items[timeline.items.length - 1];
    return {
      sentenceId: last.sentenceId,
      offsetSeconds: last.durationSeconds,
      completed: true,
    };
  }
  const item =
    timeline.items.find(
      (candidate) =>
        targetSeconds >= candidate.startSeconds &&
        targetSeconds < candidate.startSeconds + candidate.durationSeconds,
    ) ?? timeline.items[timeline.items.length - 1];
  return {
    sentenceId: item.sentenceId,
    offsetSeconds: targetSeconds - item.startSeconds,
    completed: false,
  };
}

export function progressInputForTimeline(
  timeline: PlaybackTimeline,
  currentSentenceId: string | null,
  currentOffsetSeconds: number,
  playbackRate: number,
  playbackCompleted: boolean,
): TimelineProgressInput | null {
  if (!currentSentenceId) {
    return null;
  }
  if (playbackCompleted) {
    const last = timeline.items[timeline.items.length - 1];
    if (last) {
      return {
        sentence_id: last.sentenceId,
        sentence_offset_seconds: last.durationSeconds,
        playback_rate: playbackRate,
        playback_completed: true,
      };
    }
  }
  return {
    sentence_id: currentSentenceId,
    sentence_offset_seconds: currentOffsetSeconds,
    playback_rate: playbackRate,
    playback_completed: playbackCompleted,
  };
}

export function formatTimelineTime(seconds: number): string {
  const rounded = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const remainingSeconds = rounded % 60;
  if (hours > 0) {
    return `${hours}:${pad2(minutes)}:${pad2(remainingSeconds)}`;
  }
  return `${pad2(minutes)}:${pad2(remainingSeconds)}`;
}

export function isInteractiveShortcutTarget(
  tagName: string,
  attributes: { role?: string | null; contentEditable?: string | null } = {},
): boolean {
  const tag = tagName.toUpperCase();
  if (["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(tag)) {
    return true;
  }
  if (attributes.role === "slider") {
    return true;
  }
  return attributes.contentEditable === "true";
}

function adaptiveSecondsPerCharacter(sentences: TimelineSentence[]): number {
  const known = sentences.filter(
    (sentence) =>
      sentence.audio_duration_seconds !== null &&
      sentence.audio_duration_seconds > 0 &&
      sentence.text.trim().length > 0,
  );
  if (known.length === 0) {
    return DEFAULT_SECONDS_PER_CHARACTER;
  }
  const duration = known.reduce((total, sentence) => total + (sentence.audio_duration_seconds ?? 0), 0);
  const characters = known.reduce((total, sentence) => total + sentence.text.trim().length, 0);
  return characters > 0 ? duration / characters : DEFAULT_SECONDS_PER_CHARACTER;
}

function estimatedSentenceDuration(text: string, secondsPerCharacter: number): number {
  return clamp(
    text.trim().length * secondsPerCharacter,
    MIN_ESTIMATED_SENTENCE_SECONDS,
    MAX_ESTIMATED_SENTENCE_SECONDS,
  );
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

function pad2(value: number): string {
  return value.toString().padStart(2, "0");
}

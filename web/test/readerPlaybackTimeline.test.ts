import assert from "node:assert/strict";
import test from "node:test";

import {
  buildPlaybackTimeline,
  formatTimelineTime,
  isInteractiveShortcutTarget,
  progressInputForTimeline,
  resumeSentenceIdForProgress,
  seekTimeline,
} from "../src/routes/readerPlaybackTimeline.ts";

const sentences = [
  { id: "s1", text: "一二三四", audio_duration_seconds: 4 },
  { id: "s2", text: "一二三四五六", audio_duration_seconds: null },
  { id: "s3", text: "一二三四五六", audio_duration_seconds: 6 },
];

test("buildPlaybackTimeline uses real durations and adaptive estimates", () => {
  const timeline = buildPlaybackTimeline(sentences, {
    sentence_id: "s2",
    sentence_offset_seconds: 2,
    playback_completed: false,
  });

  assert.equal(timeline.estimated, true);
  assert.equal(timeline.items[0].durationSeconds, 4);
  assert.equal(timeline.items[0].estimated, false);
  assert.equal(timeline.items[1].estimated, true);
  assert.equal(timeline.elapsedSeconds, 6);
  assert.equal(timeline.totalSeconds, 16);
});

test("buildPlaybackTimeline maps completed progress to the start for resuming", () => {
  const timeline = buildPlaybackTimeline(sentences, {
    sentence_id: "s3",
    sentence_offset_seconds: 6,
    playback_completed: true,
  });

  assert.equal(timeline.currentSentenceId, "s1");
  assert.equal(timeline.currentOffsetSeconds, 0);
  assert.equal(timeline.elapsedSeconds, 0);
});

test("resumeSentenceIdForProgress centralizes completed and missing progress fallback", () => {
  const sentenceIds = sentences.map((sentence) => sentence.id);

  assert.equal(resumeSentenceIdForProgress(sentenceIds, null), "s1");
  assert.equal(
    resumeSentenceIdForProgress(sentenceIds, {
      sentence_id: "s2",
      sentence_offset_seconds: 2,
      playback_completed: false,
    }),
    "s2",
  );
  assert.equal(
    resumeSentenceIdForProgress(sentenceIds, {
      sentence_id: "s3",
      sentence_offset_seconds: 6,
      playback_completed: true,
    }),
    "s1",
  );
  assert.equal(
    resumeSentenceIdForProgress(sentenceIds, {
      sentence_id: "missing",
      sentence_offset_seconds: 0,
      playback_completed: false,
    }),
    "s1",
  );
});

test("seekTimeline clamps at material boundaries and marks completion at the end", () => {
  const timeline = buildPlaybackTimeline(sentences, {
    sentence_id: "s1",
    sentence_offset_seconds: 0,
    playback_completed: false,
  });

  assert.deepEqual(seekTimeline(timeline, -15), {
    sentenceId: "s1",
    offsetSeconds: 0,
    completed: false,
  });
  assert.deepEqual(seekTimeline(timeline, timeline.totalSeconds + 10), {
    sentenceId: "s3",
    offsetSeconds: 6,
    completed: true,
  });
  assert.deepEqual(seekTimeline(timeline, 5), {
    sentenceId: "s2",
    offsetSeconds: 1,
    completed: false,
  });
});

test("progressInputForTimeline saves completed progress at the final sentence", () => {
  const timeline = buildPlaybackTimeline(sentences, {
    sentence_id: "s3",
    sentence_offset_seconds: 6,
    playback_completed: true,
  });

  assert.deepEqual(progressInputForTimeline(timeline, "s1", 0, 1.25, true), {
    sentence_id: "s3",
    sentence_offset_seconds: 6,
    playback_rate: 1.25,
    playback_completed: true,
  });
});

test("formatTimelineTime uses compact media time labels", () => {
  assert.equal(formatTimelineTime(75), "01:15");
  assert.equal(formatTimelineTime(3670), "1:01:10");
});

test("isInteractiveShortcutTarget keeps global shortcuts away from controls", () => {
  assert.equal(isInteractiveShortcutTarget("INPUT"), true);
  assert.equal(isInteractiveShortcutTarget("SELECT"), true);
  assert.equal(isInteractiveShortcutTarget("BUTTON"), true);
  assert.equal(isInteractiveShortcutTarget("DIV", { role: "slider" }), true);
  assert.equal(isInteractiveShortcutTarget("SPAN"), false);
});

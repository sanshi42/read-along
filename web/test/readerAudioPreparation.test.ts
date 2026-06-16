import assert from "node:assert/strict";
import test from "node:test";

import {
  SentenceAudioPreparationQueue,
  audioPreloadWindow,
  initialAudioPreloadAnchor,
} from "../src/routes/readerAudioPreparation.ts";
import type { ReadingProgress } from "../src/api.ts";

const sentenceIds = ["s1", "s2", "s3", "s4", "s5", "s6"];

function progress(
  sentenceId: string,
  playbackCompleted = false,
): Pick<ReadingProgress, "sentence_id" | "playback_completed"> {
  return {
    sentence_id: sentenceId,
    playback_completed: playbackCompleted,
  };
}

test("initialAudioPreloadAnchor starts from saved progress unless playback is completed", () => {
  assert.equal(initialAudioPreloadAnchor(sentenceIds, progress("s3")), "s3");
  assert.equal(initialAudioPreloadAnchor(sentenceIds, progress("s3", true)), "s1");
  assert.equal(initialAudioPreloadAnchor(sentenceIds, null), "s1");
});

test("audioPreloadWindow returns current sentence and the next four sentences", () => {
  assert.deepEqual(audioPreloadWindow(sentenceIds, "s2"), ["s2", "s3", "s4", "s5", "s6"]);
  assert.deepEqual(audioPreloadWindow(sentenceIds, "s5"), ["s5", "s6"]);
  assert.deepEqual(audioPreloadWindow(sentenceIds, null), []);
});

test("SentenceAudioPreparationQueue retries a failed background preload once", async () => {
  const calls: string[] = [];
  const queue = new SentenceAudioPreparationQueue(async (sentenceId) => {
    calls.push(sentenceId);
    throw new Error(`无法准备 ${sentenceId}`);
  });

  await queue.preloadWindow(["s1"]);

  assert.deepEqual(calls, ["s1", "s1"]);
  assert.equal(queue.snapshot("s1").status, "failed");
  assert.equal(queue.snapshot("s1").errorMessage, "无法准备 s1");
});

test("SentenceAudioPreparationQueue lets foreground playback retry a failed preload", async () => {
  const calls: string[] = [];
  const queue = new SentenceAudioPreparationQueue(async (sentenceId) => {
    calls.push(sentenceId);
    if (calls.length <= 2) {
      throw new Error("暂时失败");
    }
  });

  await queue.preloadWindow(["s1"]);
  await queue.prepareForPlayback("s1");

  assert.deepEqual(calls, ["s1", "s1", "s1"]);
  assert.equal(queue.snapshot("s1").status, "ready");
  assert.equal(queue.snapshot("s1").errorMessage, null);
});

test("SentenceAudioPreparationQueue keeps foreground playback attached to a background retry", async () => {
  let attempts = 0;
  let rejectFirstAttempt!: (reason: Error) => void;
  let resolveFirstAttemptStarted!: () => void;
  const firstAttemptStarted = new Promise<void>((resolve) => {
    resolveFirstAttemptStarted = resolve;
  });
  const queue = new SentenceAudioPreparationQueue(async () => {
    attempts += 1;
    if (attempts === 1) {
      resolveFirstAttemptStarted();
      await new Promise<void>((_, reject) => {
        rejectFirstAttempt = reject;
      });
    }
  });

  void queue.preloadWindow(["s1"]);
  await firstAttemptStarted;
  const foreground = queue.prepareForPlayback("s1");
  rejectFirstAttempt(new Error("首次失败"));
  await foreground;

  assert.equal(attempts, 2);
  assert.equal(queue.snapshot("s1").status, "ready");
});

test("SentenceAudioPreparationQueue lets foreground requests bypass a different background preload", async () => {
  const calls: string[] = [];
  let releaseBackground!: () => void;
  const backgroundStarted = new Promise<void>((resolve) => {
    const queue = new SentenceAudioPreparationQueue(async (sentenceId) => {
      calls.push(sentenceId);
      if (sentenceId === "s1") {
        resolve();
        await new Promise<void>((release) => {
          releaseBackground = release;
        });
      }
    });

    void queue.preloadWindow(["s1"]);
    void queue.prepareForPlayback("s2");
  });

  await backgroundStarted;
  assert.deepEqual(calls, ["s1", "s2"]);
  releaseBackground();
});

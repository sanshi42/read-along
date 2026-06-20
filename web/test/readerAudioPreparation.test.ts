import assert from "node:assert/strict";
import test from "node:test";

import {
  SentenceAudioElementCache,
  SentenceAudioPreparationQueue,
  audioRepairPreloadWindow,
  audioPreloadWindow,
  initialAudioPreloadAnchor,
} from "../src/routes/readerAudioPreparation.ts";
import type { ReadingProgress } from "../src/api.ts";

const sentenceIds = ["s1", "s2", "s3", "s4", "s5", "s6"];

class FakeAudioElement {
  playbackRate = 1;
  preload = "metadata";
  loadCalls = 0;
  pauseCalls = 0;
  removedAttributes: string[] = [];

  load() {
    this.loadCalls += 1;
  }

  pause() {
    this.pauseCalls += 1;
  }

  removeAttribute(name: string) {
    this.removedAttributes.push(name);
  }
}

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

test("audioRepairPreloadWindow keeps repair work near the visible current sentence", () => {
  assert.deepEqual(
    audioRepairPreloadWindow(sentenceIds, "s4", ["s3", "s4", "s5"], {
      contextBefore: 2,
      contextAfter: 1,
    }),
    ["s2", "s3", "s4", "s5"],
  );
});

test("audioRepairPreloadWindow follows the visible area when current sentence is offscreen", () => {
  assert.deepEqual(
    audioRepairPreloadWindow(sentenceIds, "s6", ["s2", "s3"], {
      contextBefore: 1,
      contextAfter: 1,
    }),
    ["s1", "s2", "s3"],
  );
  assert.deepEqual(
    audioRepairPreloadWindow(sentenceIds, "missing", ["s3"], {
      contextBefore: 1,
      contextAfter: 1,
    }),
    ["s2", "s3", "s4"],
  );
  assert.deepEqual(audioRepairPreloadWindow(sentenceIds, null), []);
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

test("SentenceAudioPreparationQueue clear makes ready sentences prepare again", async () => {
  const calls: string[] = [];
  const queue = new SentenceAudioPreparationQueue(async (sentenceId) => {
    calls.push(sentenceId);
  });

  await queue.prepareForPlayback("s1");
  queue.clear();
  await queue.prepareForPlayback("s1");

  assert.deepEqual(calls, ["s1", "s1"]);
});

test("SentenceAudioElementCache loads and reuses prepared audio for playback", () => {
  const created: string[] = [];
  const cache = new SentenceAudioElementCache((sentenceId) => {
    created.push(sentenceId);
    return new FakeAudioElement();
  });

  const prepared = cache.prepare("s2", 1.25);
  const reused = cache.take("s2", 1.5);

  assert.deepEqual(created, ["s2"]);
  assert.equal(reused, prepared);
  assert.equal(reused.preload, "auto");
  assert.equal(reused.loadCalls, 1);
  assert.equal(reused.playbackRate, 1.5);
  assert.equal(cache.has("s2"), false);
});

test("SentenceAudioElementCache clears unused prepared audio", () => {
  const cache = new SentenceAudioElementCache(() => new FakeAudioElement());
  const prepared = cache.prepare("s2", 1);

  cache.clear();

  assert.equal(prepared.pauseCalls, 1);
  assert.deepEqual(prepared.removedAttributes, ["src"]);
  assert.equal(prepared.loadCalls, 2);
  assert.equal(cache.has("s2"), false);
});

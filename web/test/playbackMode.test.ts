import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_PLAYBACK_MODE,
  playbackModeLabel,
  playbackModeTargetForNaturalEnd,
  playbackModeTargetForNext,
  playbackModeTargetForPrevious,
  type PlaybackMode,
  type PlaybackModeNavigation,
} from "../src/routes/playbackMode.ts";
import {
  loadPlaybackModePreference,
  savePlaybackModePreference,
} from "../src/playbackModePreference.ts";

const navigation: PlaybackModeNavigation = {
  currentId: "m2",
  previousId: "m1",
  nextId: "m3",
  firstId: "m1",
  lastId: "m3",
};

test("playback mode labels expose the three supported modes", () => {
  assert.equal(playbackModeLabel("repeat_one"), "单曲循环");
  assert.equal(playbackModeLabel("sequential"), "顺序播放");
  assert.equal(playbackModeLabel("repeat_list"), "列表循环");
});

test("natural material end follows the selected playback mode", () => {
  assert.deepEqual(playbackModeTargetForNaturalEnd("repeat_one", navigation), {
    materialId: "m2",
    autoplay: true,
  });
  assert.deepEqual(playbackModeTargetForNaturalEnd("sequential", navigation), {
    materialId: "m3",
    autoplay: true,
  });
  assert.deepEqual(playbackModeTargetForNaturalEnd("repeat_list", navigation), {
    materialId: "m3",
    autoplay: true,
  });
});

test("natural material end handles list edges and single item lists", () => {
  const lastNavigation: PlaybackModeNavigation = {
    currentId: "m3",
    previousId: "m2",
    nextId: null,
    firstId: "m1",
    lastId: "m3",
  };
  const singleNavigation: PlaybackModeNavigation = {
    currentId: "m1",
    previousId: null,
    nextId: null,
    firstId: "m1",
    lastId: "m1",
  };

  assert.equal(playbackModeTargetForNaturalEnd("sequential", lastNavigation), null);
  assert.deepEqual(playbackModeTargetForNaturalEnd("repeat_list", lastNavigation), {
    materialId: "m1",
    autoplay: true,
  });
  assert.deepEqual(playbackModeTargetForNaturalEnd("repeat_list", singleNavigation), {
    materialId: "m1",
    autoplay: true,
  });
});

test("manual previous and next respect sequential and list repeat edges", () => {
  const firstNavigation: PlaybackModeNavigation = {
    currentId: "m1",
    previousId: null,
    nextId: "m2",
    firstId: "m1",
    lastId: "m3",
  };
  const lastNavigation: PlaybackModeNavigation = {
    currentId: "m3",
    previousId: "m2",
    nextId: null,
    firstId: "m1",
    lastId: "m3",
  };

  assert.equal(playbackModeTargetForPrevious("sequential", firstNavigation), null);
  assert.deepEqual(playbackModeTargetForPrevious("repeat_list", firstNavigation), {
    materialId: "m3",
    autoplay: false,
  });
  assert.equal(playbackModeTargetForNext("sequential", lastNavigation), null);
  assert.deepEqual(playbackModeTargetForNext("repeat_list", lastNavigation), {
    materialId: "m1",
    autoplay: false,
  });
});

test("manual previous and next handle single item lists", () => {
  const singleNavigation: PlaybackModeNavigation = {
    currentId: "m1",
    previousId: null,
    nextId: null,
    firstId: "m1",
    lastId: "m1",
  };

  assert.equal(playbackModeTargetForPrevious("sequential", singleNavigation), null);
  assert.equal(playbackModeTargetForNext("sequential", singleNavigation), null);
  assert.equal(playbackModeTargetForPrevious("repeat_one", singleNavigation), null);
  assert.equal(playbackModeTargetForNext("repeat_one", singleNavigation), null);
  assert.deepEqual(playbackModeTargetForPrevious("repeat_list", singleNavigation), {
    materialId: "m1",
    autoplay: false,
  });
  assert.deepEqual(playbackModeTargetForNext("repeat_list", singleNavigation), {
    materialId: "m1",
    autoplay: false,
  });
});

test("single repeat does not lock manual previous and next navigation", () => {
  assert.deepEqual(playbackModeTargetForPrevious("repeat_one", navigation), {
    materialId: "m1",
    autoplay: false,
  });
  assert.deepEqual(playbackModeTargetForNext("repeat_one", navigation), {
    materialId: "m3",
    autoplay: false,
  });
});

test("playback mode preference defaults, saves, and rejects invalid values", () => {
  const storage = new Map<string, string>();
  const originalWindow = globalThis.window;
  globalThis.window = {
    localStorage: {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        storage.set(key, value);
      },
    },
  } as Window & typeof globalThis;

  try {
    assert.equal(DEFAULT_PLAYBACK_MODE, "sequential");
    assert.equal(loadPlaybackModePreference(), DEFAULT_PLAYBACK_MODE);
    assert.equal(savePlaybackModePreference("repeat_list"), true);
    assert.equal(loadPlaybackModePreference(), "repeat_list");
    storage.set("read-along.playback-mode.v1", JSON.stringify("unknown" as PlaybackMode));
    assert.equal(loadPlaybackModePreference(), DEFAULT_PLAYBACK_MODE);
  } finally {
    globalThis.window = originalWindow;
  }
});

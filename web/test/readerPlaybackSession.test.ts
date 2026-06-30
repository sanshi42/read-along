import assert from "node:assert/strict";
import test from "node:test";

import {
  ReaderPlaybackSession,
  type PlaybackAudio,
  type PlaybackSessionAdapters,
} from "../src/routes/readerPlaybackSession.ts";

class FakeAudio implements PlaybackAudio {
  currentTime = 0;
  ended = false;
  playbackRate = 1;
  preload = "metadata";
  ontimeupdate: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  pauseCalls = 0;
  playCalls = 0;
  loadCalls = 0;
  removedAttributes: string[] = [];
  playError: Error | null = null;

  async play() {
    this.playCalls += 1;
    if (this.playError) {
      throw this.playError;
    }
  }

  pause() {
    this.pauseCalls += 1;
  }

  load() {
    this.loadCalls += 1;
  }

  removeAttribute(name: string) {
    this.removedAttributes.push(name);
  }
}

function createAdapters(
  overrides: Partial<PlaybackSessionAdapters> = {},
): PlaybackSessionAdapters {
  return {
    prepareAudio: async () => null,
    createAudio: () => new FakeAudio(),
    saveProgress: async () => {},
    clearAudioCache: async () => {},
    savePlaybackMode: () => true,
    navigate: () => {},
    now: () => 0,
    createReloadToken: () => "0",
    ...overrides,
  };
}

function createSession(
  adapters: PlaybackSessionAdapters,
  progress: {
    sentence_id: string;
    sentence_offset_seconds: number;
    playback_rate: number;
    playback_completed: boolean;
  } | null = null,
  options: {
    materialId?: string;
    playbackMode?: "repeat_one" | "sequential" | "repeat_list";
    navigation?: {
      currentId: string;
      previousId: string | null;
      nextId: string | null;
      firstId: string | null;
      lastId: string | null;
    };
  } = {},
) {
  return new ReaderPlaybackSession({
    materialId: options.materialId ?? "material-1",
    sentences: [
      { id: "s1", text: "第一句。", audio_duration_seconds: 2 },
      { id: "s2", text: "第二句。", audio_duration_seconds: 3 },
      { id: "s3", text: "第三句。", audio_duration_seconds: null },
    ],
    progress,
    navigation:
      options.navigation ??
      {
        currentId: "material-1",
        previousId: null,
        nextId: "material-2",
        firstId: "material-1",
        lastId: "material-2",
      },
    playbackMode: options.playbackMode ?? "sequential",
    adapters,
  });
}

async function nextTurn() {
  await new Promise<void>((resolve) => {
    setImmediate(resolve);
  });
}

test("朗读会话从阅读进度恢复并从当前句开始预取", async () => {
  const prepared: string[] = [];
  const session = createSession(
    createAdapters({
      prepareAudio: async (sentenceId) => {
        prepared.push(sentenceId);
        return null;
      },
    }),
    {
      sentence_id: "s2",
      sentence_offset_seconds: 1.5,
      playback_rate: 1.25,
      playback_completed: false,
    },
  );
  const snapshots: string[] = [];

  const unsubscribe = session.subscribe((snapshot) => {
    snapshots.push(snapshot.currentSentenceId ?? "none");
  });
  await nextTurn();

  assert.equal(session.snapshot().currentSentenceId, "s2");
  assert.equal(session.snapshot().currentSentenceOffsetSeconds, 1.5);
  assert.equal(session.snapshot().playbackRate, 1.25);
  assert.equal(session.snapshot().playbackStatus, "paused");
  assert.deepEqual(prepared, ["s2", "s3"]);
  assert.deepEqual(snapshots, ["s2"]);

  unsubscribe();
  session.dispose();
});

test("没有 Reading Progress 时只预取第一句但不提前选中当前句", async () => {
  const prepared: string[] = [];
  const session = createSession(
    createAdapters({
      prepareAudio: async (sentenceId) => {
        prepared.push(sentenceId);
        return null;
      },
    }),
  );

  await nextTurn();

  assert.equal(session.snapshot().currentSentenceId, null);
  assert.equal(session.snapshot().playbackStatus, "idle");
  assert.deepEqual(prepared, ["s1", "s2", "s3"]);
  session.dispose();
});

test("销毁朗读会话后忽略尚未完成的音频准备结果", async () => {
  let finishPreparation!: (duration: number) => void;
  const preparation = new Promise<number>((resolve) => {
    finishPreparation = resolve;
  });
  const session = createSession(
    createAdapters({
      prepareAudio: async () => preparation,
    }),
  );
  let notifications = 0;
  session.subscribe(() => {
    notifications += 1;
  });

  session.dispose();
  finishPreparation(12);
  await nextTurn();

  assert.equal(notifications, 1);
  assert.equal(session.snapshot().timeline.items[0].durationSeconds, 2);
  assert.equal(session.snapshot().timeline.items[2].estimated, true);
});

test("朗读会话协调播放暂停和播放中的选句", async () => {
  const audios: FakeAudio[] = [];
  const saved: Array<{ sentence_id: string; sentence_offset_seconds: number }> = [];
  const session = createSession(
    createAdapters({
      createAudio: () => {
        const audio = new FakeAudio();
        audios.push(audio);
        return audio;
      },
      saveProgress: async (progress) => {
        saved.push(progress);
      },
    }),
  );

  await session.playPause();
  await nextTurn();

  assert.equal(session.snapshot().playbackStatus, "playing");
  assert.equal(session.snapshot().currentSentenceId, "s1");
  assert.equal(audios[0].playCalls, 1);

  await session.selectSentence("s2");
  await nextTurn();

  assert.equal(session.snapshot().playbackStatus, "playing");
  assert.equal(session.snapshot().currentSentenceId, "s2");
  assert.equal(audios[0].pauseCalls, 1);
  assert.equal(audios[1].playCalls, 1);

  await session.playPause();
  await nextTurn();

  assert.equal(session.snapshot().playbackStatus, "paused");
  assert.equal(audios[1].pauseCalls, 1);
  assert.equal(saved.at(-1)?.sentence_id, "s2");
  session.dispose();
});

test("朗读会话集中处理时间跳转和倍速", async () => {
  const session = createSession(createAdapters());

  await session.seek(3);
  session.setPlaybackRate(1.5);
  await nextTurn();

  assert.equal(session.snapshot().currentSentenceId, "s2");
  assert.equal(session.snapshot().currentSentenceOffsetSeconds, 1);
  assert.equal(session.snapshot().playbackRate, 1.5);
  assert.equal(session.snapshot().playbackStatus, "paused");
  session.dispose();
});

test("Reading Progress 保存失败后阻塞并允许手动重试", async () => {
  let shouldFail = true;
  let attempts = 0;
  const session = createSession(
    createAdapters({
      saveProgress: async () => {
        attempts += 1;
        if (shouldFail) {
          throw new Error("暂时无法保存");
        }
      },
    }),
  );

  await session.selectSentence("s2");
  await nextTurn();

  assert.equal(session.snapshot().progressError, "阅读进度保存失败，请重试。");
  assert.equal(attempts, 1);

  shouldFail = false;
  session.retryProgressSave();
  await nextTurn();

  assert.equal(session.snapshot().progressError, null);
  assert.equal(attempts, 2);
  session.dispose();
});

test("播放时间更新按现有五秒间隔节流保存 Reading Progress", async () => {
  let now = 0;
  const audios: FakeAudio[] = [];
  const savedOffsets: number[] = [];
  const session = createSession(
    createAdapters({
      now: () => now,
      createAudio: () => {
        const audio = new FakeAudio();
        audios.push(audio);
        return audio;
      },
      saveProgress: async (progress) => {
        savedOffsets.push(progress.sentence_offset_seconds);
      },
    }),
  );

  await session.playPause();
  await nextTurn();
  assert.deepEqual(savedOffsets, [0]);

  now = 1000;
  audios[0].currentTime = 0.5;
  audios[0].ontimeupdate?.();
  await nextTurn();
  assert.deepEqual(savedOffsets, [0]);

  now = 6000;
  audios[0].currentTime = 1;
  audios[0].ontimeupdate?.();
  await nextTurn();
  assert.deepEqual(savedOffsets, [0, 1]);
  session.dispose();
});

test("自然句末继续播放下一句", async () => {
  const audios: FakeAudio[] = [];
  const session = createSession(
    createAdapters({
      createAudio: () => {
        const audio = new FakeAudio();
        audios.push(audio);
        return audio;
      },
    }),
  );

  await session.playPause();
  const active = audios.find((audio) => audio.onended !== null);
  active?.onended?.();
  await nextTurn();

  assert.equal(session.snapshot().currentSentenceId, "s2");
  assert.equal(session.snapshot().playbackStatus, "playing");
  session.dispose();
});

test("顺序播放在篇末保存完成状态并导航到下一篇", async () => {
  const audios: FakeAudio[] = [];
  const navigations: Array<{ materialId: string; autoplay: boolean }> = [];
  const session = createSession(
    createAdapters({
      createAudio: () => {
        const audio = new FakeAudio();
        audios.push(audio);
        return audio;
      },
      navigate: (materialId, autoplay) => {
        navigations.push({ materialId, autoplay });
      },
    }),
  );

  await session.selectSentence("s3");
  await session.playPause();
  audios.find((audio) => audio.onended !== null)?.onended?.();
  await nextTurn();

  assert.equal(session.snapshot().playbackCompleted, true);
  assert.equal(session.snapshot().playbackStatus, "paused");
  assert.deepEqual(navigations, [{ materialId: "material-2", autoplay: true }]);
  session.dispose();
});

test("单篇循环在篇末从第一句继续播放", async () => {
  const audios: FakeAudio[] = [];
  const navigations: string[] = [];
  const session = createSession(
    createAdapters({
      createAudio: () => {
        const audio = new FakeAudio();
        audios.push(audio);
        return audio;
      },
      navigate: (materialId) => {
        navigations.push(materialId);
      },
    }),
    null,
    { playbackMode: "repeat_one" },
  );

  await session.selectSentence("s3");
  await session.playPause();
  audios.find((audio) => audio.onended !== null)?.onended?.();
  await nextTurn();

  assert.equal(session.snapshot().currentSentenceId, "s1");
  assert.equal(session.snapshot().playbackStatus, "playing");
  assert.deepEqual(navigations, []);
  session.dispose();
});

test("列表循环在末篇结束后导航到第一篇", async () => {
  const navigations: Array<{ materialId: string; autoplay: boolean }> = [];
  const audios: FakeAudio[] = [];
  const session = createSession(
    createAdapters({
      createAudio: () => {
        const audio = new FakeAudio();
        audios.push(audio);
        return audio;
      },
      navigate: (materialId, autoplay) => {
        navigations.push({ materialId, autoplay });
      },
    }),
    null,
    {
      materialId: "material-2",
      playbackMode: "repeat_list",
      navigation: {
        currentId: "material-2",
        previousId: "material-1",
        nextId: null,
        firstId: "material-1",
        lastId: "material-2",
      },
    },
  );

  await session.selectSentence("s3");
  await session.playPause();
  audios.find((audio) => audio.onended !== null)?.onended?.();
  await nextTurn();

  assert.deepEqual(navigations, [{ materialId: "material-1", autoplay: true }]);
  session.dispose();
});

test("切换 Playback Mode 保存偏好并更新前后材料目标", () => {
  const savedModes: string[] = [];
  const session = createSession(
    createAdapters({
      savePlaybackMode: (mode) => {
        savedModes.push(mode);
        return true;
      },
    }),
  );

  session.setPlaybackMode("repeat_list");

  assert.equal(session.snapshot().playbackMode, "repeat_list");
  assert.equal(session.snapshot().previousTarget?.materialId, "material-2");
  assert.equal(session.snapshot().nextTarget?.materialId, "material-2");
  assert.deepEqual(savedModes, ["repeat_list"]);
  session.dispose();
});

test("音频修复清理缓存并恢复此前正在进行的朗读", async () => {
  const prepared: Array<{ sentenceId: string; reloadToken: string | null }> = [];
  const audios: FakeAudio[] = [];
  let clearCalls = 0;
  const session = createSession(
    createAdapters({
      createReloadToken: () => "123",
      prepareAudio: async (sentenceId, reloadToken) => {
        prepared.push({ sentenceId, reloadToken });
        return 4;
      },
      createAudio: () => {
        const audio = new FakeAudio();
        audios.push(audio);
        return audio;
      },
      clearAudioCache: async () => {
        clearCalls += 1;
      },
    }),
    {
      sentence_id: "s2",
      sentence_offset_seconds: 1,
      playback_rate: 1,
      playback_completed: false,
    },
  );
  await nextTurn();
  prepared.length = 0;

  await session.playPause();
  await session.repairAudio(["s2"]);

  assert.equal(clearCalls, 1);
  assert.equal(session.snapshot().audioRepairStatus, "success");
  assert.equal(session.snapshot().currentSentenceId, "s2");
  assert.equal(session.snapshot().playbackStatus, "playing");
  assert.equal(prepared.every((item) => item.reloadToken === "123"), true);
  session.dispose();
});

test("音频修复失败时保留当前定位并报告失败状态", async () => {
  const session = createSession(
    createAdapters({
      clearAudioCache: async () => {
        throw new Error("无法清理");
      },
    }),
    {
      sentence_id: "s2",
      sentence_offset_seconds: 1,
      playback_rate: 1,
      playback_completed: false,
    },
  );

  await session.repairAudio(["s2"]);

  assert.equal(session.snapshot().audioRepairStatus, "failed");
  assert.equal(session.snapshot().currentSentenceId, "s2");
  assert.equal(session.snapshot().currentSentenceOffsetSeconds, 1);
  assert.equal(session.snapshot().playbackStatus, "paused");
  session.dispose();
});

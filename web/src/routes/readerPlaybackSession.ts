import type { ReadingProgress } from "../api";
import {
  SentenceAudioElementCache,
  SentenceAudioPreparationQueue,
  audioRepairPreloadWindow,
  audioPreloadWindow,
  initialAudioPreloadAnchor,
  preparationErrorMessage,
} from "./readerAudioPreparation.ts";
import {
  playbackModeTargetForNaturalEnd,
  playbackModeTargetForNext,
  playbackModeTargetForPrevious,
  type PlaybackMode,
  type PlaybackModeNavigation,
  type PlaybackModeTarget,
} from "./playbackMode.ts";
import {
  buildPlaybackTimeline,
  progressInputForTimeline,
  resumeSentenceIdForProgress,
  seekTimeline,
  type PlaybackTimeline,
  type TimelineSentence,
} from "./readerPlaybackTimeline.ts";

const PROGRESS_SAVE_INTERVAL_MS = 5000;

export type PlaybackStatus = "idle" | "loading" | "playing" | "paused";
export type AudioRepairStatus = "idle" | "repairing" | "success" | "failed";

export interface PlaybackAudio {
  currentTime: number;
  ended: boolean;
  playbackRate: number;
  preload: string;
  ontimeupdate: ((this: GlobalEventHandlers, event: Event) => unknown) | null;
  onended: ((this: GlobalEventHandlers, event: Event) => unknown) | null;
  onerror: ((this: GlobalEventHandlers, event: Event) => unknown) | null;
  play: () => Promise<void>;
  pause: () => void;
  load: () => void;
  removeAttribute: (qualifiedName: string) => void;
}

type ProgressInput = Pick<
  ReadingProgress,
  "sentence_id" | "sentence_offset_seconds" | "playback_rate" | "playback_completed"
>;

export interface PlaybackSessionAdapters {
  prepareAudio: (sentenceId: string, reloadToken: string | null) => Promise<number | null>;
  createAudio: (sentenceId: string, reloadToken: string | null) => PlaybackAudio;
  saveProgress: (progress: ProgressInput) => Promise<void>;
  clearAudioCache: () => Promise<void>;
  savePlaybackMode: (mode: PlaybackMode) => boolean;
  navigate: (materialId: string, autoplay: boolean) => void;
  now: () => number;
  createReloadToken: () => string;
}

interface ReaderPlaybackSessionOptions {
  materialId: string;
  sentences: TimelineSentence[];
  progress: ProgressInput | null;
  navigation: PlaybackModeNavigation;
  playbackMode: PlaybackMode;
  adapters: PlaybackSessionAdapters;
}

export interface ReaderPlaybackSessionSnapshot {
  currentSentenceId: string | null;
  currentSentenceOffsetSeconds: number;
  playbackRate: number;
  playbackCompleted: boolean;
  playbackStatus: PlaybackStatus;
  playbackError: string | null;
  progressError: string | null;
  playbackMode: PlaybackMode;
  playbackModeError: string | null;
  audioRepairStatus: AudioRepairStatus;
  timeline: PlaybackTimeline;
  previousTarget: PlaybackModeTarget | null;
  nextTarget: PlaybackModeTarget | null;
}

export class ReaderPlaybackSession {
  private readonly materialId: string;
  private sentences: TimelineSentence[];
  private readonly navigation: PlaybackModeNavigation;
  private readonly adapters: PlaybackSessionAdapters;
  private readonly audioPreparation: SentenceAudioPreparationQueue;
  private readonly audioElements: SentenceAudioElementCache<PlaybackAudio>;
  private readonly listeners = new Set<(snapshot: ReaderPlaybackSessionSnapshot) => void>();
  private state: ReaderPlaybackSessionSnapshot;
  private reloadToken: string | null = null;
  private generation = 0;
  private progressGeneration = 0;
  private activeAudio: PlaybackAudio | null = null;
  private pendingProgress: ProgressInput | null = null;
  private savingProgress = false;
  private progressBlocked = false;
  private lastProgressSaveAt = 0;
  private disposed = false;

  constructor(options: ReaderPlaybackSessionOptions) {
    this.materialId = options.materialId;
    this.sentences = [...options.sentences];
    this.navigation = options.navigation;
    this.adapters = options.adapters;

    const sentenceIds = this.sentences.map((sentence) => sentence.id);
    const resumeSentenceId = resumeSentenceIdForProgress(sentenceIds, options.progress);
    const currentSentenceId = options.progress ? resumeSentenceId : null;
    const currentSentenceOffsetSeconds =
      options.progress &&
      !options.progress.playback_completed &&
      currentSentenceId === options.progress.sentence_id
        ? options.progress.sentence_offset_seconds
        : 0;
    this.state = {
      currentSentenceId,
      currentSentenceOffsetSeconds,
      playbackRate: options.progress?.playback_rate ?? 1,
      playbackCompleted: options.progress?.playback_completed ?? false,
      playbackStatus: options.progress && currentSentenceId ? "paused" : "idle",
      playbackError: null,
      progressError: null,
      playbackMode: options.playbackMode,
      playbackModeError: null,
      audioRepairStatus: "idle",
      timeline: buildPlaybackTimeline(this.sentences, options.progress),
      previousTarget: navigableTarget(
        playbackModeTargetForPrevious(options.playbackMode, options.navigation),
        options.materialId,
      ),
      nextTarget: navigableTarget(
        playbackModeTargetForNext(options.playbackMode, options.navigation),
        options.materialId,
      ),
    };

    this.audioPreparation = new SentenceAudioPreparationQueue(async (sentenceId) => {
      const generation = this.generation;
      const duration = await this.adapters.prepareAudio(sentenceId, this.reloadToken);
      if (duration !== null && !this.disposed && this.generation === generation) {
        this.updateSentenceDuration(sentenceId, duration);
      }
    });
    this.audioElements = new SentenceAudioElementCache((sentenceId) =>
      this.adapters.createAudio(sentenceId, this.reloadToken),
    );
    void this.audioPreparation.preloadWindow(
      audioPreloadWindow(
        sentenceIds,
        initialAudioPreloadAnchor(sentenceIds, options.progress),
      ),
    );
  }

  snapshot(): ReaderPlaybackSessionSnapshot {
    return this.state;
  }

  subscribe(listener: (snapshot: ReaderPlaybackSessionSnapshot) => void): () => void {
    this.listeners.add(listener);
    listener(this.state);
    return () => {
      this.listeners.delete(listener);
    };
  }

  async playPause() {
    if (this.disposed || this.state.playbackStatus === "loading") {
      return;
    }
    if (this.state.playbackStatus === "playing") {
      this.activeAudio?.pause();
      this.queueCurrentProgress();
      this.updateState({ playbackStatus: "paused" });
      return;
    }

    const sentenceId = this.state.playbackCompleted
      ? this.sentences[0]?.id
      : (this.state.currentSentenceId ?? this.sentences[0]?.id);
    if (!sentenceId) {
      return;
    }
    if (this.state.playbackCompleted && sentenceId === this.state.currentSentenceId) {
      this.updateCurrentPosition(sentenceId, 0, false);
    }
    await this.playSentence(
      sentenceId,
      false,
      this.state.playbackCompleted ? 0 : this.state.currentSentenceOffsetSeconds,
    );
  }

  async selectSentence(sentenceId: string) {
    if (this.disposed || !this.sentences.some((sentence) => sentence.id === sentenceId)) {
      return;
    }
    if (
      this.state.playbackStatus === "playing" ||
      this.state.playbackStatus === "loading"
    ) {
      await this.playSentence(sentenceId);
      return;
    }
    this.discardPlayback();
    this.updateState({ playbackError: null, playbackStatus: "paused" });
    this.updateCurrentPosition(sentenceId, 0, false);
  }

  async restartSentence(sentenceId: string) {
    if (this.disposed || !this.sentences.some((sentence) => sentence.id === sentenceId)) {
      return;
    }
    await this.playSentence(sentenceId, true);
  }

  async seek(targetSeconds: number) {
    if (this.disposed) {
      return;
    }
    const result = seekTimeline(this.state.timeline, targetSeconds);
    if (!result) {
      return;
    }
    this.updateState({ playbackError: null });
    if (result.completed) {
      this.discardPlayback();
      this.updateCurrentPosition(result.sentenceId, result.offsetSeconds, true);
      this.updateState({ playbackStatus: "paused" });
      return;
    }
    if (
      this.state.playbackStatus === "playing" ||
      this.state.playbackStatus === "loading"
    ) {
      await this.playSentence(result.sentenceId, false, result.offsetSeconds);
      return;
    }
    this.discardPlayback();
    this.updateState({ playbackStatus: "paused" });
    this.updateCurrentPosition(result.sentenceId, result.offsetSeconds, false);
  }

  async skip(deltaSeconds: number) {
    const baseSeconds = this.state.playbackCompleted
      ? this.state.timeline.totalSeconds
      : this.state.timeline.elapsedSeconds;
    await this.seek(baseSeconds + deltaSeconds);
  }

  setPlaybackRate(playbackRate: number) {
    if (this.disposed) {
      return;
    }
    if (this.activeAudio) {
      this.activeAudio.playbackRate = playbackRate;
    }
    this.audioElements.syncPlaybackRate(playbackRate);
    this.updateState({ playbackRate });

    const sentenceId = this.state.currentSentenceId ?? this.sentences[0]?.id;
    if (!sentenceId) {
      return;
    }
    this.updateCurrentPosition(
      sentenceId,
      this.state.currentSentenceOffsetSeconds,
      this.state.playbackCompleted,
    );
    if (this.state.playbackStatus === "idle") {
      this.updateState({ playbackStatus: "paused" });
    }
  }

  saveCurrentProgress() {
    this.queueCurrentProgress();
  }

  retryProgressSave() {
    if (this.disposed) {
      return;
    }
    this.progressBlocked = false;
    void this.flushProgress();
  }

  setPlaybackMode(playbackMode: PlaybackMode) {
    if (this.disposed) {
      return;
    }
    this.updateState({
      playbackMode,
      playbackModeError: this.adapters.savePlaybackMode(playbackMode)
        ? null
        : "播放模式已切换，但无法保存到浏览器。",
      previousTarget: navigableTarget(
        playbackModeTargetForPrevious(playbackMode, this.navigation),
        this.materialId,
      ),
      nextTarget: navigableTarget(
        playbackModeTargetForNext(playbackMode, this.navigation),
        this.materialId,
      ),
    });
  }

  navigatePrevious() {
    if (this.state.previousTarget) {
      this.navigateToTarget(this.state.previousTarget);
    }
  }

  navigateNext() {
    if (this.state.nextTarget) {
      this.navigateToTarget(this.state.nextTarget);
    }
  }

  async repairAudio(visibleSentenceIds: string[]) {
    if (this.disposed || this.state.audioRepairStatus === "repairing") {
      return;
    }
    const shouldResume = this.state.playbackStatus === "playing";
    const sentenceId = this.state.currentSentenceId ?? this.sentences[0]?.id ?? null;
    const offsetSeconds = this.state.currentSentenceOffsetSeconds;
    const sentenceIds = this.sentences.map((sentence) => sentence.id);
    const preloadSentenceIds = audioRepairPreloadWindow(
      sentenceIds,
      sentenceId,
      visibleSentenceIds,
    );

    this.updateState({ audioRepairStatus: "repairing", playbackError: null });
    this.discardPlayback();
    this.audioPreparation.clear();
    this.audioElements.clear();
    this.updateState({ playbackStatus: "paused" });

    try {
      await this.adapters.clearAudioCache();
      if (this.disposed) {
        return;
      }
      this.reloadToken = this.adapters.createReloadToken();
      this.sentences = this.sentences.map((sentence) => ({
        ...sentence,
        audio_duration_seconds: null,
      }));
      this.rebuildTimeline();
      for (const preloadSentenceId of preloadSentenceIds) {
        if (this.disposed) {
          return;
        }
        await this.audioPreparation.prepareForPlayback(preloadSentenceId);
      }
      this.updateState({ audioRepairStatus: "success" });
      if (shouldResume && sentenceId) {
        await this.playSentence(sentenceId, false, offsetSeconds);
      } else {
        void this.audioPreparation.preloadWindow(
          audioPreloadWindow(sentenceIds, sentenceId),
        );
      }
    } catch {
      if (!this.disposed) {
        this.updateState({ audioRepairStatus: "failed" });
      }
    }
  }

  dispose() {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.generation += 1;
    this.progressGeneration += 1;
    this.discardPlayback();
    this.audioPreparation.clear();
    this.audioElements.clear();
    this.pendingProgress = null;
    this.listeners.clear();
  }

  private async playSentence(sentenceId: string, restart = false, offsetSeconds = 0) {
    if (this.disposed) {
      return;
    }
    this.updateState({ playbackError: null });
    const activeAudio = this.activeAudio;
    if (activeAudio && this.state.currentSentenceId === sentenceId) {
      if (restart || activeAudio.ended) {
        activeAudio.currentTime = 0;
      } else if (offsetSeconds > 0) {
        activeAudio.currentTime = offsetSeconds;
      }
      this.updateCurrentPosition(sentenceId, activeAudio.currentTime, false);
      activeAudio.playbackRate = this.state.playbackRate;
      try {
        await activeAudio.play();
        if (this.activeAudio === activeAudio) {
          this.updateState({ playbackStatus: "playing" });
        }
      } catch {
        if (this.activeAudio === activeAudio) {
          this.updateState({
            playbackStatus: "paused",
            playbackError: "无法播放当前句音频，请重试。",
          });
        }
      }
      return;
    }

    this.discardPlayback();
    this.updateCurrentPosition(sentenceId, offsetSeconds, false);
    this.updateState({ playbackStatus: "loading" });
    const generation = this.generation;
    try {
      await this.audioPreparation.prepareForPlayback(sentenceId);
    } catch (reason: unknown) {
      if (this.generation !== generation) {
        return;
      }
      this.updateState({
        playbackStatus: "paused",
        playbackError: preparationErrorMessage(reason),
      });
      return;
    }
    if (this.generation !== generation || this.disposed) {
      return;
    }

    const audio = this.audioElements.take(sentenceId, this.state.playbackRate);
    audio.playbackRate = this.state.playbackRate;
    if (offsetSeconds > 0) {
      audio.currentTime = offsetSeconds;
    }
    this.activeAudio = audio;
    audio.ontimeupdate = () => {
      if (this.activeAudio !== audio) {
        return;
      }
      this.updateCurrentPosition(sentenceId, audio.currentTime, false, true);
    };
    audio.onended = () => {
      if (this.activeAudio === audio) {
        this.handleSentenceEnded(sentenceId);
      }
    };
    audio.onerror = () => {
      if (this.activeAudio !== audio) {
        return;
      }
      this.discardPlayback();
      this.updateState({
        playbackStatus: "paused",
        playbackError: "无法播放当前句音频，请重试。",
      });
    };

    try {
      this.prepareNextBrowserAudio(sentenceId, generation);
      await audio.play();
      if (this.activeAudio === audio) {
        this.updateState({ playbackStatus: "playing" });
      }
    } catch {
      if (this.generation !== generation) {
        return;
      }
      this.discardPlayback();
      this.updateState({
        playbackStatus: "paused",
        playbackError: "无法播放当前句音频，请重试。",
      });
    }
  }

  private updateCurrentPosition(
    sentenceId: string,
    offsetSeconds: number,
    completed: boolean,
    throttled = false,
  ) {
    const sentenceChanged = this.state.currentSentenceId !== sentenceId;
    const progress = {
      sentence_id: sentenceId,
      sentence_offset_seconds: offsetSeconds,
      playback_rate: this.state.playbackRate,
      playback_completed: completed,
    };
    this.state = {
      ...this.state,
      currentSentenceId: sentenceId,
      currentSentenceOffsetSeconds: offsetSeconds,
      playbackCompleted: completed,
      timeline: buildPlaybackTimeline(this.sentences, progress),
    };
    this.emit();
    if (throttled) {
      this.queueProgressThrottled(progress);
    } else {
      this.queueProgress(progress);
    }
    if (sentenceChanged) {
      void this.audioPreparation.preloadWindow(
        audioPreloadWindow(
          this.sentences.map((sentence) => sentence.id),
          sentenceId,
        ),
      );
    }
  }

  private queueCurrentProgress() {
    const progress = progressInputForTimeline(
      this.state.timeline,
      this.state.currentSentenceId,
      this.state.currentSentenceOffsetSeconds,
      this.state.playbackRate,
      this.state.playbackCompleted,
    );
    if (progress) {
      this.queueProgress(progress);
    }
  }

  private queueProgress(progress: ProgressInput) {
    if (this.disposed) {
      return;
    }
    this.pendingProgress = progress;
    this.progressBlocked = false;
    this.lastProgressSaveAt = this.adapters.now();
    void this.flushProgress();
  }

  private queueProgressThrottled(progress: ProgressInput) {
    if (this.adapters.now() - this.lastProgressSaveAt < PROGRESS_SAVE_INTERVAL_MS) {
      this.pendingProgress = progress;
      return;
    }
    this.queueProgress(progress);
  }

  private async flushProgress() {
    if (this.savingProgress || this.progressBlocked || this.disposed) {
      return;
    }
    const progress = this.pendingProgress;
    if (!progress) {
      return;
    }

    this.pendingProgress = null;
    this.savingProgress = true;
    const generation = this.progressGeneration;
    try {
      await this.adapters.saveProgress(progress);
      if (this.progressGeneration === generation && !this.disposed) {
        this.updateState({ progressError: null });
      }
    } catch {
      if (this.progressGeneration === generation && !this.disposed) {
        this.pendingProgress ??= progress;
        this.progressBlocked = true;
        this.updateState({ progressError: "阅读进度保存失败，请重试。" });
      }
    } finally {
      if (this.progressGeneration === generation && !this.disposed) {
        this.savingProgress = false;
        if (this.pendingProgress && !this.progressBlocked) {
          void this.flushProgress();
        }
      }
    }
  }

  private discardPlayback() {
    this.generation += 1;
    const audio = this.activeAudio;
    this.activeAudio = null;
    if (!audio) {
      return;
    }
    audio.pause();
    audio.ontimeupdate = null;
    audio.onended = null;
    audio.onerror = null;
    audio.removeAttribute("src");
    audio.load();
  }

  private prepareNextBrowserAudio(sentenceId: string, generation: number) {
    const currentIndex = this.sentences.findIndex((sentence) => sentence.id === sentenceId);
    const nextSentence = this.sentences[currentIndex + 1];
    if (!nextSentence || this.audioElements.has(nextSentence.id)) {
      return;
    }
    void this.audioPreparation
      .prepareForPlayback(nextSentence.id)
      .then(() => {
        if (this.generation === generation && !this.disposed) {
          this.audioElements.prepare(nextSentence.id, this.state.playbackRate);
        }
      })
      .catch(() => {
        // 后台浏览器预载失败不打断当前朗读；真正播放该句时会重试。
      });
  }

  private handleSentenceEnded(sentenceId: string) {
    const finishedIndex = this.sentences.findIndex(
      (sentence) => sentence.id === sentenceId,
    );
    const nextSentence = this.sentences[finishedIndex + 1];
    if (nextSentence) {
      void this.playSentence(nextSentence.id);
      return;
    }

    const currentItem = this.state.timeline.items.find(
      (item) => item.sentenceId === sentenceId,
    );
    this.updateCurrentPosition(
      sentenceId,
      currentItem?.durationSeconds ?? 0,
      true,
    );
    this.updateState({ playbackStatus: "paused" });
    const target = playbackModeTargetForNaturalEnd(
      this.state.playbackMode,
      this.navigation,
    );
    if (!target) {
      return;
    }
    if (target.materialId === this.materialId) {
      const firstSentenceId = this.sentences[0]?.id;
      if (firstSentenceId) {
        void this.playSentence(firstSentenceId);
      }
      return;
    }
    this.navigateToTarget(target);
  }

  private updateSentenceDuration(sentenceId: string, durationSeconds: number) {
    this.sentences = this.sentences.map((sentence) =>
      sentence.id === sentenceId
        ? { ...sentence, audio_duration_seconds: durationSeconds }
        : sentence,
    );
    this.state = {
      ...this.state,
      timeline: buildPlaybackTimeline(this.sentences, {
        sentence_id: this.state.currentSentenceId ?? this.sentences[0]?.id ?? "",
        sentence_offset_seconds: this.state.currentSentenceOffsetSeconds,
        playback_completed: this.state.playbackCompleted,
      }),
    };
    this.emit();
    if (
      this.state.currentSentenceId === sentenceId &&
      this.state.currentSentenceOffsetSeconds > durationSeconds
    ) {
      this.updateCurrentPosition(
        sentenceId,
        durationSeconds,
        this.state.playbackCompleted,
      );
      if (this.state.playbackStatus === "playing") {
        this.handleSentenceEnded(sentenceId);
      }
    }
  }

  private navigateToTarget(target: PlaybackModeTarget) {
    this.queueCurrentProgress();
    this.adapters.navigate(target.materialId, target.autoplay);
  }

  private rebuildTimeline() {
    this.state = {
      ...this.state,
      timeline: buildPlaybackTimeline(this.sentences, {
        sentence_id: this.state.currentSentenceId ?? this.sentences[0]?.id ?? "",
        sentence_offset_seconds: this.state.currentSentenceOffsetSeconds,
        playback_completed: this.state.playbackCompleted,
      }),
    };
    this.emit();
  }

  private updateState(changes: Partial<ReaderPlaybackSessionSnapshot>) {
    this.state = { ...this.state, ...changes };
    this.emit();
  }

  private emit() {
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }
}

function navigableTarget(
  target: PlaybackModeTarget | null,
  currentMaterialId: string,
): PlaybackModeTarget | null {
  if (!target || target.materialId === currentMaterialId) {
    return null;
  }
  return target;
}

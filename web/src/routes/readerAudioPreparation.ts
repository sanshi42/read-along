import type { ReadingProgress } from "../api";

export type AudioPreparationStatus = "idle" | "loading" | "ready" | "failed";

export interface AudioPreparationSnapshot {
  status: AudioPreparationStatus;
  errorMessage: string | null;
}

interface CacheableAudioElement {
  playbackRate: number;
  preload: string;
  load: () => void;
  pause: () => void;
  removeAttribute: (qualifiedName: string) => void;
}

interface AudioPreparationRecord extends AudioPreparationSnapshot {
  promise: Promise<void> | null;
  backgroundRequests: number;
}

const AUDIO_PRELOAD_WINDOW_SIZE = 5;
const AUDIO_REPAIR_CONTEXT_BEFORE = 3;
const AUDIO_REPAIR_CONTEXT_AFTER = 4;
const BACKGROUND_RETRY_COUNT = 1;
const GENERIC_AUDIO_PREPARATION_ERROR = "无法准备当前句音频，请重试。";

interface AudioRepairPreloadWindowOptions {
  contextBefore?: number;
  contextAfter?: number;
}

export function initialAudioPreloadAnchor(
  sentenceIds: string[],
  progress: Pick<ReadingProgress, "sentence_id" | "playback_completed"> | null,
): string | null {
  if (sentenceIds.length === 0) {
    return null;
  }
  if (!progress || progress.playback_completed) {
    return sentenceIds[0];
  }
  return sentenceIds.includes(progress.sentence_id) ? progress.sentence_id : sentenceIds[0];
}

export function audioPreloadWindow(
  sentenceIds: string[],
  anchorSentenceId: string | null,
  windowSize = AUDIO_PRELOAD_WINDOW_SIZE,
): string[] {
  if (!anchorSentenceId || windowSize <= 0) {
    return [];
  }
  const startIndex = sentenceIds.indexOf(anchorSentenceId);
  if (startIndex < 0) {
    return [];
  }
  return sentenceIds.slice(startIndex, startIndex + windowSize);
}

export function audioRepairPreloadWindow(
  sentenceIds: string[],
  anchorSentenceId: string | null,
  visibleSentenceIds: string[] = [],
  {
    contextBefore = AUDIO_REPAIR_CONTEXT_BEFORE,
    contextAfter = AUDIO_REPAIR_CONTEXT_AFTER,
  }: AudioRepairPreloadWindowOptions = {},
): string[] {
  if (sentenceIds.length === 0) {
    return [];
  }

  const repairAnchorSentenceId =
    anchorSentenceId && visibleSentenceIds.includes(anchorSentenceId)
      ? anchorSentenceId
      : visibleSentenceIds.find((sentenceId) => sentenceIds.includes(sentenceId)) ??
        anchorSentenceId;
  if (!repairAnchorSentenceId) {
    return [];
  }

  const anchorIndex = sentenceIds.indexOf(repairAnchorSentenceId);
  if (anchorIndex < 0) {
    return [];
  }
  const startIndex = Math.max(0, anchorIndex - Math.max(0, contextBefore));
  const endIndex = Math.min(
    sentenceIds.length,
    anchorIndex + Math.max(0, contextAfter) + 1,
  );

  return sentenceIds.slice(startIndex, endIndex);
}

export class SentenceAudioElementCache<AudioElement extends CacheableAudioElement> {
  private readonly elements = new Map<string, AudioElement>();
  private readonly createAudio: (sentenceId: string) => AudioElement;

  constructor(createAudio: (sentenceId: string) => AudioElement) {
    this.createAudio = createAudio;
  }

  has(sentenceId: string): boolean {
    return this.elements.has(sentenceId);
  }

  prepare(sentenceId: string, playbackRate: number): AudioElement {
    const audio = this.elementFor(sentenceId);
    audio.preload = "auto";
    audio.playbackRate = playbackRate;
    audio.load();
    return audio;
  }

  take(sentenceId: string, playbackRate: number): AudioElement {
    const audio = this.elementFor(sentenceId);
    this.elements.delete(sentenceId);
    audio.preload = "auto";
    audio.playbackRate = playbackRate;
    return audio;
  }

  syncPlaybackRate(playbackRate: number) {
    for (const audio of this.elements.values()) {
      audio.playbackRate = playbackRate;
    }
  }

  clear() {
    for (const audio of this.elements.values()) {
      this.release(audio);
    }
    this.elements.clear();
  }

  private elementFor(sentenceId: string): AudioElement {
    const existing = this.elements.get(sentenceId);
    if (existing) {
      return existing;
    }
    const audio = this.createAudio(sentenceId);
    this.elements.set(sentenceId, audio);
    return audio;
  }

  private release(audio: AudioElement) {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
  }
}

export class SentenceAudioPreparationQueue {
  private records = new Map<string, AudioPreparationRecord>();
  private preloadGeneration = 0;
  private readonly prepareAudio: (sentenceId: string) => Promise<void>;
  private readonly backgroundRetryCount: number;

  constructor(
    prepareAudio: (sentenceId: string) => Promise<void>,
    backgroundRetryCount = BACKGROUND_RETRY_COUNT,
  ) {
    this.prepareAudio = prepareAudio;
    this.backgroundRetryCount = backgroundRetryCount;
  }

  snapshot(sentenceId: string): AudioPreparationSnapshot {
    const record = this.records.get(sentenceId);
    return {
      status: record?.status ?? "idle",
      errorMessage: record?.errorMessage ?? null,
    };
  }

  clear() {
    this.preloadGeneration += 1;
    this.records.clear();
  }

  async preloadWindow(sentenceIds: string[]): Promise<void> {
    const generation = ++this.preloadGeneration;
    for (const sentenceId of sentenceIds) {
      if (generation !== this.preloadGeneration) {
        return;
      }
      await this.prepareInBackground(sentenceId);
    }
  }

  async prepareForPlayback(sentenceId: string): Promise<void> {
    await this.startRequest(sentenceId);
  }

  private recordFor(sentenceId: string): AudioPreparationRecord {
    const existing = this.records.get(sentenceId);
    if (existing) {
      return existing;
    }
    const record: AudioPreparationRecord = {
      status: "idle",
      errorMessage: null,
      promise: null,
      backgroundRequests: 0,
    };
    this.records.set(sentenceId, record);
    return record;
  }

  private async prepareInBackground(sentenceId: string): Promise<void> {
    const record = this.recordFor(sentenceId);
    if (record.status === "ready") {
      return;
    }
    if (record.status === "loading" && record.promise) {
      try {
        await record.promise;
      } catch {
        // 后台预取失败不打扰当前阅读流程。
      }
      return;
    }

    const request = this.runBackgroundRequests(sentenceId, record).finally(() => {
      if (record.promise === request) {
        record.promise = null;
      }
    });
    record.promise = request;
    try {
      await request;
    } catch {
      // 后台预取失败不打扰当前阅读流程。
    }
  }

  private startRequest(sentenceId: string): Promise<void> {
    const record = this.recordFor(sentenceId);
    if (record.status === "ready") {
      return Promise.resolve();
    }
    if (record.status === "loading" && record.promise) {
      return record.promise;
    }

    const request = this.runSingleRequest(sentenceId, record).finally(() => {
      if (record.promise === request) {
        record.promise = null;
      }
    });

    record.promise = request;
    return request;
  }

  private async runBackgroundRequests(
    sentenceId: string,
    record: AudioPreparationRecord,
  ): Promise<void> {
    const maxRequests = this.backgroundRetryCount + 1;
    while (record.backgroundRequests < maxRequests) {
      record.backgroundRequests += 1;
      try {
        await this.runSingleRequest(sentenceId, record);
        return;
      } catch {
        // 继续消耗本轮后台重试次数；最终失败保留在 snapshot 中。
      }
    }
    throw new Error(record.errorMessage ?? GENERIC_AUDIO_PREPARATION_ERROR);
  }

  private async runSingleRequest(
    sentenceId: string,
    record: AudioPreparationRecord,
  ): Promise<void> {
    record.status = "loading";
    record.errorMessage = null;
    try {
      await this.prepareAudio(sentenceId);
      record.status = "ready";
      record.errorMessage = null;
    } catch (reason: unknown) {
      record.status = "failed";
      record.errorMessage = preparationErrorMessage(reason);
      throw new Error(record.errorMessage);
    }
  }
}

export function preparationErrorMessage(reason: unknown): string {
  if (reason instanceof Error && reason.message.trim()) {
    return reason.message;
  }
  return GENERIC_AUDIO_PREPARATION_ERROR;
}

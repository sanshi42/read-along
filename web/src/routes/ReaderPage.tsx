import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FastForward,
  Gauge,
  LocateFixed,
  LoaderCircle,
  Pause,
  Play,
  Rewind,
  RotateCcw,
  Settings2,
  X,
} from "lucide-react";
import { type SyntheticEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  clearMaterialAudioCache,
  getMaterial,
  prepareSentenceAudio,
  saveProgress,
  sentenceAudioUrl,
  type MaterialDetail,
  type ReadingProgress,
} from "../api";
import {
  type FontSizePreference,
  type LineHeightPreference,
  type ReadingPreferences,
  type ThemePreference,
} from "../readingPreferences";
import {
  SentenceAudioElementCache,
  SentenceAudioPreparationQueue,
  audioRepairPreloadWindow,
  audioPreloadWindow,
  initialAudioPreloadAnchor,
  preparationErrorMessage,
} from "./readerAudioPreparation";
import {
  buildPlaybackTimeline,
  formatTimelineTime,
  isInteractiveShortcutTarget,
  progressInputForTimeline,
  seekTimeline,
} from "./readerPlaybackTimeline";
import {
  isRectFullyVisibleWithinReaderChrome,
  normalizeReadingTitle,
  sentencePointerAction,
  scrollTargetForRectWithinReaderChrome,
  shouldShowReaderNavContext,
} from "./readerPageViewModel";

type PlaybackStatus = "idle" | "loading" | "playing" | "paused";
type AudioRepairStatus = "idle" | "repairing" | "success" | "failed";
type ProgressInput = Pick<
  ReadingProgress,
  "sentence_id" | "sentence_offset_seconds" | "playback_rate" | "playback_completed"
>;

const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 2] as const;
const SCROLL_KEYS = new Set(["ArrowDown", "ArrowUp", "End", "Home", "PageDown", "PageUp"]);
const READER_CHROME_MARGIN = 18;
const SKIP_BACK_SECONDS = 15;
const SKIP_FORWARD_SECONDS = 30;
const PROGRESS_SAVE_INTERVAL_MS = 5000;

interface ReaderPageProps {
  readingPreferences: ReadingPreferences;
  readingPreferencesError: boolean;
  onReadingPreferencesChange: (preferences: ReadingPreferences) => void;
}

function sourceLabel(material: MaterialDetail) {
  return material.primary_source.source_type === "pdf" ? "文本型 PDF" : "网页";
}

function sourceDetailLabel(material: MaterialDetail, readingTitle: string) {
  const sourceUri = material.primary_source.source_uri.trim();
  if (!sourceUri) {
    return null;
  }
  if (
    material.primary_source.source_type === "pdf" &&
    normalizeReadingTitle(sourceUri) === readingTitle
  ) {
    return null;
  }
  return sourceUri;
}

export function ReaderPage({
  readingPreferences,
  readingPreferencesError,
  onReadingPreferencesChange,
}: ReaderPageProps) {
  const { materialId } = useParams();
  const navigate = useNavigate();
  const [material, setMaterial] = useState<MaterialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSentenceId, setCurrentSentenceId] = useState<string | null>(null);
  const [currentSentenceOffsetSeconds, setCurrentSentenceOffsetSeconds] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [playbackCompleted, setPlaybackCompleted] = useState(false);
  const [playbackStatus, setPlaybackStatus] = useState<PlaybackStatus>("idle");
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [progressError, setProgressError] = useState<string | null>(null);
  const [showReturnToCurrent, setShowReturnToCurrent] = useState(false);
  const [showReadingPreferences, setShowReadingPreferences] = useState(false);
  const [showPlaybackRateMenu, setShowPlaybackRateMenu] = useState(false);
  const [showReaderContext, setShowReaderContext] = useState(false);
  const [pendingSeekSeconds, setPendingSeekSeconds] = useState<number | null>(null);
  const [audioRepairStatus, setAudioRepairStatus] = useState<AudioRepairStatus>("idle");
  const [materialReloadKey, setMaterialReloadKey] = useState(0);
  const currentSentenceIdRef = useRef<string | null>(null);
  const currentSentenceOffsetSecondsRef = useRef(0);
  const playbackRateRef = useRef(1);
  const playbackCompletedRef = useRef(false);
  const playbackStatusRef = useRef<PlaybackStatus>("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioPreparationRef = useRef<SentenceAudioPreparationQueue | null>(null);
  const audioElementCacheRef = useRef<SentenceAudioElementCache<HTMLAudioElement> | null>(null);
  const audioReloadTokenRef = useRef<string | null>(null);
  const playbackGenerationRef = useRef(0);
  const activeMaterialIdRef = useRef<string | null>(null);
  const pendingProgressRef = useRef<ProgressInput | null>(null);
  const savingProgressRef = useRef(false);
  const progressBlockedRef = useRef(false);
  const progressGenerationRef = useRef(0);
  const lastProgressSaveAtRef = useRef(0);
  const autoplayOnMaterialLoadRef = useRef(false);
  const followCurrentRef = useRef(true);
  const userScrollIntentUntilRef = useRef(0);
  const readerNavRef = useRef<HTMLElement | null>(null);
  const readerHeaderRef = useRef<HTMLElement | null>(null);
  const playerBarRef = useRef<HTMLElement | null>(null);
  const readingPreferencesRef = useRef<HTMLDivElement | null>(null);
  const readingPreferencesTriggerRef = useRef<HTMLButtonElement | null>(null);
  const playbackRateMenuRef = useRef<HTMLDivElement | null>(null);
  const playbackRateTriggerRef = useRef<HTMLButtonElement | null>(null);

  const sentences = useMemo(
    () => material?.paragraphs.flatMap((paragraph) => paragraph.sentences) ?? [],
    [material],
  );
  const playbackTimeline = useMemo(
    () =>
      buildPlaybackTimeline(
        sentences.map((sentence) => ({
          id: sentence.id,
          text: sentence.text,
          audio_duration_seconds: sentence.audio_duration_seconds,
        })),
        currentSentenceId
          ? {
              sentence_id: currentSentenceId,
              sentence_offset_seconds: currentSentenceOffsetSeconds,
              playback_completed: playbackCompleted,
            }
          : null,
      ),
    [sentences, currentSentenceId, currentSentenceOffsetSeconds, playbackCompleted],
  );
  const currentSentenceIndex = sentences.findIndex(
    (sentence) => sentence.id === currentSentenceId,
  );
  const displayedElapsedSeconds =
    pendingSeekSeconds ?? (playbackCompleted ? playbackTimeline.totalSeconds : playbackTimeline.elapsedSeconds);
  const timelineTotalLabel = `${playbackTimeline.estimated ? "约 " : ""}${formatTimelineTime(
    playbackTimeline.totalSeconds,
  )}`;
  const timelinePositionLabel =
    playbackTimeline.totalSeconds > 0
      ? `${formatTimelineTime(displayedElapsedSeconds)} / ${timelineTotalLabel}`
      : "";
  const previewSeekResult =
    pendingSeekSeconds !== null ? seekTimeline(playbackTimeline, pendingSeekSeconds) : null;
  const highlightedSentenceId = previewSeekResult?.sentenceId ?? currentSentenceId;
  const readingTitle = material ? normalizeReadingTitle(material.title) : "";
  const sourceDetail = material ? sourceDetailLabel(material, readingTitle) : null;
  const readerContextProgress =
    timelinePositionLabel ||
    (playbackTimeline.totalSeconds > 0 ? timelineTotalLabel : sentences.length > 0 ? `共 ${sentences.length} 句` : "");

  useEffect(() => {
    discardPlayback();
    audioElementCacheRef.current?.clear();
    resetProgressSaving();
    currentSentenceIdRef.current = null;
    currentSentenceOffsetSecondsRef.current = 0;
    playbackRateRef.current = 1;
    playbackCompletedRef.current = false;
    followCurrentRef.current = true;
    activeMaterialIdRef.current = materialId ?? null;
    audioReloadTokenRef.current = null;
    audioPreparationRef.current = materialId
      ? new SentenceAudioPreparationQueue(async (sentenceId) => {
          const duration = await prepareSentenceAudio(
            materialId,
            sentenceId,
            audioReloadTokenRef.current,
          );
          if (duration !== null) {
            updateSentenceAudioDuration(sentenceId, duration);
          }
        })
      : null;
    audioElementCacheRef.current = materialId
      ? new SentenceAudioElementCache(
          (sentenceId) =>
            new Audio(sentenceAudioUrl(materialId, sentenceId, audioReloadTokenRef.current)),
        )
      : null;
    setCurrentSentenceId(null);
    setCurrentSentenceOffsetSeconds(0);
    setPlaybackRate(1);
    setPlaybackCompleted(false);
    setPlaybackError(null);
    setProgressError(null);
    setAudioRepairStatus("idle");
    setShowReturnToCurrent(false);
    setShowReaderContext(false);
    updatePlaybackStatus("idle");
    setMaterial(null);
    setError(null);

    if (!materialId) {
      setError("阅读材料地址不完整");
      return;
    }

    let active = true;
    getMaterial(materialId)
      .then((item) => {
        if (!active) {
          return;
        }
        setMaterial(item);
        const progress = item.progress;
        const loadedSentences = item.paragraphs.flatMap((paragraph) => paragraph.sentences);
        const loadedSentenceIds = loadedSentences.map((sentence) => sentence.id);
        const sentenceExists =
          progress !== null &&
          loadedSentences.some((sentence) => sentence.id === progress.sentence_id);
        if (progress && sentenceExists) {
          const initialSentenceId = progress.playback_completed
            ? (loadedSentences[0]?.id ?? progress.sentence_id)
            : progress.sentence_id;
          const initialOffset = progress.playback_completed ? 0 : progress.sentence_offset_seconds;
          currentSentenceIdRef.current = initialSentenceId;
          currentSentenceOffsetSecondsRef.current = initialOffset;
          playbackRateRef.current = progress.playback_rate;
          playbackCompletedRef.current = progress.playback_completed;
          setCurrentSentenceId(initialSentenceId);
          setCurrentSentenceOffsetSeconds(initialOffset);
          setPlaybackRate(progress.playback_rate);
          setPlaybackCompleted(progress.playback_completed);
          updatePlaybackStatus("paused");
          scheduleScrollToCurrent("auto");
        }
        scheduleAudioPreload(
          initialAudioPreloadAnchor(loadedSentenceIds, sentenceExists ? progress : null),
          loadedSentenceIds,
        );
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "读取材料失败");
        }
      });
    return () => {
      active = false;
    };
  }, [materialId, materialReloadKey]);

  useEffect(() => {
    function recordUserScrollIntent() {
      userScrollIntentUntilRef.current = performance.now() + 600;
    }

    function recordKeyboardScrollIntent(event: KeyboardEvent) {
      if (!SCROLL_KEYS.has(event.key)) {
        return;
      }
      recordUserScrollIntent();
    }

    function handleScroll() {
      if (
        performance.now() <= userScrollIntentUntilRef.current &&
        !isCurrentSentenceFullyVisible()
      ) {
        followCurrentRef.current = false;
      }
      updateReturnToCurrent();
      updateReaderNavContext();
    }

    window.addEventListener("wheel", recordUserScrollIntent, { passive: true });
    window.addEventListener("touchmove", recordUserScrollIntent, { passive: true });
    window.addEventListener("keydown", recordKeyboardScrollIntent);
    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", updateReturnToCurrent);
    window.addEventListener("resize", updateReaderNavContext);
    return () => {
      window.removeEventListener("wheel", recordUserScrollIntent);
      window.removeEventListener("touchmove", recordUserScrollIntent);
      window.removeEventListener("keydown", recordKeyboardScrollIntent);
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", updateReturnToCurrent);
      window.removeEventListener("resize", updateReaderNavContext);
    };
  }, []);

  useEffect(() => {
    updateReaderNavContext();
  }, [material, currentSentenceIndex]);

  useEffect(() => {
    if (!material || !autoplayOnMaterialLoadRef.current) {
      return;
    }
    const sentenceId = currentSentenceIdRef.current ?? sentences[0]?.id;
    if (!sentenceId) {
      return;
    }
    autoplayOnMaterialLoadRef.current = false;
    followCurrentRef.current = true;
    void playSentence(sentenceId, false, currentSentenceOffsetSecondsRef.current);
  }, [material, currentSentenceId, sentences]);

  useEffect(() => {
    if (!showReadingPreferences) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (
        readingPreferencesRef.current &&
        !readingPreferencesRef.current.contains(event.target as Node)
      ) {
        setShowReadingPreferences(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeReadingPreferences(true);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [showReadingPreferences]);

  useEffect(() => {
    if (!showPlaybackRateMenu) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (playbackRateMenuRef.current && !playbackRateMenuRef.current.contains(event.target as Node)) {
        setShowPlaybackRateMenu(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setShowPlaybackRateMenu(false);
        playbackRateTriggerRef.current?.focus();
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [showPlaybackRateMenu]);

  useEffect(() => {
    function handleGlobalShortcut(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (isInteractiveShortcutTarget(target.tagName, {
          role: target.getAttribute("role"),
          contentEditable: target.getAttribute("contenteditable"),
        }) ||
          readingPreferencesRef.current?.contains(target))
      ) {
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        handleTimelineSkip(-SKIP_BACK_SECONDS);
        return;
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        handleTimelineSkip(SKIP_FORWARD_SECONDS);
        return;
      }
      if (event.key === " ") {
        event.preventDefault();
        handlePlayPause();
      }
    }

    window.addEventListener("keydown", handleGlobalShortcut);
    return () => {
      window.removeEventListener("keydown", handleGlobalShortcut);
    };
  });

  useEffect(() => {
    function saveCurrentProgress() {
      queueCurrentProgress();
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "hidden") {
        saveCurrentProgress();
      }
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("pagehide", saveCurrentProgress);
    window.addEventListener("beforeunload", saveCurrentProgress);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("pagehide", saveCurrentProgress);
      window.removeEventListener("beforeunload", saveCurrentProgress);
    };
  });

  useEffect(() => {
    return () => {
      playbackGenerationRef.current += 1;
      progressGenerationRef.current += 1;
      const audio = audioRef.current;
      if (audio) {
        audio.pause();
        audio.ontimeupdate = null;
        audio.onended = null;
        audio.onerror = null;
        audio.removeAttribute("src");
        audio.load();
      }
      audioPreparationRef.current = null;
      audioElementCacheRef.current?.clear();
      audioElementCacheRef.current = null;
    };
  }, []);

  function updatePlaybackStatus(status: PlaybackStatus) {
    playbackStatusRef.current = status;
    setPlaybackStatus(status);
  }

  function updateCurrentPosition(
    sentenceId: string,
    offsetSeconds: number,
    completed: boolean,
    options: {
      persist?: boolean | "throttled";
      resumeFollowing?: boolean;
      scrollBehavior?: ScrollBehavior;
    } = {},
  ) {
    const sentenceChanged = currentSentenceIdRef.current !== sentenceId;
    currentSentenceIdRef.current = sentenceId;
    currentSentenceOffsetSecondsRef.current = offsetSeconds;
    playbackCompletedRef.current = completed;
    setCurrentSentenceId(sentenceId);
    setCurrentSentenceOffsetSeconds(offsetSeconds);
    setPlaybackCompleted(completed);
    if (options.resumeFollowing) {
      followCurrentRef.current = true;
      setShowReturnToCurrent(false);
    }
    if (options.persist === "throttled") {
      queueProgressThrottled({
        sentence_id: sentenceId,
        sentence_offset_seconds: offsetSeconds,
        playback_rate: playbackRateRef.current,
        playback_completed: completed,
      });
    } else if (options.persist !== false) {
      queueProgress({
        sentence_id: sentenceId,
        sentence_offset_seconds: offsetSeconds,
        playback_rate: playbackRateRef.current,
        playback_completed: completed,
      });
    }
    if (followCurrentRef.current && (sentenceChanged || options.resumeFollowing)) {
      scheduleScrollToCurrent(options.scrollBehavior ?? "smooth");
    }
    if (sentenceChanged) {
      scheduleAudioPreload(sentenceId);
    }
  }

  function currentProgressInput() {
    return progressInputForTimeline(
      playbackTimeline,
      currentSentenceIdRef.current,
      currentSentenceOffsetSecondsRef.current,
      playbackRateRef.current,
      playbackCompletedRef.current,
    );
  }

  function queueCurrentProgress() {
    const progress = currentProgressInput();
    if (!progress) {
      return;
    }
    queueProgress(progress);
  }

  function scheduleAudioPreload(
    anchorSentenceId: string | null,
    sentenceIds = sentences.map((sentence) => sentence.id),
  ) {
    const queue = audioPreparationRef.current;
    if (!queue) {
      return;
    }
    void queue.preloadWindow(audioPreloadWindow(sentenceIds, anchorSentenceId));
  }

  function discardPlayback() {
    playbackGenerationRef.current += 1;

    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      audio.pause();
      audio.ontimeupdate = null;
      audio.onended = null;
      audio.onerror = null;
      audio.removeAttribute("src");
      audio.load();
    }
  }

  function prepareNextBrowserAudio(sentenceId: string, generation: number) {
    const queue = audioPreparationRef.current;
    const cache = audioElementCacheRef.current;
    if (!queue || !cache) {
      return;
    }
    const currentIndex = sentences.findIndex((sentence) => sentence.id === sentenceId);
    const nextSentence = sentences[currentIndex + 1];
    if (!nextSentence || cache.has(nextSentence.id)) {
      return;
    }

    void queue
      .prepareForPlayback(nextSentence.id)
      .then(() => {
        if (
          playbackGenerationRef.current !== generation ||
          audioElementCacheRef.current !== cache
        ) {
          return;
        }
        cache.prepare(nextSentence.id, playbackRateRef.current);
      })
      .catch(() => {
        // 后台浏览器预载失败时不打断当前朗读；真正播放该句时会重试。
      });
  }

  function resetProgressSaving() {
    progressGenerationRef.current += 1;
    pendingProgressRef.current = null;
    savingProgressRef.current = false;
    progressBlockedRef.current = false;
  }

  function queueProgress(progress: ProgressInput) {
    pendingProgressRef.current = progress;
    progressBlockedRef.current = false;
    lastProgressSaveAtRef.current = performance.now();
    void flushProgress();
  }

  function queueProgressThrottled(progress: ProgressInput) {
    const now = performance.now();
    if (now - lastProgressSaveAtRef.current < PROGRESS_SAVE_INTERVAL_MS) {
      pendingProgressRef.current = progress;
      return;
    }
    queueProgress(progress);
  }

  async function flushProgress() {
    if (savingProgressRef.current || progressBlockedRef.current) {
      return;
    }
    const progress = pendingProgressRef.current;
    const activeMaterialId = activeMaterialIdRef.current;
    if (!progress || !activeMaterialId) {
      return;
    }

    pendingProgressRef.current = null;
    savingProgressRef.current = true;
    const generation = progressGenerationRef.current;
    try {
      await saveProgress(activeMaterialId, progress);
      if (progressGenerationRef.current === generation) {
        setProgressError(null);
      }
    } catch {
      if (progressGenerationRef.current === generation) {
        pendingProgressRef.current ??= progress;
        progressBlockedRef.current = true;
        setProgressError("阅读进度保存失败，请重试。");
      }
    } finally {
      if (progressGenerationRef.current === generation) {
        savingProgressRef.current = false;
        if (pendingProgressRef.current && !progressBlockedRef.current) {
          void flushProgress();
        }
      }
    }
  }

  function retryProgressSave() {
    progressBlockedRef.current = false;
    void flushProgress();
  }

  function updateSentenceAudioDuration(sentenceId: string, durationSeconds: number) {
    setMaterial((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        paragraphs: current.paragraphs.map((paragraph) => ({
          ...paragraph,
          sentences: paragraph.sentences.map((sentence) =>
            sentence.id === sentenceId
              ? { ...sentence, audio_duration_seconds: durationSeconds }
              : sentence,
          ),
        })),
      };
    });
    if (
      currentSentenceIdRef.current === sentenceId &&
      currentSentenceOffsetSecondsRef.current > durationSeconds
    ) {
      updateCurrentPosition(sentenceId, durationSeconds, playbackCompletedRef.current);
      if (playbackStatusRef.current === "playing") {
        handleSentenceEnded(sentenceId);
      }
    }
  }

  function resetMaterialAudioState() {
    setMaterial((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        paragraphs: current.paragraphs.map((paragraph) => ({
          ...paragraph,
          sentences: paragraph.sentences.map((sentence) => ({
            ...sentence,
            audio_status: "pending",
            audio_duration_seconds: null,
            error_message: null,
          })),
        })),
      };
    });
  }

  function visibleSentenceIdsWithinReaderChrome() {
    const bounds = readerChromeBounds();
    return sentences
      .filter((sentence) => {
        const element = document.getElementById(sentence.id);
        if (!element) {
          return false;
        }
        const rect = element.getBoundingClientRect();
        return rect.bottom >= bounds.top && rect.top <= bounds.bottom;
      })
      .map((sentence) => sentence.id);
  }

  async function handleRepairAudio() {
    if (!materialId || audioRepairStatus === "repairing") {
      return;
    }
    const repairMaterialId = materialId;
    const shouldResume = playbackStatusRef.current === "playing";
    const sentenceId = currentSentenceIdRef.current ?? sentences[0]?.id ?? null;
    const offsetSeconds = currentSentenceOffsetSecondsRef.current;
    const sentenceIds = sentences.map((sentence) => sentence.id);
    const repairPreloadSentenceIds = audioRepairPreloadWindow(
      sentenceIds,
      sentenceId,
      visibleSentenceIdsWithinReaderChrome(),
    );

    setAudioRepairStatus("repairing");
    setPlaybackError(null);
    discardPlayback();
    audioPreparationRef.current?.clear();
    audioElementCacheRef.current?.clear();
    updatePlaybackStatus("paused");

    try {
      await clearMaterialAudioCache(repairMaterialId);
      if (activeMaterialIdRef.current !== repairMaterialId) {
        return;
      }
      audioReloadTokenRef.current = String(Date.now());
      resetMaterialAudioState();
      for (const preloadSentenceId of repairPreloadSentenceIds) {
        if (activeMaterialIdRef.current !== repairMaterialId) {
          return;
        }
        await audioPreparationRef.current?.prepareForPlayback(preloadSentenceId);
      }
      setAudioRepairStatus("success");
      if (shouldResume && sentenceId) {
        void playSentence(sentenceId, false, offsetSeconds);
      } else {
        scheduleAudioPreload(sentenceId);
      }
    } catch {
      if (activeMaterialIdRef.current === repairMaterialId) {
        setAudioRepairStatus("failed");
      }
    }
  }

  function selectSentence(sentenceId: string) {
    discardPlayback();
    setPlaybackError(null);
    updatePlaybackStatus("paused");
    updateCurrentPosition(sentenceId, 0, false, { resumeFollowing: true });
  }

  async function playSentence(sentenceId: string, restart = false, offsetSeconds = 0) {
    if (!materialId) {
      return;
    }

    setPlaybackError(null);
    const activeAudio = audioRef.current;
    if (activeAudio && currentSentenceIdRef.current === sentenceId) {
      if (restart || activeAudio.ended) {
        activeAudio.currentTime = 0;
      } else if (offsetSeconds > 0) {
        activeAudio.currentTime = offsetSeconds;
      }
      updateCurrentPosition(sentenceId, activeAudio.currentTime, false);
      activeAudio.playbackRate = playbackRateRef.current;
      try {
        await activeAudio.play();
        if (audioRef.current === activeAudio) {
          updatePlaybackStatus("playing");
        }
      } catch {
        if (audioRef.current === activeAudio) {
          updatePlaybackStatus("paused");
          setPlaybackError("无法播放当前句音频，请重试。");
        }
      }
      return;
    }

    discardPlayback();
    updateCurrentPosition(sentenceId, offsetSeconds, false);
    updatePlaybackStatus("loading");
    const generation = playbackGenerationRef.current;
    try {
      await audioPreparationRef.current?.prepareForPlayback(sentenceId);
    } catch (reason: unknown) {
      if (playbackGenerationRef.current !== generation) {
        return;
      }
      updatePlaybackStatus("paused");
      setPlaybackError(preparationErrorMessage(reason));
      return;
    }
    if (playbackGenerationRef.current !== generation) {
      return;
    }
    const audio =
      audioElementCacheRef.current?.take(sentenceId, playbackRateRef.current) ??
      new Audio(sentenceAudioUrl(materialId, sentenceId, audioReloadTokenRef.current));
    audio.playbackRate = playbackRateRef.current;
    if (offsetSeconds > 0) {
      audio.currentTime = offsetSeconds;
    }
    audioRef.current = audio;
    audio.ontimeupdate = () => {
      if (audioRef.current !== audio) {
        return;
      }
      updateCurrentPosition(sentenceId, audio.currentTime, false, {
        persist: "throttled",
      });
    };
    audio.onended = () => {
      if (audioRef.current !== audio) {
        return;
      }
      handleSentenceEnded(sentenceId);
    };
    audio.onerror = () => {
      if (audioRef.current !== audio) {
        return;
      }
      discardPlayback();
      updatePlaybackStatus("paused");
      setPlaybackError("无法播放当前句音频，请重试。");
    };

    try {
      prepareNextBrowserAudio(sentenceId, generation);
      await audio.play();
      if (audioRef.current === audio) {
        updatePlaybackStatus("playing");
      }
    } catch {
      if (playbackGenerationRef.current !== generation) {
        return;
      }
      discardPlayback();
      updatePlaybackStatus("paused");
      setPlaybackError("无法播放当前句音频，请重试。");
    }
  }

  function handleSentenceEnded(sentenceId: string) {
    const finishedIndex = sentences.findIndex((sentence) => sentence.id === sentenceId);
    const nextSentence = sentences[finishedIndex + 1];
    if (nextSentence) {
      void playSentence(nextSentence.id, false, 0);
      return;
    }
    const currentItem = playbackTimeline.items.find((item) => item.sentenceId === sentenceId);
    updateCurrentPosition(sentenceId, currentItem?.durationSeconds ?? 0, true);
    updatePlaybackStatus("paused");
  }

  function handlePlayPause() {
    if (playbackStatusRef.current === "loading") {
      return;
    }
    if (playbackStatusRef.current === "playing") {
      audioRef.current?.pause();
      queueCurrentProgress();
      updatePlaybackStatus("paused");
      return;
    }

    const sentenceId = playbackCompletedRef.current
      ? sentences[0]?.id
      : (currentSentenceIdRef.current ?? sentences[0]?.id);
    if (sentenceId) {
      if (playbackCompletedRef.current) {
        followCurrentRef.current = true;
        if (sentenceId === currentSentenceIdRef.current) {
          updateCurrentPosition(sentenceId, 0, false);
        }
      }
      void playSentence(sentenceId, false, playbackCompletedRef.current ? 0 : currentSentenceOffsetSecondsRef.current);
    }
  }

  function handleSentenceChange(sentenceId: string) {
    followCurrentRef.current = true;
    if (
      playbackStatusRef.current === "playing" ||
      playbackStatusRef.current === "loading"
    ) {
      void playSentence(sentenceId);
    } else {
      selectSentence(sentenceId);
    }
  }

  function handleSentenceClick(sentenceId: string) {
    if (sentenceId === currentSentenceIdRef.current && !playbackCompletedRef.current) {
      if (playbackStatusRef.current === "playing") {
        void playSentence(sentenceId, true);
      }
      return;
    }
    handleSentenceChange(sentenceId);
  }

  function handleSentencePointer(sentenceId: string, clickCount: number) {
    if (sentencePointerAction(clickCount) === "play") {
      followCurrentRef.current = true;
      void playSentence(sentenceId, true);
      return;
    }
    handleSentenceClick(sentenceId);
  }

  function commitTimelineSeek(targetSeconds: number) {
    const result = seekTimeline(playbackTimeline, targetSeconds);
    setPendingSeekSeconds(null);
    if (!result) {
      return;
    }
    followCurrentRef.current = true;
    setPlaybackError(null);
    if (result.completed) {
      discardPlayback();
      updateCurrentPosition(result.sentenceId, result.offsetSeconds, true, {
        resumeFollowing: true,
      });
      updatePlaybackStatus("paused");
      return;
    }
    if (playbackStatusRef.current === "playing" || playbackStatusRef.current === "loading") {
      void playSentence(result.sentenceId, false, result.offsetSeconds);
      return;
    }
    discardPlayback();
    updatePlaybackStatus("paused");
    updateCurrentPosition(result.sentenceId, result.offsetSeconds, false, {
      resumeFollowing: true,
    });
  }

  function handleTimelineSkip(deltaSeconds: number) {
    const baseSeconds = playbackCompletedRef.current
      ? playbackTimeline.totalSeconds
      : playbackTimeline.elapsedSeconds;
    commitTimelineSeek(baseSeconds + deltaSeconds);
  }

  function handleTimelinePreview(value: number) {
    setPendingSeekSeconds(value);
  }

  function commitTimelineInput(event: SyntheticEvent<HTMLInputElement>) {
    commitTimelineSeek(Number(event.currentTarget.value));
  }

  function navigateToMaterial(targetMaterialId: string) {
    queueCurrentProgress();
    autoplayOnMaterialLoadRef.current = playbackStatusRef.current === "playing" || playbackStatusRef.current === "loading";
    navigate(`/materials/${targetMaterialId}`);
  }

  function handlePlaybackRateChange(rate: number) {
    playbackRateRef.current = rate;
    setPlaybackRate(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
    audioElementCacheRef.current?.syncPlaybackRate(rate);

    const sentenceId = currentSentenceIdRef.current ?? sentences[0]?.id;
    if (sentenceId) {
      updateCurrentPosition(sentenceId, currentSentenceOffsetSecondsRef.current, playbackCompletedRef.current, {
        resumeFollowing: currentSentenceIdRef.current === null,
      });
      if (currentSentenceIdRef.current === sentenceId && playbackStatusRef.current === "idle") {
        updatePlaybackStatus("paused");
      }
    }
  }

  function handlePlaybackRateMenuToggle() {
    setShowPlaybackRateMenu((current) => !current);
  }

  function selectPlaybackRate(rate: number) {
    handlePlaybackRateChange(rate);
    setShowPlaybackRateMenu(false);
    playbackRateTriggerRef.current?.focus();
  }

  function sentenceElement() {
    const sentenceId = currentSentenceIdRef.current;
    return sentenceId ? document.getElementById(sentenceId) : null;
  }

  function readerChromeBounds() {
    const navBottom = readerNavRef.current?.getBoundingClientRect().bottom ?? 0;
    const playerTop = playerBarRef.current?.getBoundingClientRect().top ?? window.innerHeight;
    const top = Math.min(window.innerHeight, navBottom + READER_CHROME_MARGIN);
    const playerAwareBottom = playerTop - READER_CHROME_MARGIN;
    const fallbackBottom = window.innerHeight - READER_CHROME_MARGIN;
    const bottom =
      playerAwareBottom > top + 44 ? Math.min(playerAwareBottom, fallbackBottom) : fallbackBottom;
    return { top, bottom };
  }

  function isCurrentSentenceFullyVisible() {
    const element = sentenceElement();
    if (!element) {
      return true;
    }
    const rect = element.getBoundingClientRect();
    return isRectFullyVisibleWithinReaderChrome(
      { top: rect.top, bottom: rect.bottom, height: rect.height },
      readerChromeBounds(),
    );
  }

  function scheduleScrollToCurrent(behavior: ScrollBehavior) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const element = sentenceElement();
        if (element && !isCurrentSentenceFullyVisible()) {
          const rect = element.getBoundingClientRect();
          userScrollIntentUntilRef.current = 0;
          window.scrollTo({
            top: scrollTargetForRectWithinReaderChrome(
              { top: rect.top, bottom: rect.bottom, height: rect.height },
              window.scrollY,
              readerChromeBounds(),
            ),
            behavior,
          });
        }
        window.setTimeout(updateReturnToCurrent, behavior === "smooth" ? 240 : 0);
      });
    });
  }

  function updateReturnToCurrent() {
    setShowReturnToCurrent(
      currentSentenceIdRef.current !== null && !isCurrentSentenceFullyVisible(),
    );
  }

  function updateReaderNavContext() {
    const header = readerHeaderRef.current;
    const nav = readerNavRef.current;
    if (!header || !nav) {
      setShowReaderContext(false);
      return;
    }
    setShowReaderContext(
      shouldShowReaderNavContext({
        headerBottom: header.getBoundingClientRect().bottom,
        navBottom: nav.getBoundingClientRect().bottom,
      }),
    );
  }

  function returnToCurrentSentence() {
    followCurrentRef.current = true;
    scheduleScrollToCurrent("auto");
  }

  function updateReadingPreference<Key extends keyof ReadingPreferences>(
    key: Key,
    value: ReadingPreferences[Key],
  ) {
    onReadingPreferencesChange({
      ...readingPreferences,
      [key]: value,
    });
  }

  function closeReadingPreferences(returnFocus = false) {
    if (returnFocus) {
      readingPreferencesTriggerRef.current?.focus();
    }
    setShowReadingPreferences(false);
  }

  const playbackLabel =
    playbackStatus === "loading"
      ? "正在准备音频"
      : playbackStatus === "playing"
        ? "正在播放"
        : playbackCompleted
          ? "朗读完成"
          : currentSentenceId
            ? "已暂停"
            : "准备朗读";

  return (
    <main className="reader-shell">
      <nav
        ref={readerNavRef}
        className={`reader-nav ${showReaderContext ? "reader-nav-with-context" : ""}`}
        aria-label="阅读页导航"
      >
        <Link className="text-link" to="/">
          <ArrowLeft aria-hidden="true" />
          返回书架
        </Link>
        {material ? (
          <div
            className={`reader-nav-context ${
              showReaderContext ? "reader-nav-context-visible" : ""
            }`}
            aria-hidden={!showReaderContext}
          >
            <span className="reader-nav-title">{readingTitle}</span>
            {readerContextProgress ? (
              <span className="reader-nav-progress">{readerContextProgress}</span>
            ) : null}
          </div>
        ) : null}
        <div className="reader-nav-actions" ref={readingPreferencesRef}>
          <span className="reader-brand">Read Along</span>
          <button
            ref={readingPreferencesTriggerRef}
            className="icon-button reader-settings-trigger"
            type="button"
            aria-expanded={showReadingPreferences}
            aria-controls="reading-preferences-panel"
            aria-label="阅读设置"
            title="阅读设置"
            onClick={() => setShowReadingPreferences((current) => !current)}
          >
            <Settings2 aria-hidden="true" />
          </button>
          {showReadingPreferences ? (
            <div
              id="reading-preferences-panel"
              className="reading-preferences-panel"
              role="dialog"
              aria-label="阅读设置"
            >
              <div className="preference-panel-heading">
                <strong>阅读设置</strong>
                <button
                  className="icon-button"
                  type="button"
                  aria-label="关闭阅读设置"
                  title="关闭"
                  onClick={() => closeReadingPreferences(true)}
                >
                  <X aria-hidden="true" />
                </button>
              </div>
              <PreferenceOptions<FontSizePreference>
                label="字号"
                value={readingPreferences.fontSize}
                options={[
                  ["small", "小"],
                  ["standard", "标准"],
                  ["large", "大"],
                ]}
                onChange={(value) => updateReadingPreference("fontSize", value)}
              />
              <PreferenceOptions<LineHeightPreference>
                label="行距"
                value={readingPreferences.lineHeight}
                options={[
                  ["compact", "紧凑"],
                  ["standard", "标准"],
                  ["relaxed", "宽松"],
                ]}
                onChange={(value) => updateReadingPreference("lineHeight", value)}
              />
              <PreferenceOptions<ThemePreference>
                label="主题"
                value={readingPreferences.theme}
                options={[
                  ["system", "跟随系统"],
                  ["light", "浅色"],
                  ["dark", "深色"],
                ]}
                onChange={(value) => updateReadingPreference("theme", value)}
              />
              <div className="reading-audio-repair">
                <div>
                  <strong>修复朗读</strong>
                  <p>清理旧音频，并立即重新生成当前屏幕附近的朗读。</p>
                </div>
                <button
                  className="button button-secondary"
                  type="button"
                  disabled={!material || audioRepairStatus === "repairing"}
                  onClick={handleRepairAudio}
                >
                  {audioRepairStatus === "repairing" ? (
                    <LoaderCircle aria-hidden="true" className="spin" />
                  ) : (
                    <RotateCcw aria-hidden="true" />
                  )}
                  {audioRepairStatus === "repairing" ? "重新生成中…" : "重新生成朗读"}
                </button>
                {audioRepairStatus === "repairing" ? (
                  <p className="reading-audio-repair-status" role="status">
                    正在重建当前屏幕附近的音频
                  </p>
                ) : null}
                {audioRepairStatus === "success" ? (
                  <p className="reading-audio-repair-status" role="status">
                    当前屏幕附近的朗读已重新生成
                  </p>
                ) : null}
                {audioRepairStatus === "failed" ? (
                  <p className="reading-audio-repair-status reading-audio-repair-error" role="alert">
                    修复失败，请重试
                  </p>
                ) : null}
              </div>
              {readingPreferencesError ? (
                <p className="reading-preferences-error" role="alert">
                  设置已应用，但无法保存到浏览器。
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      </nav>

      {error ? (
        <section className="state-panel reader-state" role="alert">
          <p className="eyebrow">无法打开材料</p>
          <h1>阅读页加载失败</h1>
          <p>{error}</p>
          <button
            className="button button-primary"
            type="button"
            onClick={() => setMaterialReloadKey((current) => current + 1)}
          >
            重试打开
          </button>
        </section>
      ) : null}

      {!error && material === null ? (
        <section className="reader-loading" aria-live="polite" aria-label="正在打开阅读页">
          <span className="skeleton-block reader-loading-kicker" />
          <span className="skeleton-block reader-loading-title" />
          <span className="skeleton-block reader-loading-source" />
          <span className="skeleton-block reader-loading-line" />
          <span className="skeleton-block reader-loading-line" />
          <span className="skeleton-block reader-loading-line-short" />
        </section>
      ) : null}

      {!error && material ? (
        <article className="reader-entry">
          <header ref={readerHeaderRef}>
            <p className="eyebrow">{sourceLabel(material)}</p>
            <h1>{readingTitle}</h1>
            {sourceDetail ? <p className="reader-source">{sourceDetail}</p> : null}
          </header>
          <div className="reader-content">
            {material.paragraphs.map((paragraph) => (
              <section key={paragraph.id} className="reader-paragraph">
                <p>
                  {paragraph.sentences.map((sentence) => {
                    const isCurrent = sentence.id === highlightedSentenceId;
                    const isPlaying = isCurrent && playbackStatus === "playing";
                    return (
                      <span
                        key={sentence.id}
                        id={sentence.id}
                        aria-current={isCurrent ? "location" : undefined}
                        className={[
                          "reader-sentence",
                          isCurrent ? "reader-sentence-current" : "",
                          isPlaying ? "reader-sentence-playing" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        onClick={(event) => handleSentencePointer(sentence.id, event.detail)}
                      >
                        {sentence.text}
                      </span>
                    );
                  })}
                </p>
              </section>
            ))}
          </div>
        </article>
      ) : null}

      {!error && material && sentences.length > 0 ? (
        <section ref={playerBarRef} className="player-bar" aria-label="朗读控制">
          <div className="player-position" aria-live="polite">
            <strong>{playbackLabel}</strong>
            <span>{timelinePositionLabel || timelineTotalLabel}</span>
            {playbackCompleted && material.navigation.next ? (
              <span className="player-next-prompt">
                下一篇：{normalizeReadingTitle(material.navigation.next.title)}
                <button
                  className="inline-action"
                  type="button"
                  onClick={() => navigateToMaterial(material.navigation.next?.id ?? "")}
                >
                  继续
                </button>
              </span>
            ) : null}
            {playbackError ? (
              <span className="player-error" role="alert">
                {playbackError}
                <button className="inline-action" type="button" onClick={handlePlayPause}>
                  重试
                </button>
              </span>
            ) : null}
            {progressError ? (
              <span className="player-error" role="alert">
                {progressError}
                <button className="inline-action" type="button" onClick={retryProgressSave}>
                  重试
                </button>
              </span>
            ) : null}
          </div>
          <div className="player-controls">
            <div ref={playbackRateMenuRef} className="playback-rate">
              <span id="playback-rate-label">倍速</span>
              <button
                ref={playbackRateTriggerRef}
                className="playback-rate-button"
                type="button"
                aria-haspopup="listbox"
                aria-expanded={showPlaybackRateMenu}
                aria-labelledby="playback-rate-label playback-rate-value"
                onClick={handlePlaybackRateMenuToggle}
              >
                <Gauge aria-hidden="true" />
                <span id="playback-rate-value">{playbackRate}×</span>
                <ChevronDown
                  aria-hidden="true"
                  className={showPlaybackRateMenu ? "chevron chevron-open" : "chevron"}
                />
              </button>
              {showPlaybackRateMenu ? (
                <div className="playback-rate-menu" role="listbox" aria-label="播放倍速">
                  {PLAYBACK_RATES.map((rate) => (
                    <button
                      key={rate}
                      type="button"
                      role="option"
                      aria-selected={rate === playbackRate}
                      onClick={() => selectPlaybackRate(rate)}
                    >
                      <span>{rate}×</span>
                      {rate === playbackRate ? <Check aria-hidden="true" /> : null}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="player-timeline">
              <span className="timeline-time">{formatTimelineTime(displayedElapsedSeconds)}</span>
              <input
                type="range"
                min={0}
                max={Math.max(playbackTimeline.totalSeconds, 1)}
                step={0.1}
                value={Math.min(displayedElapsedSeconds, Math.max(playbackTimeline.totalSeconds, 1))}
                aria-label="朗读进度"
                onChange={(event) => handleTimelinePreview(Number(event.target.value))}
                onPointerUp={commitTimelineInput}
                onTouchEnd={commitTimelineInput}
                onKeyUp={commitTimelineInput}
                onBlur={commitTimelineInput}
              />
              <span className="timeline-time">{timelineTotalLabel}</span>
            </div>
            {showReturnToCurrent ? (
              <button className="button button-secondary return-current" type="button" onClick={returnToCurrentSentence}>
                <LocateFixed aria-hidden="true" />
                回到当前句
              </button>
            ) : null}
            <button
              className="icon-button player-icon-button"
              type="button"
              disabled={!material.navigation.previous}
              aria-label="上一篇"
              title="上一篇"
              onClick={() => {
                if (material.navigation.previous) {
                  navigateToMaterial(material.navigation.previous.id);
                }
              }}
            >
              <ChevronLeft aria-hidden="true" />
            </button>
            <button
              className="icon-button player-icon-button"
              type="button"
              aria-label="快退 15 秒"
              title="快退 15 秒"
              onClick={() => handleTimelineSkip(-SKIP_BACK_SECONDS)}
            >
              <Rewind aria-hidden="true" />
            </button>
            <button
              className="icon-button player-primary"
              type="button"
              disabled={playbackStatus === "loading"}
              aria-label={
                playbackStatus === "loading"
                  ? "正在准备音频"
                  : playbackStatus === "playing"
                    ? "暂停"
                    : playbackCompleted
                      ? "从头播放"
                      : "播放"
              }
              title={
                playbackStatus === "loading"
                  ? "正在准备音频"
                  : playbackStatus === "playing"
                    ? "暂停"
                    : playbackCompleted
                      ? "从头播放"
                      : "播放"
              }
              onClick={handlePlayPause}
            >
              {playbackStatus === "loading" ? (
                <LoaderCircle aria-hidden="true" className="spin" />
              ) : playbackStatus === "playing" ? (
                <Pause aria-hidden="true" />
              ) : playbackCompleted ? (
                <RotateCcw aria-hidden="true" />
              ) : (
                <Play aria-hidden="true" />
              )}
            </button>
            <button
              className="icon-button player-icon-button"
              type="button"
              aria-label="前进 30 秒"
              title="前进 30 秒"
              onClick={() => handleTimelineSkip(SKIP_FORWARD_SECONDS)}
            >
              <FastForward aria-hidden="true" />
            </button>
            <button
              className="icon-button player-icon-button"
              type="button"
              disabled={!material.navigation.next}
              aria-label="下一篇"
              title="下一篇"
              onClick={() => {
                if (material.navigation.next) {
                  navigateToMaterial(material.navigation.next.id);
                }
              }}
            >
              <ChevronRight aria-hidden="true" />
            </button>
          </div>
        </section>
      ) : null}
    </main>
  );
}

interface PreferenceOptionsProps<Value extends string> {
  label: string;
  value: Value;
  options: Array<[Value, string]>;
  onChange: (value: Value) => void;
}

function PreferenceOptions<Value extends string>({
  label,
  value,
  options,
  onChange,
}: PreferenceOptionsProps<Value>) {
  return (
    <fieldset className="reading-preference-group">
      <legend>{label}</legend>
      <div className="reading-preference-options">
        {options.map(([optionValue, optionLabel]) => (
          <label key={optionValue}>
            <input
              type="radio"
              name={`reading-preference-${label}`}
              value={optionValue}
              checked={value === optionValue}
              onChange={() => onChange(optionValue)}
            />
            <span>{optionLabel}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

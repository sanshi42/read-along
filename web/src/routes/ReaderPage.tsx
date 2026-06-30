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
  Maximize2,
  Minimize2,
  Pause,
  Play,
  Repeat,
  Repeat1,
  Rewind,
  RotateCcw,
  Settings2,
  X,
} from "lucide-react";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  type SyntheticEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  clearMaterialAudioCache,
  getMaterial,
  prepareSentenceAudio,
  saveProgress,
  sentenceAudioUrl,
  type MaterialDetail,
  type MaterialNavigationItem,
} from "../api";
import {
  loadPlaybackModePreference,
  savePlaybackModePreference,
} from "../playbackModePreference";
import {
  type FontSizePreference,
  type LineHeightPreference,
  type ReadingPreferences,
  type ThemePreference,
} from "../readingPreferences";
import {
  formatTimelineTime,
  isInteractiveShortcutTarget,
  seekTimeline,
} from "./readerPlaybackTimeline";
import {
  playbackModeLabel,
  type PlaybackMode,
  type PlaybackModeNavigation,
} from "./playbackMode";
import {
  ReaderPlaybackSession,
  type ReaderPlaybackSessionSnapshot,
} from "./readerPlaybackSession";
import {
  isRectFullyVisibleWithinReaderChrome,
  normalizeReadingTitle,
  readerChromeBoundsForFixedControls,
  readerContextProgressLabel,
  readerSentenceInteraction,
  sentencePointerAction,
  scrollTargetForRectWithinReaderChrome,
  shouldShowReaderNavContext,
  zenModeShortcutAction,
} from "./readerPageViewModel";

const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 2] as const;
const PLAYBACK_MODES: PlaybackMode[] = ["sequential", "repeat_list", "repeat_one"];
const SCROLL_KEYS = new Set(["ArrowDown", "ArrowUp", "End", "Home", "PageDown", "PageUp"]);
const READER_CHROME_MARGIN = 18;
const SKIP_BACK_SECONDS = 15;
const SKIP_FORWARD_SECONDS = 30;
const EMPTY_PLAYBACK_TIMELINE = {
  items: [],
  currentSentenceId: null,
  currentOffsetSeconds: 0,
  elapsedSeconds: 0,
  totalSeconds: 0,
  estimated: false,
};

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

function materialPlaybackNavigation(material: MaterialDetail): PlaybackModeNavigation {
  return {
    currentId: material.id,
    previousId: material.navigation.previous?.id ?? null,
    nextId: material.navigation.next?.id ?? null,
    firstId: material.navigation.first?.id ?? null,
    lastId: material.navigation.last?.id ?? null,
  };
}

function navigationItemForMaterial(
  material: MaterialDetail,
  targetMaterialId: string,
): MaterialNavigationItem | null {
  return (
    [
      material.navigation.first,
      material.navigation.previous,
      material.navigation.next,
      material.navigation.last,
    ].find((item) => item?.id === targetMaterialId) ?? null
  );
}

function PlaybackModeIcon({ mode }: { mode: PlaybackMode }) {
  if (mode === "repeat_one") {
    return <Repeat1 aria-hidden="true" />;
  }
  if (mode === "repeat_list") {
    return <Repeat aria-hidden="true" />;
  }
  return <ChevronRight aria-hidden="true" />;
}

function compactPlaybackModeLabel(mode: PlaybackMode) {
  switch (mode) {
    case "repeat_one":
      return "单曲";
    case "sequential":
      return "顺序";
    case "repeat_list":
      return "列表";
  }
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
  const [playbackSnapshot, setPlaybackSnapshot] =
    useState<ReaderPlaybackSessionSnapshot | null>(null);
  const [showReturnToCurrent, setShowReturnToCurrent] = useState(false);
  const [showReadingPreferences, setShowReadingPreferences] = useState(false);
  const [showPlaybackRateMenu, setShowPlaybackRateMenu] = useState(false);
  const [showPlaybackModeMenu, setShowPlaybackModeMenu] = useState(false);
  const [showReaderContext, setShowReaderContext] = useState(false);
  const [pendingSeekSeconds, setPendingSeekSeconds] = useState<number | null>(null);
  const [materialReloadKey, setMaterialReloadKey] = useState(0);
  const [zenMode, setZenMode] = useState(false);
  const [zenFullscreenNotice, setZenFullscreenNotice] = useState(false);
  const playbackSessionRef = useRef<ReaderPlaybackSession | null>(null);
  const autoplayOnMaterialLoadRef = useRef(false);
  const zenModeRef = useRef(false);
  const zenFullscreenActiveRef = useRef(false);
  const zenNoticeTimeoutRef = useRef<number | null>(null);
  const followCurrentRef = useRef(true);
  const userScrollIntentUntilRef = useRef(0);
  const readerNavRef = useRef<HTMLElement | null>(null);
  const readerHeaderRef = useRef<HTMLElement | null>(null);
  const playerBarRef = useRef<HTMLElement | null>(null);
  const readingPreferencesRef = useRef<HTMLDivElement | null>(null);
  const readingPreferencesTriggerRef = useRef<HTMLButtonElement | null>(null);
  const playbackRateMenuRef = useRef<HTMLDivElement | null>(null);
  const playbackRateTriggerRef = useRef<HTMLButtonElement | null>(null);
  const playbackModeMenuRef = useRef<HTMLDivElement | null>(null);
  const playbackModeTriggerRef = useRef<HTMLButtonElement | null>(null);

  const sentences = useMemo(
    () => material?.paragraphs.flatMap((paragraph) => paragraph.sentences) ?? [],
    [material],
  );
  const currentSentenceId = playbackSnapshot?.currentSentenceId ?? null;
  const playbackRate = playbackSnapshot?.playbackRate ?? 1;
  const playbackCompleted = playbackSnapshot?.playbackCompleted ?? false;
  const playbackStatus = playbackSnapshot?.playbackStatus ?? "idle";
  const playbackError = playbackSnapshot?.playbackError ?? null;
  const progressError = playbackSnapshot?.progressError ?? null;
  const playbackMode = playbackSnapshot?.playbackMode ?? loadPlaybackModePreference();
  const playbackModeError = playbackSnapshot?.playbackModeError ?? null;
  const audioRepairStatus = playbackSnapshot?.audioRepairStatus ?? "idle";
  const playbackTimeline = playbackSnapshot?.timeline ?? EMPTY_PLAYBACK_TIMELINE;
  const currentSentenceIndex = sentences.findIndex(
    (sentence) => sentence.id === currentSentenceId,
  );
  const sentenceIndexById = useMemo(
    () => new Map(sentences.map((sentence, index) => [sentence.id, index])),
    [sentences],
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
  const readerContextProgress = readerContextProgressLabel({
    sentenceIndex: currentSentenceIndex,
    sentenceCount: sentences.length,
    timelinePositionLabel,
    timelineTotalLabel: playbackTimeline.totalSeconds > 0 ? timelineTotalLabel : "",
  });
  const previousPlaybackTarget = playbackSnapshot?.previousTarget ?? null;
  const nextPlaybackTarget = playbackSnapshot?.nextTarget ?? null;
  const completedPromptItem =
    material && playbackCompleted && nextPlaybackTarget
      ? navigationItemForMaterial(material, nextPlaybackTarget.materialId)
      : null;

  useEffect(() => {
    void exitZenMode({ returnFocus: false });
    followCurrentRef.current = true;
    setPlaybackSnapshot(null);
    clearZenFullscreenNotice();
    zenFullscreenActiveRef.current = false;
    setShowReturnToCurrent(false);
    setShowReaderContext(false);
    setMaterial(null);
    setError(null);

    let active = true;
    let session: ReaderPlaybackSession | null = null;
    let unsubscribe: (() => void) | null = null;
    if (!materialId) {
      setError("阅读材料地址不完整");
      return () => {
        active = false;
      };
    }

    getMaterial(materialId)
      .then((item) => {
        if (!active) {
          return;
        }
        setMaterial(item);
        const loadedSentences = item.paragraphs.flatMap((paragraph) => paragraph.sentences);
        session = new ReaderPlaybackSession({
          materialId,
          sentences: loadedSentences.map((sentence) => ({
            id: sentence.id,
            text: sentence.text,
            audio_duration_seconds: sentence.audio_duration_seconds,
          })),
          progress: item.progress,
          navigation: materialPlaybackNavigation(item),
          playbackMode: loadPlaybackModePreference(),
          adapters: {
            prepareAudio: (sentenceId, reloadToken) =>
              prepareSentenceAudio(materialId, sentenceId, reloadToken),
            createAudio: (sentenceId, reloadToken) =>
              new Audio(sentenceAudioUrl(materialId, sentenceId, reloadToken)),
            saveProgress: async (progress) => {
              await saveProgress(materialId, progress);
            },
            clearAudioCache: () => clearMaterialAudioCache(materialId),
            savePlaybackMode: savePlaybackModePreference,
            navigate: (targetMaterialId, autoplay) => {
              if (zenModeRef.current) {
                void exitZenMode({ returnFocus: false });
              }
              autoplayOnMaterialLoadRef.current = autoplay;
              navigate(`/materials/${targetMaterialId}`);
            },
            now: () => performance.now(),
            createReloadToken: () => String(Date.now()),
          },
        });
        playbackSessionRef.current = session;
        let previousSentenceId = session.snapshot().currentSentenceId;
        unsubscribe = session.subscribe((snapshot) => {
          const sentenceChanged = previousSentenceId !== snapshot.currentSentenceId;
          previousSentenceId = snapshot.currentSentenceId;
          setPlaybackSnapshot(snapshot);
          if (sentenceChanged && followCurrentRef.current) {
            scheduleScrollToCurrent("smooth");
          }
        });
        if (item.progress && session.snapshot().currentSentenceId) {
          scheduleScrollToCurrent("auto");
        }
        if (autoplayOnMaterialLoadRef.current) {
          autoplayOnMaterialLoadRef.current = false;
          followCurrentRef.current = true;
          void session.playPause();
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "读取材料失败");
        }
      });
    return () => {
      active = false;
      if (session) {
        session.saveCurrentProgress();
        unsubscribe?.();
        session.dispose();
        if (playbackSessionRef.current === session) {
          playbackSessionRef.current = null;
        }
      }
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
    function handleFullscreenChange() {
      if (
        zenFullscreenActiveRef.current &&
        zenModeRef.current &&
        !document.fullscreenElement
      ) {
        zenFullscreenActiveRef.current = false;
        setZenModeState(false);
      }
    }

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

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
    if (!showPlaybackModeMenu) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (playbackModeMenuRef.current && !playbackModeMenuRef.current.contains(event.target as Node)) {
        setShowPlaybackModeMenu(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setShowPlaybackModeMenu(false);
        playbackModeTriggerRef.current?.focus();
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [showPlaybackModeMenu]);

  useEffect(() => {
    function handleGlobalShortcut(event: KeyboardEvent) {
      const target = event.target instanceof HTMLElement ? event.target : null;
      const interactiveTarget =
        target &&
        (isInteractiveShortcutTarget(target.tagName, {
          role: target.getAttribute("role"),
          contentEditable: target.getAttribute("contenteditable"),
        }) ||
          readingPreferencesRef.current?.contains(target) ||
          playbackRateMenuRef.current?.contains(target) ||
          playbackModeMenuRef.current?.contains(target));
      const zenShortcut = zenModeShortcutAction(event, {
        zenMode: zenModeRef.current,
        interactiveTarget: Boolean(interactiveTarget),
      });
      if (zenShortcut === "exit") {
        event.preventDefault();
        void exitZenMode();
        return;
      }
      if (zenShortcut === "toggle") {
        event.preventDefault();
        if (zenModeRef.current) {
          void exitZenMode();
        } else {
          void enterZenMode();
        }
        return;
      }
      if (interactiveTarget) {
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
      playbackSessionRef.current?.saveCurrentProgress();
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
      if (zenNoticeTimeoutRef.current !== null) {
        window.clearTimeout(zenNoticeTimeoutRef.current);
      }
    };
  }, []);

  function retryProgressSave() {
    playbackSessionRef.current?.retryProgressSave();
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
    await playbackSessionRef.current?.repairAudio(
      visibleSentenceIdsWithinReaderChrome(),
    );
  }

  function handlePlayPause() {
    if (playbackSessionRef.current?.snapshot().playbackCompleted) {
      followCurrentRef.current = true;
    }
    void playbackSessionRef.current?.playPause();
  }

  function handleSentenceChange(sentenceId: string) {
    followCurrentRef.current = true;
    setShowReturnToCurrent(false);
    void playbackSessionRef.current?.selectSentence(sentenceId);
  }

  function handleSentenceClick(sentenceId: string) {
    const snapshot = playbackSessionRef.current?.snapshot();
    if (sentenceId === snapshot?.currentSentenceId && !snapshot.playbackCompleted) {
      if (snapshot.playbackStatus === "playing") {
        void playbackSessionRef.current?.restartSentence(sentenceId);
      }
      return;
    }
    handleSentenceChange(sentenceId);
  }

  function handleSentencePointer(sentenceId: string, clickCount: number) {
    if (sentencePointerAction(clickCount) === "play") {
      followCurrentRef.current = true;
      void playbackSessionRef.current?.restartSentence(sentenceId);
      return;
    }
    handleSentenceClick(sentenceId);
  }

  function handleSentenceKeyDown(
    sentenceId: string,
    event: ReactKeyboardEvent<HTMLSpanElement>,
  ) {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    if (sentenceId === playbackSessionRef.current?.snapshot().currentSentenceId) {
      handlePlayPause();
    } else {
      handleSentenceChange(sentenceId);
    }
  }

  function commitTimelineSeek(targetSeconds: number) {
    setPendingSeekSeconds(null);
    followCurrentRef.current = true;
    setShowReturnToCurrent(false);
    void playbackSessionRef.current?.seek(targetSeconds).then(() => {
      scheduleScrollToCurrent("smooth");
    });
  }

  function handleTimelineSkip(deltaSeconds: number) {
    setPendingSeekSeconds(null);
    followCurrentRef.current = true;
    setShowReturnToCurrent(false);
    void playbackSessionRef.current?.skip(deltaSeconds).then(() => {
      scheduleScrollToCurrent("smooth");
    });
  }

  function handleTimelinePreview(value: number) {
    setPendingSeekSeconds(value);
  }

  function commitTimelineInput(event: SyntheticEvent<HTMLInputElement>) {
    commitTimelineSeek(Number(event.currentTarget.value));
  }

  function handlePlaybackRateMenuToggle() {
    setShowPlaybackModeMenu(false);
    setShowPlaybackRateMenu((current) => !current);
  }

  function selectPlaybackRate(rate: number) {
    playbackSessionRef.current?.setPlaybackRate(rate);
    setShowPlaybackRateMenu(false);
    playbackRateTriggerRef.current?.focus();
  }

  function handlePlaybackModeMenuToggle() {
    setShowPlaybackRateMenu(false);
    setShowPlaybackModeMenu((current) => !current);
  }

  function selectPlaybackMode(mode: PlaybackMode) {
    playbackSessionRef.current?.setPlaybackMode(mode);
    setShowPlaybackModeMenu(false);
    playbackModeTriggerRef.current?.focus();
  }

  function sentenceElement() {
    const sentenceId = playbackSessionRef.current?.snapshot().currentSentenceId;
    return sentenceId ? document.getElementById(sentenceId) : null;
  }

  function readerChromeBounds() {
    const navBottom = readerNavRef.current?.getBoundingClientRect().bottom ?? 0;
    const playerTop = playerBarRef.current?.getBoundingClientRect().top ?? null;
    return readerChromeBoundsForFixedControls({
      viewportHeight: window.innerHeight,
      navBottom,
      playerTop,
      margin: READER_CHROME_MARGIN,
    });
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
      playbackSessionRef.current?.snapshot().currentSentenceId != null &&
        !isCurrentSentenceFullyVisible(),
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

  function clearZenFullscreenNotice() {
    if (zenNoticeTimeoutRef.current !== null) {
      window.clearTimeout(zenNoticeTimeoutRef.current);
      zenNoticeTimeoutRef.current = null;
    }
    setZenFullscreenNotice(false);
  }

  function showZenFullscreenFallbackNotice() {
    if (zenNoticeTimeoutRef.current !== null) {
      window.clearTimeout(zenNoticeTimeoutRef.current);
    }
    setZenFullscreenNotice(true);
    zenNoticeTimeoutRef.current = window.setTimeout(() => {
      zenNoticeTimeoutRef.current = null;
      setZenFullscreenNotice(false);
    }, 4200);
  }

  function setZenModeState(enabled: boolean) {
    zenModeRef.current = enabled;
    setZenMode(enabled);
    if (!enabled) {
      clearZenFullscreenNotice();
    }
  }

  async function enterZenMode() {
    if (!material) {
      return;
    }
    setShowReadingPreferences(false);
    setShowPlaybackRateMenu(false);
    setShowPlaybackModeMenu(false);
    setZenModeState(true);
    followCurrentRef.current = true;
    setShowReturnToCurrent(false);
    scheduleScrollToCurrent("smooth");

    const fullscreenTarget = document.documentElement;
    if (!fullscreenTarget.requestFullscreen) {
      showZenFullscreenFallbackNotice();
      return;
    }
    if (document.fullscreenElement) {
      zenFullscreenActiveRef.current = true;
      return;
    }
    try {
      await fullscreenTarget.requestFullscreen();
      if (zenModeRef.current && document.fullscreenElement) {
        zenFullscreenActiveRef.current = true;
      } else if (zenModeRef.current) {
        showZenFullscreenFallbackNotice();
      }
    } catch {
      if (zenModeRef.current) {
        showZenFullscreenFallbackNotice();
      }
    }
  }

  async function exitZenMode(
    options: { exitFullscreen?: boolean; returnFocus?: boolean } = {},
  ) {
    const exitFullscreen = options.exitFullscreen ?? true;
    zenFullscreenActiveRef.current = false;
    setZenModeState(false);
    if (options.returnFocus) {
      readingPreferencesTriggerRef.current?.focus();
    }
    if (exitFullscreen && document.fullscreenElement && document.exitFullscreen) {
      try {
        await document.exitFullscreen();
      } catch {
        // 浏览器可能已经在处理退出全屏；页面内禅模式已经退出。
      }
    }
  }

  function renderPlaybackIssues() {
    return (
      <>
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
        {playbackModeError ? (
          <span className="player-error" role="alert">
            {playbackModeError}
          </span>
        ) : null}
      </>
    );
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
    <main className={zenMode ? "reader-shell reader-shell-zen" : "reader-shell"}>
      {zenMode ? (
        <button
          className="icon-button zen-exit-button"
          type="button"
          aria-label="退出禅模式"
          title="退出禅模式"
          onClick={() => void exitZenMode()}
        >
          <Minimize2 aria-hidden="true" />
        </button>
      ) : (
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
            {material ? (
              <button
                className="icon-button reader-settings-trigger"
                type="button"
                aria-label="进入禅模式"
                aria-keyshortcuts="Z"
                title="禅模式 (Z)"
                onClick={() => void enterZenMode()}
              >
                <Maximize2 aria-hidden="true" />
              </button>
            ) : null}
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
      )}

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
            <p className="reader-source-type">{sourceLabel(material)}</p>
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
                    const sentenceIndex = sentenceIndexById.get(sentence.id) ?? -1;
                    const interaction = readerSentenceInteraction({
                      sentenceIndex,
                      sentenceCount: sentences.length,
                      isCurrent,
                      isPlaying,
                    });
                    return (
                      <span
                        key={sentence.id}
                        id={sentence.id}
                        aria-current={interaction.ariaCurrent}
                        aria-label={interaction.ariaLabel}
                        className={[
                          "reader-sentence",
                          isCurrent ? "reader-sentence-current" : "",
                          isPlaying ? "reader-sentence-playing" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        tabIndex={interaction.tabIndex}
                        onClick={(event) => handleSentencePointer(sentence.id, event.detail)}
                        onKeyDown={(event) => handleSentenceKeyDown(sentence.id, event)}
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

      {zenMode && !error && material && sentences.length > 0 ? (
        <section ref={playerBarRef} className="zen-status-bar" aria-label="禅模式朗读状态">
          <div className="zen-status-content" aria-live="polite">
            <strong>{playbackLabel}</strong>
            <span>{timelinePositionLabel || timelineTotalLabel}</span>
            {zenFullscreenNotice ? (
              <span className="zen-status-notice" role="status">
                浏览器未进入全屏，已保留禅模式
              </span>
            ) : null}
            {renderPlaybackIssues()}
          </div>
        </section>
      ) : null}

      {!zenMode && !error && material && sentences.length > 0 ? (
        <section ref={playerBarRef} className="player-bar player-bar-slim" aria-label="朗读控制">
              <div className="player-timeline player-timeline-slim">
                <span className="timeline-time timeline-time-combo">
                  {formatTimelineTime(displayedElapsedSeconds)}/{timelineTotalLabel.replace(/^约\s*/, "")}
                </span>
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
              </div>
              <div className="player-actions-slim">
                <div className="player-settings-slim">
                  <div ref={playbackModeMenuRef} className="player-setting playback-mode">
                    <span id="playback-mode-label">模式</span>
                    <button
                      ref={playbackModeTriggerRef}
                      className="player-setting-button playback-mode-button"
                      type="button"
                      aria-haspopup="listbox"
                      aria-expanded={showPlaybackModeMenu}
                      aria-label={`播放模式：${playbackModeLabel(playbackMode)}`}
                      title="播放模式"
                      onClick={handlePlaybackModeMenuToggle}
                    >
                      <PlaybackModeIcon mode={playbackMode} />
                      <span>{compactPlaybackModeLabel(playbackMode)}</span>
                      <ChevronDown aria-hidden="true" className={showPlaybackModeMenu ? "chevron chevron-open" : "chevron"} />
                    </button>
                    {showPlaybackModeMenu ? (
                      <div className="player-setting-menu playback-mode-menu" role="listbox" aria-label="播放模式">
                        {PLAYBACK_MODES.map((mode) => (
                          <button key={mode} type="button" role="option" aria-selected={mode === playbackMode} onClick={() => selectPlaybackMode(mode)}>
                            <PlaybackModeIcon mode={mode} />
                            <span>{playbackModeLabel(mode)}</span>
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div ref={playbackRateMenuRef} className="player-setting playback-rate">
                    <span id="playback-rate-label">倍速</span>
                    <button
                      ref={playbackRateTriggerRef}
                      className="player-setting-button playback-rate-button"
                      type="button"
                      aria-haspopup="listbox"
                      aria-expanded={showPlaybackRateMenu}
                      aria-labelledby="playback-rate-label playback-rate-value"
                      onClick={handlePlaybackRateMenuToggle}
                    >
                      <Gauge aria-hidden="true" />
                      <span id="playback-rate-value">{playbackRate}×</span>
                      <ChevronDown aria-hidden="true" className={showPlaybackRateMenu ? "chevron chevron-open" : "chevron"} />
                    </button>
                    {showPlaybackRateMenu ? (
                      <div className="player-setting-menu playback-rate-menu" role="listbox" aria-label="播放倍速">
                        {PLAYBACK_RATES.map((rate) => (
                          <button key={rate} type="button" role="option" aria-selected={rate === playbackRate} onClick={() => selectPlaybackRate(rate)}>
                            <span>{rate}×</span>
                            {rate === playbackRate ? <Check aria-hidden="true" /> : null}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
                {showReturnToCurrent ? (
                  <button className="icon-button player-icon-button" type="button" aria-label="回到当前句" title="回到当前句" onClick={returnToCurrentSentence}>
                    <LocateFixed aria-hidden="true" />
                  </button>
                ) : null}
                <div className="player-transport-slim">
                  {previousPlaybackTarget ? (
                    <button className="icon-button player-icon-button" type="button" aria-label="上一篇" title="上一篇" onClick={() => playbackSessionRef.current?.navigatePrevious()}>
                      <ChevronLeft aria-hidden="true" />
                    </button>
                  ) : null}
                  <button className="icon-button player-icon-button" type="button" aria-label="快退 15 秒" title="快退 15 秒" onClick={() => handleTimelineSkip(-SKIP_BACK_SECONDS)}>
                    <Rewind aria-hidden="true" />
                  </button>
                  <button className="icon-button player-primary" type="button" disabled={playbackStatus === "loading"} aria-label={playbackStatus === "loading" ? "正在准备音频" : playbackStatus === "playing" ? "暂停" : playbackCompleted ? "从头播放" : "播放"} title={playbackStatus === "loading" ? "正在准备音频" : playbackStatus === "playing" ? "暂停" : playbackCompleted ? "从头播放" : "播放"} onClick={handlePlayPause}>
                    {playbackStatus === "loading" ? <LoaderCircle aria-hidden="true" className="spin" /> : playbackStatus === "playing" ? <Pause aria-hidden="true" /> : playbackCompleted ? <RotateCcw aria-hidden="true" /> : <Play aria-hidden="true" />}
                  </button>
                  <button className="icon-button player-icon-button" type="button" aria-label="前进 30 秒" title="前进 30 秒" onClick={() => handleTimelineSkip(SKIP_FORWARD_SECONDS)}>
                    <FastForward aria-hidden="true" />
                  </button>
                  {nextPlaybackTarget ? (
                    <button className="icon-button player-icon-button" type="button" aria-label="下一篇" title="下一篇" onClick={() => playbackSessionRef.current?.navigateNext()}>
                      <ChevronRight aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
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

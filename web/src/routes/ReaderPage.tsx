import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  LocateFixed,
  LoaderCircle,
  Pause,
  Play,
  RotateCcw,
  Settings2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getMaterial,
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

type PlaybackStatus = "idle" | "loading" | "playing" | "paused";
type ProgressInput = Pick<
  ReadingProgress,
  "sentence_id" | "playback_rate" | "playback_completed"
>;

const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 2] as const;
const SCROLL_KEYS = new Set(["ArrowDown", "ArrowUp", "End", "Home", "PageDown", "PageUp", " "]);

interface ReaderPageProps {
  readingPreferences: ReadingPreferences;
  readingPreferencesError: boolean;
  onReadingPreferencesChange: (preferences: ReadingPreferences) => void;
}

function sourceLabel(material: MaterialDetail) {
  return material.primary_source.source_type === "pdf" ? "文本型 PDF" : "网页";
}

export function ReaderPage({
  readingPreferences,
  readingPreferencesError,
  onReadingPreferencesChange,
}: ReaderPageProps) {
  const { materialId } = useParams();
  const [material, setMaterial] = useState<MaterialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSentenceId, setCurrentSentenceId] = useState<string | null>(null);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [playbackCompleted, setPlaybackCompleted] = useState(false);
  const [playbackStatus, setPlaybackStatus] = useState<PlaybackStatus>("idle");
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [progressError, setProgressError] = useState<string | null>(null);
  const [showReturnToCurrent, setShowReturnToCurrent] = useState(false);
  const [showReadingPreferences, setShowReadingPreferences] = useState(false);
  const [focusableSentenceId, setFocusableSentenceId] = useState<string | null>(null);
  const [materialReloadKey, setMaterialReloadKey] = useState(0);
  const currentSentenceIdRef = useRef<string | null>(null);
  const playbackRateRef = useRef(1);
  const playbackCompletedRef = useRef(false);
  const playbackStatusRef = useRef<PlaybackStatus>("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playbackGenerationRef = useRef(0);
  const activeMaterialIdRef = useRef<string | null>(null);
  const pendingProgressRef = useRef<ProgressInput | null>(null);
  const savingProgressRef = useRef(false);
  const progressBlockedRef = useRef(false);
  const progressGenerationRef = useRef(0);
  const followCurrentRef = useRef(true);
  const userScrollIntentUntilRef = useRef(0);
  const readingPreferencesRef = useRef<HTMLDivElement | null>(null);
  const readingPreferencesTriggerRef = useRef<HTMLButtonElement | null>(null);

  const sentences = useMemo(
    () => material?.paragraphs.flatMap((paragraph) => paragraph.sentences) ?? [],
    [material],
  );
  const currentSentenceIndex = sentences.findIndex(
    (sentence) => sentence.id === currentSentenceId,
  );

  useEffect(() => {
    discardPlayback();
    resetProgressSaving();
    currentSentenceIdRef.current = null;
    playbackRateRef.current = 1;
    playbackCompletedRef.current = false;
    followCurrentRef.current = true;
    activeMaterialIdRef.current = materialId ?? null;
    setCurrentSentenceId(null);
    setPlaybackRate(1);
    setPlaybackCompleted(false);
    setPlaybackError(null);
    setProgressError(null);
    setShowReturnToCurrent(false);
    setFocusableSentenceId(null);
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
        const sentenceExists =
          progress !== null &&
          item.paragraphs.some((paragraph) =>
            paragraph.sentences.some((sentence) => sentence.id === progress.sentence_id),
          );
        if (progress && sentenceExists) {
          currentSentenceIdRef.current = progress.sentence_id;
          playbackRateRef.current = progress.playback_rate;
          playbackCompletedRef.current = progress.playback_completed;
          setCurrentSentenceId(progress.sentence_id);
          setPlaybackRate(progress.playback_rate);
          setPlaybackCompleted(progress.playback_completed);
          updatePlaybackStatus("paused");
          scheduleScrollToCurrent("auto");
        }
        setFocusableSentenceId(
          progress && sentenceExists
            ? progress.sentence_id
            : (item.paragraphs[0]?.sentences[0]?.id ?? null),
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
    }

    window.addEventListener("wheel", recordUserScrollIntent, { passive: true });
    window.addEventListener("touchmove", recordUserScrollIntent, { passive: true });
    window.addEventListener("keydown", recordKeyboardScrollIntent);
    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", updateReturnToCurrent);
    return () => {
      window.removeEventListener("wheel", recordUserScrollIntent);
      window.removeEventListener("touchmove", recordUserScrollIntent);
      window.removeEventListener("keydown", recordKeyboardScrollIntent);
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", updateReturnToCurrent);
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
    return () => {
      playbackGenerationRef.current += 1;
      progressGenerationRef.current += 1;
      const audio = audioRef.current;
      if (audio) {
        audio.pause();
        audio.onended = null;
        audio.onerror = null;
        audio.removeAttribute("src");
        audio.load();
      }
    };
  }, []);

  function updatePlaybackStatus(status: PlaybackStatus) {
    playbackStatusRef.current = status;
    setPlaybackStatus(status);
  }

  function updateCurrentPosition(
    sentenceId: string,
    completed: boolean,
    options: { persist?: boolean; resumeFollowing?: boolean; scrollBehavior?: ScrollBehavior } = {},
  ) {
    currentSentenceIdRef.current = sentenceId;
    playbackCompletedRef.current = completed;
    setCurrentSentenceId(sentenceId);
    setFocusableSentenceId(sentenceId);
    setPlaybackCompleted(completed);
    if (options.resumeFollowing) {
      followCurrentRef.current = true;
      setShowReturnToCurrent(false);
    }
    if (options.persist !== false) {
      queueProgress({
        sentence_id: sentenceId,
        playback_rate: playbackRateRef.current,
        playback_completed: completed,
      });
    }
    if (followCurrentRef.current) {
      scheduleScrollToCurrent(options.scrollBehavior ?? "smooth");
    }
  }

  function discardPlayback() {
    playbackGenerationRef.current += 1;

    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      audio.pause();
      audio.onended = null;
      audio.onerror = null;
      audio.removeAttribute("src");
      audio.load();
    }
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
    void flushProgress();
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

  function selectSentence(sentenceId: string) {
    discardPlayback();
    setPlaybackError(null);
    setFocusableSentenceId(sentenceId);
    updatePlaybackStatus("paused");
    updateCurrentPosition(sentenceId, false, { resumeFollowing: true });
  }

  async function playSentence(sentenceId: string, restart = false) {
    if (!materialId) {
      return;
    }

    setPlaybackError(null);
    const activeAudio = audioRef.current;
    if (activeAudio && currentSentenceIdRef.current === sentenceId) {
      if (restart || activeAudio.ended) {
        activeAudio.currentTime = 0;
      }
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
    updateCurrentPosition(sentenceId, false);
    updatePlaybackStatus("loading");
    const generation = playbackGenerationRef.current;
    const audio = new Audio(sentenceAudioUrl(materialId, sentenceId));
    audio.playbackRate = playbackRateRef.current;
    audioRef.current = audio;
    audio.onended = () => {
      if (audioRef.current !== audio) {
        return;
      }
      const finishedIndex = sentences.findIndex((sentence) => sentence.id === sentenceId);
      const nextSentence = sentences[finishedIndex + 1];
      if (nextSentence) {
        void playSentence(nextSentence.id);
      } else {
        updateCurrentPosition(sentenceId, true);
        updatePlaybackStatus("paused");
      }
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

  function handlePlayPause() {
    if (playbackStatusRef.current === "loading") {
      return;
    }
    if (playbackStatusRef.current === "playing") {
      audioRef.current?.pause();
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
          updateCurrentPosition(sentenceId, false);
        }
      }
      void playSentence(sentenceId);
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
    setFocusableSentenceId(sentenceId);
    if (sentenceId === currentSentenceIdRef.current && !playbackCompletedRef.current) {
      if (playbackStatusRef.current === "playing") {
        void playSentence(sentenceId, true);
      }
      return;
    }
    handleSentenceChange(sentenceId);
  }

  function handlePlaybackRateChange(rate: number) {
    playbackRateRef.current = rate;
    setPlaybackRate(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }

    const sentenceId = currentSentenceIdRef.current ?? sentences[0]?.id;
    if (sentenceId) {
      updateCurrentPosition(sentenceId, playbackCompletedRef.current, {
        resumeFollowing: currentSentenceIdRef.current === null,
      });
      if (currentSentenceIdRef.current === sentenceId && playbackStatusRef.current === "idle") {
        updatePlaybackStatus("paused");
      }
    }
  }

  function sentenceElement() {
    const sentenceId = currentSentenceIdRef.current;
    return sentenceId ? document.getElementById(sentenceId) : null;
  }

  function isCurrentSentenceFullyVisible() {
    const element = sentenceElement();
    if (!element) {
      return true;
    }
    const rect = element.getBoundingClientRect();
    return rect.top >= 72 && rect.bottom <= window.innerHeight - 120;
  }

  function scheduleScrollToCurrent(behavior: ScrollBehavior) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const element = sentenceElement();
        if (element && !isCurrentSentenceFullyVisible()) {
          userScrollIntentUntilRef.current = 0;
          element.scrollIntoView({ behavior, block: "center" });
        }
        updateReturnToCurrent();
      });
    });
  }

  function updateReturnToCurrent() {
    setShowReturnToCurrent(
      !followCurrentRef.current &&
        currentSentenceIdRef.current !== null &&
        !isCurrentSentenceFullyVisible(),
    );
  }

  function returnToCurrentSentence() {
    followCurrentRef.current = true;
    setShowReturnToCurrent(false);
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

  function handleSentenceKeyDown(event: React.KeyboardEvent<HTMLSpanElement>, sentenceId: string) {
    const currentIndex = sentences.findIndex((sentence) => sentence.id === sentenceId);
    let nextIndex = currentIndex;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = Math.min(currentIndex + 1, sentences.length - 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = Math.max(currentIndex - 1, 0);
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = sentences.length - 1;
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      event.stopPropagation();
      handleSentenceClick(sentenceId);
      return;
    } else {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    const nextSentenceId = sentences[nextIndex]?.id;
    if (nextSentenceId) {
      document.getElementById(nextSentenceId)?.focus();
      setFocusableSentenceId(nextSentenceId);
    }
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
      <nav className="reader-nav" aria-label="阅读页导航">
        <Link className="text-link" to="/">
          <ArrowLeft aria-hidden="true" />
          返回书架
        </Link>
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
          <header>
            <p className="eyebrow">{sourceLabel(material)}</p>
            <h1>{material.title}</h1>
            <p className="reader-source">{material.primary_source.source_uri}</p>
          </header>
          <div className="reader-content">
            {material.paragraphs.map((paragraph) => (
              <section key={paragraph.id} className="reader-paragraph">
                <p>
                  {paragraph.sentences.map((sentence) => {
                    const isCurrent = sentence.id === currentSentenceId;
                    const isPlaying = isCurrent && playbackStatus === "playing";
                    return (
                      <span
                        key={sentence.id}
                        id={sentence.id}
                        role="button"
                        tabIndex={sentence.id === focusableSentenceId ? 0 : -1}
                        aria-current={isCurrent ? "true" : undefined}
                        aria-label={`${sentence.text}${isCurrent ? " 当前句" : ""}`}
                        className={[
                          "reader-sentence",
                          isCurrent ? "reader-sentence-current" : "",
                          isPlaying ? "reader-sentence-playing" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        onClick={() => handleSentenceClick(sentence.id)}
                        onFocus={() => setFocusableSentenceId(sentence.id)}
                        onKeyDown={(event) => handleSentenceKeyDown(event, sentence.id)}
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
        <section className="player-bar" aria-label="朗读控制">
          <div className="player-position" aria-live="polite">
            <strong>{playbackLabel}</strong>
            <span>
              {currentSentenceIndex >= 0
                ? `第 ${currentSentenceIndex + 1} / ${sentences.length} 句`
                : `共 ${sentences.length} 句`}
            </span>
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
            <label className="playback-rate">
              <span>倍速</span>
              <select
                aria-label="播放倍速"
                value={playbackRate}
                onChange={(event) => handlePlaybackRateChange(Number(event.target.value))}
              >
                {PLAYBACK_RATES.map((rate) => (
                  <option key={rate} value={rate}>
                    {rate}×
                  </option>
                ))}
              </select>
            </label>
            {showReturnToCurrent ? (
              <button className="button button-secondary return-current" type="button" onClick={returnToCurrentSentence}>
                <LocateFixed aria-hidden="true" />
                回到当前句
              </button>
            ) : null}
            <button
              className="icon-button player-icon-button"
              type="button"
              disabled={currentSentenceIndex <= 0}
              aria-label="上一句"
              title="上一句"
              onClick={() => handleSentenceChange(sentences[currentSentenceIndex - 1].id)}
            >
              <ChevronLeft aria-hidden="true" />
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
              disabled={
                currentSentenceIndex < 0 || currentSentenceIndex >= sentences.length - 1
              }
              aria-label="下一句"
              title="下一句"
              onClick={() => handleSentenceChange(sentences[currentSentenceIndex + 1].id)}
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

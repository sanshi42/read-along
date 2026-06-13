import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getMaterial,
  saveProgress,
  sentenceAudioUrl,
  type MaterialDetail,
  type ReadingProgress,
} from "../api";

type PlaybackStatus = "idle" | "loading" | "playing" | "paused";
type ProgressInput = Pick<
  ReadingProgress,
  "sentence_id" | "playback_rate" | "playback_completed"
>;

const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 2] as const;
const SCROLL_KEYS = new Set(["ArrowDown", "ArrowUp", "End", "Home", "PageDown", "PageUp", " "]);

function sourceLabel(material: MaterialDetail) {
  return material.primary_source.source_type === "pdf" ? "文本型 PDF" : "网页";
}

export function ReaderPage() {
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
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "读取材料失败");
        }
      });
    return () => {
      active = false;
    };
  }, [materialId]);

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
          ← 返回书架
        </Link>
        <span>Read Along</span>
      </nav>

      {error ? (
        <section className="state-panel reader-state" role="alert">
          <p className="eyebrow">无法打开材料</p>
          <h1>阅读页加载失败</h1>
          <p>{error}</p>
        </section>
      ) : null}

      {!error && material === null ? (
        <section className="state-panel reader-state" aria-live="polite">
          <div className="loading-mark" aria-hidden="true" />
          <h1>正在打开阅读页</h1>
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
                        tabIndex={0}
                        aria-current={isCurrent ? "true" : undefined}
                        className={[
                          "reader-sentence",
                          isCurrent ? "reader-sentence-current" : "",
                          isPlaying ? "reader-sentence-playing" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        onClick={() => handleSentenceClick(sentence.id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            handleSentenceClick(sentence.id);
                          }
                        }}
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
              <button type="button" onClick={returnToCurrentSentence}>
                回到当前句
              </button>
            ) : null}
            <button
              type="button"
              disabled={currentSentenceIndex <= 0}
              onClick={() => handleSentenceChange(sentences[currentSentenceIndex - 1].id)}
            >
              上一句
            </button>
            <button
              className="player-primary"
              type="button"
              disabled={playbackStatus === "loading"}
              onClick={handlePlayPause}
            >
              {playbackStatus === "loading"
                ? "准备中"
                : playbackStatus === "playing"
                  ? "暂停"
                  : playbackCompleted
                    ? "从头播放"
                    : "播放"}
            </button>
            <button
              type="button"
              disabled={
                currentSentenceIndex < 0 || currentSentenceIndex >= sentences.length - 1
              }
              onClick={() => handleSentenceChange(sentences[currentSentenceIndex + 1].id)}
            >
              下一句
            </button>
          </div>
        </section>
      ) : null}
    </main>
  );
}

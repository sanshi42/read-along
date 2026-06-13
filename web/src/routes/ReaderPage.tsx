import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getMaterial, sentenceAudioUrl, type MaterialDetail } from "../api";

type PlaybackStatus = "idle" | "loading" | "playing" | "paused";

function sourceLabel(material: MaterialDetail) {
  return material.primary_source.source_type === "pdf" ? "文本型 PDF" : "网页";
}

export function ReaderPage() {
  const { materialId } = useParams();
  const [material, setMaterial] = useState<MaterialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSentenceId, setCurrentSentenceId] = useState<string | null>(null);
  const [playbackStatus, setPlaybackStatus] = useState<PlaybackStatus>("idle");
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const currentSentenceIdRef = useRef<string | null>(null);
  const playbackStatusRef = useRef<PlaybackStatus>("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playbackGenerationRef = useRef(0);

  const sentences = useMemo(
    () => material?.paragraphs.flatMap((paragraph) => paragraph.sentences) ?? [],
    [material],
  );
  const currentSentenceIndex = sentences.findIndex(
    (sentence) => sentence.id === currentSentenceId,
  );

  useEffect(() => {
    discardPlayback();
    currentSentenceIdRef.current = null;
    setCurrentSentenceId(null);
    setPlaybackError(null);
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
        if (active) {
          setMaterial(item);
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
    return () => {
      playbackGenerationRef.current += 1;
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

  function updateCurrentSentence(sentenceId: string) {
    currentSentenceIdRef.current = sentenceId;
    setCurrentSentenceId(sentenceId);
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

  function selectSentence(sentenceId: string) {
    discardPlayback();
    updateCurrentSentence(sentenceId);
    setPlaybackError(null);
    updatePlaybackStatus("paused");
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
    updateCurrentSentence(sentenceId);
    updatePlaybackStatus("loading");
    const generation = playbackGenerationRef.current;
    const audio = new Audio(sentenceAudioUrl(materialId, sentenceId));
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

    const sentenceId = currentSentenceIdRef.current ?? sentences[0]?.id;
    if (sentenceId) {
      void playSentence(sentenceId);
    }
  }

  function handleSentenceChange(sentenceId: string) {
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
    if (sentenceId === currentSentenceIdRef.current) {
      if (playbackStatusRef.current === "playing") {
        void playSentence(sentenceId, true);
      }
      return;
    }
    handleSentenceChange(sentenceId);
  }

  const playbackLabel =
    playbackStatus === "loading"
      ? "正在准备音频"
      : playbackStatus === "playing"
        ? "正在播放"
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
                  {paragraph.sentences.map((sentence) => (
                    <span
                      key={sentence.id}
                      id={sentence.id}
                      role="button"
                      tabIndex={0}
                      className="reader-sentence"
                      onClick={() => handleSentenceClick(sentence.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          handleSentenceClick(sentence.id);
                        }
                      }}
                    >
                      {sentence.text}
                    </span>
                  ))}
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
          </div>
          <div className="player-controls">
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

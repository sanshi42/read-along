import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getMaterial, type MaterialDetail } from "../api";

function sourceLabel(material: MaterialDetail) {
  return material.primary_source.source_type === "pdf" ? "文本型 PDF" : "网页";
}

export function ReaderPage() {
  const { materialId } = useParams();
  const [material, setMaterial] = useState<MaterialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSentenceId, setCurrentSentenceId] = useState<string | null>(null);

  useEffect(() => {
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

  const handleSentenceClick = useCallback((sentenceId: string) => {
    setCurrentSentenceId(sentenceId);
  }, []);

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
                      className={
                        "reader-sentence" +
                        (sentence.id === currentSentenceId
                          ? " reader-sentence-active"
                          : "")
                      }
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
    </main>
  );
}

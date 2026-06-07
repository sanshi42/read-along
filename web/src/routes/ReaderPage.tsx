import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getMaterial, type MaterialDetail } from "../api";

function sourceLabel(material: MaterialDetail) {
  return material.primary_source.source_type === "pdf" ? "文本型 PDF" : "网页";
}

export function ReaderPage() {
  const { materialId } = useParams();
  const [material, setMaterial] = useState<MaterialDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          <section className="reader-placeholder">
            <p className="eyebrow">阅读页入口已就绪</p>
            <h2>正文阅读界面将在下一任务实现</h2>
            <p>材料详情已经成功载入。下一步会在这里按段落和句子展示正文。</p>
          </section>
        </article>
      ) : null}
    </main>
  );
}

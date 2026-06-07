import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { importUrl, listMaterials, type MaterialSummary } from "../api";

const dateFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "short",
  day: "numeric",
});

function sourceLabel(material: MaterialSummary) {
  return material.primary_source.source_type === "pdf" ? "PDF" : "网页";
}

export function ShelfPage() {
  const [materials, setMaterials] = useState<MaterialSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listMaterials()
      .then((items) => {
        if (active) {
          setMaterials(items);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "读取书架失败");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleUrlImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextUrl = url.trim();
    if (!nextUrl) {
      setImportError("请输入网页 URL");
      setImportMessage(null);
      return;
    }

    setImporting(true);
    setImportError(null);
    setImportMessage(null);
    try {
      const imported = await importUrl(nextUrl);
      setMaterials((current) => {
        if (!current) {
          return [imported];
        }
        return [imported, ...current.filter((item) => item.id !== imported.id)];
      });
      setUrl("");
      setImportMessage(`已导入：${imported.title}`);
    } catch (reason: unknown) {
      setImportError(reason instanceof Error ? reason.message : "网页导入失败");
    } finally {
      setImporting(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">本地阅读空间</p>
          <h1>Read Along</h1>
          <p className="page-intro">把值得慢读的材料留在这里，之后从任意一句继续。</p>
        </div>
        <div className="local-badge">
          <span aria-hidden="true" />
          仅保存在本机
        </div>
      </header>

      <section className="import-band" aria-labelledby="url-import-heading">
        <div>
          <p className="eyebrow">导入</p>
          <h2 id="url-import-heading">公开网页</h2>
        </div>
        <form className="url-import-form" onSubmit={handleUrlImport}>
          <label htmlFor="url-input">网页 URL</label>
          <div className="url-import-row">
            <input
              id="url-input"
              type="url"
              inputMode="url"
              placeholder="https://example.com/article"
              value={url}
              disabled={importing}
              onChange={(event) => setUrl(event.target.value)}
            />
            <button type="submit" disabled={importing}>
              {importing ? "导入中" : "导入"}
            </button>
          </div>
          {importError ? (
            <p className="import-feedback import-feedback-error" role="alert">
              {importError}
            </p>
          ) : null}
          {importMessage ? (
            <p className="import-feedback" aria-live="polite">
              {importMessage}
            </p>
          ) : null}
        </form>
      </section>

      <section aria-labelledby="shelf-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">书架</p>
            <h2 id="shelf-heading">阅读材料</h2>
          </div>
          {materials && materials.length > 0 ? <span>{materials.length} 篇</span> : null}
        </div>

        {error ? (
          <section className="state-panel" role="alert">
            <p className="eyebrow">连接失败</p>
            <h2>暂时无法读取书架</h2>
            <p>{error}</p>
            <p className="state-hint">请确认本地 Read Along 后端已启动，然后刷新页面。</p>
          </section>
        ) : null}

        {!error && materials === null ? (
          <section className="state-panel" aria-live="polite">
            <div className="loading-mark" aria-hidden="true" />
            <h2>正在读取书架</h2>
          </section>
        ) : null}

        {!error && materials?.length === 0 ? (
          <section className="state-panel empty-panel">
            <div className="empty-icon" aria-hidden="true">
              RA
            </div>
            <p className="eyebrow">书架还是空的</p>
            <h2>先导入一篇值得阅读的材料</h2>
            <p>在上方输入公开网页 URL，或通过后端 PDF 导入接口添加文本型 PDF。</p>
          </section>
        ) : null}

        {!error && materials && materials.length > 0 ? (
          <div className="material-grid">
            {materials.map((material) => (
              <Link className="material-card" key={material.id} to={`/materials/${material.id}`}>
                <div className="material-card-topline">
                  <span className={`source-chip source-chip-${material.primary_source.source_type}`}>
                    {sourceLabel(material)}
                  </span>
                  <time dateTime={material.updated_at}>{dateFormatter.format(new Date(material.updated_at))}</time>
                </div>
                <h3>{material.title}</h3>
                <p className="source-uri">{material.primary_source.source_uri}</p>
                <span className="open-label">打开阅读页 <span aria-hidden="true">→</span></span>
              </Link>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}

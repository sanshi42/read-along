import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  importPdf,
  importUrl,
  listMaterials,
  type ImportOutcome,
  type MaterialImportResult,
  type MaterialSummary,
  type UrlImportMode,
} from "../api";

type ImportType = "url" | "pdf";

const dateFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "short",
  day: "numeric",
});

function sourceLabel(material: MaterialSummary) {
  return material.primary_source.source_type === "pdf" ? "PDF" : "网页";
}

function importMessage(outcome: ImportOutcome, title: string) {
  switch (outcome) {
    case "created":
      return `已导入：${title}`;
    case "reused_source":
      return `已存在此来源，已复用阅读材料：${title}`;
    case "reused_content":
      return `正文已存在，已关联新来源并复用阅读材料：${title}`;
  }
}

export function ShelfPage() {
  const [materials, setMaterials] = useState<MaterialSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shelfReloadKey, setShelfReloadKey] = useState(0);
  const [importType, setImportType] = useState<ImportType>("url");
  const [url, setUrl] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [importMode, setImportMode] = useState<UrlImportMode>("auto");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<MaterialImportResult | null>(null);
  const pdfInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let active = true;
    setError(null);
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
  }, [shelfReloadKey]);

  function applyImportResult(result: MaterialImportResult) {
    const imported = result.material;
    setMaterials((current) => {
      if (!current) {
        return [imported];
      }
      if (result.outcome === "reused_source") {
        return current.map((item) => (item.id === imported.id ? imported : item));
      }
      return [imported, ...current.filter((item) => item.id !== imported.id)];
    });
    setImportResult(result);
  }

  async function handleUrlImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextUrl = url.trim();
    if (!nextUrl) {
      setImportError("请输入网页 URL");
      setImportResult(null);
      return;
    }

    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await importUrl(nextUrl, importMode);
      applyImportResult(result);
      setUrl("");
    } catch (reason: unknown) {
      setImportError(reason instanceof Error ? reason.message : "网页导入失败");
    } finally {
      setImporting(false);
    }
  }

  async function handlePdfImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pdfFile) {
      setImportError("请选择文本型 PDF 文件");
      setImportResult(null);
      return;
    }

    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await importPdf(pdfFile);
      applyImportResult(result);
      setPdfFile(null);
      if (pdfInputRef.current) {
        pdfInputRef.current.value = "";
      }
    } catch (reason: unknown) {
      setImportError(reason instanceof Error ? reason.message : "PDF 导入失败");
    } finally {
      setImporting(false);
    }
  }

  function selectImportType(type: ImportType) {
    setImportType(type);
    setImportError(null);
    setImportResult(null);
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
          <h2 id="url-import-heading">{importType === "url" ? "网页导入" : "PDF 导入"}</h2>
        </div>
        <div className="import-workspace">
          <fieldset className="import-type-control">
            <legend>材料类型</legend>
            <div className="import-mode-options">
              <label className="import-mode-option">
                <input
                  type="radio"
                  name="import-type"
                  value="url"
                  checked={importType === "url"}
                  disabled={importing}
                  onChange={() => selectImportType("url")}
                />
                <span>网页</span>
              </label>
              <label className="import-mode-option">
                <input
                  type="radio"
                  name="import-type"
                  value="pdf"
                  checked={importType === "pdf"}
                  disabled={importing}
                  onChange={() => selectImportType("pdf")}
                />
                <span>文本型 PDF</span>
              </label>
            </div>
          </fieldset>
          {importType === "url" ? (
            <form className="url-import-form" onSubmit={handleUrlImport}>
              <fieldset className="import-mode-control">
                <legend>读取方式</legend>
                <div className="import-mode-options">
                  <label className="import-mode-option">
                    <input
                      type="radio"
                      name="import-mode"
                      value="auto"
                      checked={importMode === "auto"}
                      disabled={importing}
                      onChange={() => setImportMode("auto")}
                    />
                    <span>公开网页</span>
                  </label>
                  <label className="import-mode-option">
                    <input
                      type="radio"
                      name="import-mode"
                      value="chrome"
                      checked={importMode === "chrome"}
                      disabled={importing}
                      onChange={() => setImportMode("chrome")}
                    />
                    <span>已登录 Chrome</span>
                  </label>
                </div>
              </fieldset>
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
                  {importing ? "导入中" : importMode === "chrome" ? "从 Chrome 导入" : "导入"}
                </button>
              </div>
              <ImportFeedback error={importError} result={importResult} />
            </form>
          ) : (
            <form className="url-import-form" onSubmit={handlePdfImport}>
              <label htmlFor="pdf-input">文本型 PDF 文件</label>
              <div className="url-import-row">
                <input
                  ref={pdfInputRef}
                  id="pdf-input"
                  type="file"
                  accept="application/pdf,.pdf"
                  disabled={importing}
                  onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)}
                />
                <button type="submit" disabled={importing}>
                  {importing ? "导入中" : "导入 PDF"}
                </button>
              </div>
              <p className="import-hint">仅支持包含可提取文字的 PDF，不支持扫描版 OCR。</p>
              <ImportFeedback error={importError} result={importResult} />
            </form>
          )}
        </div>
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
            <button
              className="state-action"
              type="button"
              onClick={() => setShelfReloadKey((current) => current + 1)}
            >
              重试读取
            </button>
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
            <p>在上方输入网页 URL，公开页面直接导入；需要登录权限的页面可选择已登录 Chrome。</p>
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

function ImportFeedback({
  error,
  result,
}: {
  error: string | null;
  result: MaterialImportResult | null;
}) {
  if (error) {
    return (
      <p className="import-feedback import-feedback-error" role="alert">
        {error}
      </p>
    );
  }
  if (result) {
    return (
      <p className="import-feedback" aria-live="polite">
        {importMessage(result.outcome, result.material.title)}{" "}
        <Link className="import-feedback-link" to={`/materials/${result.material.id}`}>
          打开阅读页
        </Link>
      </p>
    );
  }
  return null;
}

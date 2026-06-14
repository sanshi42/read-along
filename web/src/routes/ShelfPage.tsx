import {
  BookOpenText,
  ChevronDown,
  FileText,
  Globe2,
  Import,
  LoaderCircle,
  LockKeyhole,
} from "lucide-react";
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
  return material.primary_source.source_type === "pdf" ? "文本型 PDF" : "网页";
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

function playbackPercentage(material: MaterialSummary) {
  if (!material.playback_position || !material.progress) {
    return null;
  }
  if (material.progress.playback_completed) {
    return 100;
  }
  const { sentence_index: index, sentence_count: count } = material.playback_position;
  if (count <= 1) {
    return 0;
  }
  return Math.round(((index - 1) / (count - 1)) * 100);
}

function materialActionLabel(material: MaterialSummary) {
  if (material.progress?.playback_completed) {
    return "再次阅读";
  }
  return material.progress ? "继续阅读" : "开始阅读";
}

export function ShelfPage() {
  const [materials, setMaterials] = useState<MaterialSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shelfReloadKey, setShelfReloadKey] = useState(0);
  const [showImport, setShowImport] = useState<boolean | null>(null);
  const [importType, setImportType] = useState<ImportType>("url");
  const [url, setUrl] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [importMode, setImportMode] = useState<UrlImportMode>("auto");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<MaterialImportResult | null>(null);
  const pdfInputRef = useRef<HTMLInputElement | null>(null);
  const importExpanded = showImport ?? false;

  useEffect(() => {
    let active = true;
    setError(null);
    listMaterials()
      .then((items) => {
        if (active) {
          setMaterials(items);
          setShowImport((current) => current ?? items.length === 0);
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
    setShowImport(true);
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
    <main className="page-shell shelf-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <BookOpenText aria-hidden="true" />
          <div>
            <p className="eyebrow">本地阅读空间</p>
            <h1>Read Along</h1>
          </div>
        </div>
        <div className="app-header-actions">
          <span className="local-status">
            <LockKeyhole aria-hidden="true" />
            仅保存在本机
          </span>
          <button
            className="button button-primary"
            type="button"
            aria-expanded={importExpanded}
            aria-controls="import-panel"
            onClick={() => setShowImport((current) => !current)}
          >
            <Import aria-hidden="true" />
            导入材料
            <ChevronDown
              aria-hidden="true"
              className={importExpanded ? "chevron chevron-open" : "chevron"}
            />
          </button>
        </div>
      </header>

      <section
        id="import-panel"
        className={importExpanded ? "import-panel import-panel-open" : "import-panel"}
        aria-hidden={!importExpanded}
        inert={!importExpanded}
      >
        <div className="import-panel-inner">
          <div className="section-heading import-heading">
            <div>
              <p className="eyebrow">添加到材料库</p>
              <h2>{importType === "url" ? "导入网页" : "导入文本型 PDF"}</h2>
            </div>
            <fieldset className="segmented-control">
              <legend className="visually-hidden">材料类型</legend>
              <label>
                <input
                  type="radio"
                  name="import-type"
                  value="url"
                  checked={importType === "url"}
                  disabled={importing || !importExpanded}
                  onChange={() => selectImportType("url")}
                />
                <Globe2 aria-hidden="true" />
                <span>网页</span>
              </label>
              <label>
                <input
                  type="radio"
                  name="import-type"
                  value="pdf"
                  checked={importType === "pdf"}
                  disabled={importing || !importExpanded}
                  onChange={() => selectImportType("pdf")}
                />
                <FileText aria-hidden="true" />
                <span>PDF</span>
              </label>
            </fieldset>
          </div>

          {importType === "url" ? (
            <form className="import-form" onSubmit={handleUrlImport}>
              <fieldset className="form-field">
                <legend>读取方式</legend>
                <div className="choice-row">
                  <label>
                    <input
                      type="radio"
                      name="import-mode"
                      value="auto"
                      checked={importMode === "auto"}
                      disabled={importing || !importExpanded}
                      onChange={() => setImportMode("auto")}
                    />
                    <span>公开网页</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="import-mode"
                      value="chrome"
                      checked={importMode === "chrome"}
                      disabled={importing || !importExpanded}
                      onChange={() => setImportMode("chrome")}
                    />
                    <span>已登录 Chrome</span>
                  </label>
                </div>
              </fieldset>
              <label className="form-field" htmlFor="url-input">
                <span>网页 URL</span>
                <span className="input-action-row">
                  <input
                    id="url-input"
                    type="url"
                    inputMode="url"
                    placeholder="https://example.com/article"
                    value={url}
                    disabled={importing || !importExpanded}
                    onChange={(event) => setUrl(event.target.value)}
                  />
                  <button
                    className="button button-primary"
                    type="submit"
                    disabled={importing || !importExpanded}
                  >
                    {importing ? <LoaderCircle aria-hidden="true" className="spin" /> : null}
                    {importing ? "导入中" : importMode === "chrome" ? "从 Chrome 导入" : "导入网页"}
                  </button>
                </span>
              </label>
              <ImportFeedback error={importError} result={importResult} />
            </form>
          ) : (
            <form className="import-form" onSubmit={handlePdfImport}>
              <label className="form-field" htmlFor="pdf-input">
                <span>文本型 PDF 文件</span>
                <span className="input-action-row">
                  <input
                    ref={pdfInputRef}
                    id="pdf-input"
                    type="file"
                    accept="application/pdf,.pdf"
                    disabled={importing || !importExpanded}
                    onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)}
                  />
                  <button
                    className="button button-primary"
                    type="submit"
                    disabled={importing || !importExpanded}
                  >
                    {importing ? <LoaderCircle aria-hidden="true" className="spin" /> : null}
                    {importing ? "导入中" : "导入 PDF"}
                  </button>
                </span>
              </label>
              <p className="form-hint">仅支持包含可提取文字的 PDF，不支持扫描版 OCR。</p>
              <ImportFeedback error={importError} result={importResult} />
            </form>
          )}
        </div>
      </section>

      <section className="shelf-section" aria-labelledby="shelf-heading">
        <div className="section-heading shelf-heading">
          <div>
            <p className="eyebrow">材料库</p>
            <h2 id="shelf-heading">继续阅读</h2>
          </div>
          {materials && materials.length > 0 ? <span>{materials.length} 篇阅读材料</span> : null}
        </div>

        {error ? (
          <section className="state-panel" role="alert">
            <BookOpenText aria-hidden="true" className="state-icon" />
            <p className="eyebrow">连接失败</p>
            <h2>暂时无法读取材料库</h2>
            <p>{error}</p>
            <p className="state-hint">请确认本地 Read Along 后端已启动，然后重试。</p>
            <button
              className="button button-primary"
              type="button"
              onClick={() => setShelfReloadKey((current) => current + 1)}
            >
              重试读取
            </button>
          </section>
        ) : null}

        {!error && materials === null ? <ShelfSkeleton /> : null}

        {!error && materials?.length === 0 ? (
          <section className="state-panel state-panel-centered">
            <BookOpenText aria-hidden="true" className="state-icon" />
            <p className="eyebrow">材料库还是空的</p>
            <h2>导入第一篇阅读材料</h2>
            <p>添加一篇网页或文本型 PDF，之后可以从任意一句继续朗读。</p>
          </section>
        ) : null}

        {!error && materials && materials.length > 0 ? (
          <div className="material-list">
            {materials.map((material) => (
              <MaterialRow key={material.id} material={material} />
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}

function MaterialRow({ material }: { material: MaterialSummary }) {
  const percentage = playbackPercentage(material);
  const position = material.playback_position;
  const completed = material.progress?.playback_completed ?? false;
  return (
    <Link className="material-row" to={`/materials/${material.id}`}>
      <div className="material-source-icon" aria-hidden="true">
        {material.primary_source.source_type === "pdf" ? <FileText /> : <Globe2 />}
      </div>
      <div className="material-row-main">
        <div className="material-row-meta">
          <span>{sourceLabel(material)}</span>
          <span aria-hidden="true">·</span>
          <time dateTime={material.updated_at}>{dateFormatter.format(new Date(material.updated_at))}</time>
        </div>
        <h3>{material.title}</h3>
        <p className="source-uri">{material.primary_source.source_uri}</p>
        {percentage !== null && position ? (
          <div className="playback-position">
            <span className="position-track" aria-hidden="true">
              <span style={{ width: `${percentage}%` }} />
            </span>
            <span>
              {completed
                ? "朗读完成"
                : `朗读位置 ${percentage}% · 第 ${position.sentence_index} / ${position.sentence_count} 句`}
            </span>
          </div>
        ) : (
          <p className="material-new">尚未开始朗读</p>
        )}
      </div>
      <span className="material-row-action">{materialActionLabel(material)}</span>
    </Link>
  );
}

function ShelfSkeleton() {
  return (
    <div className="material-list" aria-live="polite" aria-label="正在读取材料库">
      {[1, 2, 3].map((item) => (
        <div className="material-row skeleton-row" key={item} aria-hidden="true">
          <span className="skeleton-block skeleton-icon" />
          <span className="material-row-main">
            <span className="skeleton-block skeleton-meta" />
            <span className="skeleton-block skeleton-title" />
            <span className="skeleton-block skeleton-text" />
          </span>
        </div>
      ))}
    </div>
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
      <p className="feedback feedback-error" role="alert">
        {error}
      </p>
    );
  }
  if (result) {
    return (
      <p className="feedback feedback-success" aria-live="polite">
        {importMessage(result.outcome, result.material.title)}{" "}
        <Link to={`/materials/${result.material.id}`}>打开阅读页</Link>
      </p>
    );
  }
  return null;
}

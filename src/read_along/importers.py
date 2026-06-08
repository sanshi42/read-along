from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from read_along.browser import BrowserExtractionError, BrowserPageText, extract_front_chrome_text, extract_page_text
from read_along.extractors import pdf_page_texts, structure_text
from read_along.material_library import MaterialLibrary
from read_along.models import (
    MaterialDetail,
    ReadingMaterialDraft,
    ReadingMaterialDraftParagraph,
    SourceType,
)
from read_along.sources import dedao

_CONTENT_SELECTORS = (
    ".prose",
    "[class*='prose']",
    "[data-pagefind-body]",
    "[data-mdx-content]",
    ".markdown",
    ".markdown-body",
    ".mdx-content",
    ".docs-content",
    ".article-content",
    ".entry-content",
    ".post-content",
)

_ARTICLE_SELECTORS = (
    "article",
    "main",
    '[role="main"]',
    ".article",
    ".content",
    "#article",
    "#content",
)


@dataclass(frozen=True)
class WebPageContent:
    title: str
    url: str
    text: str


class UrlImportError(RuntimeError):
    """网页导入失败。"""


def import_pdf(
    *,
    file_path: Path,
    filename: str,
    library: MaterialLibrary,
) -> MaterialDetail:
    """将文本型 PDF 提取为 Draft，并保存到材料库。"""
    paragraphs: list[ReadingMaterialDraftParagraph] = []
    for page_number, page_text in pdf_page_texts(str(file_path)):
        for block_number, sentences in enumerate(structure_text(page_text), start=1):
            paragraphs.append(
                ReadingMaterialDraftParagraph(
                    text=" ".join(sentences),
                    source_label=f"第 {page_number} 页，第 {block_number} 段",
                    sentences=sentences,
                )
            )

    return library.save(
        ReadingMaterialDraft(
            source_type=SourceType.PDF,
            source_uri=filename,
            title=filename,
            source_file=file_path,
            paragraphs=paragraphs,
        )
    )


def import_url(
    *,
    url: str,
    library: MaterialLibrary,
    mode: str = "auto",
) -> MaterialDetail:
    """将网页 URL 抽取为 Draft，并保存到材料库。"""
    _validate_url(url)
    normalized_mode = mode.lower()
    if normalized_mode == "auto":
        page = fetch_webpage(url)
    elif normalized_mode == "chrome":
        page = fetch_chrome_page(url)
    else:
        raise UrlImportError(f"不支持的网页导入模式：{mode}。")

    paragraphs = _draft_paragraphs(page.text, source_uri=page.url)
    if not paragraphs:
        if normalized_mode == "auto" and dedao.supports_url(page.url):
            raise UrlImportError("得到页面 URL 直抓未返回正文，可能需要登录态或动态渲染。")
        raise UrlImportError("网页正文为空或无法抽取。")

    return library.save(
        ReadingMaterialDraft(
            source_type=SourceType.URL,
            source_uri=page.url,
            title=page.title or page.url,
            paragraphs=paragraphs,
        )
    )


def fetch_chrome_page(url: str) -> WebPageContent:
    """从专用 Chrome DevTools 会话读取匹配 URL 的页面正文。"""
    page = _extract_chrome_page(url)

    text = _clean_chrome_text(
        requested_url=url,
        page_url=page.url,
        text=page.text,
    )
    if not text:
        raise UrlImportError("Chrome 页面正文为空或无法抽取。")

    return WebPageContent(
        title=page.title or url,
        url=page.url or url,
        text=text,
    )


def fetch_webpage(url: str) -> WebPageContent:
    """使用 Scrapling 抓取公开网页并抽取标题和正文。"""
    try:
        from scrapling.fetchers import Fetcher
    except ImportError as exc:
        raise UrlImportError("当前环境缺少网页抓取依赖，无法导入网页。") from exc

    try:
        page = Fetcher.get(url, stealthy_headers=True, timeout=15)
    except Exception as exc:
        raise UrlImportError("网页无法访问或不支持直接抓取。") from exc

    status = getattr(page, "status", 200)
    if isinstance(status, int) and status >= 400:
        raise UrlImportError(f"网页无法访问（HTTP {status}）。")

    text = _extract_main_text(page)
    if not text:
        if dedao.supports_url(url):
            raise UrlImportError("得到页面 URL 直抓未返回正文，可能需要登录态或动态渲染。")
        raise UrlImportError("网页正文为空或无法抽取。")

    return WebPageContent(
        title=_extract_title(page, fallback=url),
        url=str(getattr(page, "url", url) or url),
        text=text,
    )


def _validate_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise UrlImportError("请输入有效的 HTTP 或 HTTPS URL。") from exc

    if parsed.scheme.lower() not in {"http", "https"} or parsed.hostname is None:
        raise UrlImportError("请输入有效的 HTTP 或 HTTPS URL。")
    if parsed.username is not None or parsed.password is not None:
        raise UrlImportError("URL 不得包含用户名或密码。")


def _chrome_tab_filter(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    filter_text = f"{parsed.netloc}{path}"
    if parsed.query:
        filter_text = f"{filter_text}?{parsed.query}"
    return filter_text


def _chrome_tab_filters(url: str) -> list[str]:
    exact = _chrome_tab_filter(url)
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    without_query = f"{parsed.netloc}{path}"
    return list(dict.fromkeys([exact, without_query]))


def _extract_chrome_page(url: str) -> BrowserPageText:
    errors: list[str] = []
    for url_filter in _chrome_tab_filters(url):
        try:
            return extract_page_text(url_contains=url_filter)
        except BrowserExtractionError as exc:
            errors.append(str(exc))

    try:
        page = extract_front_chrome_text()
    except BrowserExtractionError as exc:
        errors.append(str(exc))
        raise UrlImportError(_chrome_error_message(errors)) from exc

    if not _chrome_page_matches(url, page.url):
        raise UrlImportError(
            "Chrome 前台标签页不是请求的网页。"
            f"当前页面：{page.url or '未知'}。请切到目标页面后重试。"
        )
    return page


def _chrome_page_matches(requested_url: str, page_url: str) -> bool:
    if not page_url:
        return False
    requested = urlsplit(requested_url)
    page = urlsplit(page_url)
    requested_host = requested.hostname or ""
    page_host = page.hostname or ""
    requested_path = requested.path.rstrip("/") or "/"
    page_path = page.path.rstrip("/") or "/"
    return requested_host.lower() == page_host.lower() and requested_path == page_path


def _chrome_error_message(errors: list[str]) -> str:
    unique_errors = list(dict.fromkeys(error for error in errors if error.strip()))
    if not unique_errors:
        return "Chrome 页面读取失败。"
    return "Chrome 页面读取失败：" + "；".join(unique_errors)


def _clean_chrome_text(*, requested_url: str, page_url: str, text: str) -> str:
    if dedao.supports_url(requested_url) or dedao.supports_url(page_url):
        return dedao.clean_text(text)
    return normalize_web_text(text)


def _draft_paragraphs(
    text: str,
    *,
    source_uri: str,
) -> list[ReadingMaterialDraftParagraph]:
    if dedao.supports_url(source_uri):
        text = dedao.clean_text(text)

    paragraphs: list[ReadingMaterialDraftParagraph] = []
    for block_number, sentences in enumerate(structure_text(text), start=1):
        if not sentences:
            continue
        paragraphs.append(
            ReadingMaterialDraftParagraph(
                text=" ".join(sentences),
                source_label=f"网页正文，第 {block_number} 段",
                sentences=sentences,
            )
        )
    return paragraphs


def _extract_title(page: Any, *, fallback: str) -> str:
    for selector in ("h1", "title"):
        text = _first_selector_text(page, selector)
        if text:
            return text
    title = getattr(page, "title", "")
    if isinstance(title, str) and title.strip():
        return normalize_web_text(title)
    return fallback


def _extract_main_text(page: Any) -> str:
    preferred_candidates = _selector_text_candidates(page, _CONTENT_SELECTORS)
    if preferred_candidates:
        return max(preferred_candidates, key=len)

    candidates = _selector_text_candidates(page, _ARTICLE_SELECTORS)
    if candidates:
        return max(candidates, key=len)
    return _node_text(page)


def _selector_text_candidates(page: Any, selectors: tuple[str, ...]) -> list[str]:
    candidates: list[str] = []
    for selector in selectors:
        for node in _css_nodes(page, selector):
            text = _node_text(node)
            if text and len(text) >= 40:
                candidates.append(text)
    return candidates


def _first_selector_text(page: Any, selector: str) -> str:
    for node in _css_nodes(page, selector):
        text = _node_text(node)
        if text:
            return text.split("\n", 1)[0].strip()
    return ""


def _css_nodes(node: Any, selector: str) -> list[Any]:
    css = getattr(node, "css", None)
    if not callable(css):
        return []
    result = css(selector)
    if result is None:
        return []
    if isinstance(result, list):
        return result
    try:
        return list(result)
    except TypeError:
        return [result]


def _node_text(node: Any) -> str:
    get_all_text = getattr(node, "get_all_text", None)
    if callable(get_all_text):
        try:
            return normalize_web_text(get_all_text(ignore_tags=("script", "style", "noscript")))
        except TypeError:
            return normalize_web_text(get_all_text())

    text = getattr(node, "text", "")
    if callable(text):
        text = text()
    return normalize_web_text(str(text or ""))


def normalize_web_text(text: str) -> str:
    """规范化网页抽取文本，保留空行作为段落边界。"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    previous = ""
    for raw_line in normalized.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", raw_line).strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            previous = ""
            continue
        if line == previous:
            continue
        lines.append(line)
        previous = line

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)

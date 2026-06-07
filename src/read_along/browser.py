from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from websocket import create_connection


DEFAULT_DEBUG_URL = "http://127.0.0.1:9222"

GENERIC_NOISE_LINE_PATTERNS = [
    r"^返回$",
    r"^分享$",
    r"^评论$",
    r"^下载$",
    r"^复制链接$",
    r"^登录$",
    r"^注册$",
    r"^客服$",
    r"^Copyright\b",
]

EXTRACT_PAGE_SCRIPT = r"""
(() => {
  const selectors = [
    'article',
    'main',
    '[role="main"]',
    '[class*="article"]',
    '[class*="lesson"]',
    '[class*="content"]',
    '[class*="detail"]'
  ];

  function isVisible(node) {
    if (!node || !(node instanceof Element)) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false;
    }
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function textOf(node) {
    return (node && node.innerText ? node.innerText : '').trim();
  }

  const candidates = [];
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      if (!isVisible(node)) continue;
      const text = textOf(node);
      if (text.length < 80) continue;
      candidates.push({ selector, text, length: text.length });
    }
  }

  const bodyText = textOf(document.body);
  candidates.sort((a, b) => b.length - a.length);
  const best = candidates[0] || { selector: 'body', text: bodyText, length: bodyText.length };

  const title =
    textOf(document.querySelector('h1')) ||
    document.title ||
    '';

  return JSON.stringify({
    title,
    url: location.href,
    selector: best.selector,
    text: best.text
  });
})()
""".strip()

CHROME_JXA_SCRIPT = """
function run(argv) {
  const jsCode = argv[0];
  const chrome = Application('Google Chrome');
  if (chrome.windows.length === 0) {
    throw new Error('没有已打开的 Chrome 窗口。');
  }
  const tab = chrome.windows[0].activeTab;
  return tab.execute({ javascript: jsCode });
}
""".strip()


@dataclass(frozen=True)
class BrowserTab:
    title: str
    url: str
    websocket_url: str


@dataclass(frozen=True)
class BrowserPageText:
    title: str
    url: str
    selector: str
    text: str


class BrowserExtractionError(RuntimeError):
    pass


def fetch_tabs(debug_url: str = DEFAULT_DEBUG_URL, timeout: float = 5.0) -> list[BrowserTab]:
    endpoint = f"{debug_url.rstrip('/')}/json/list"
    request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise BrowserExtractionError(
            f"无法连接 Chrome DevTools：{endpoint}。"
            "请先使用 --remote-debugging-port 启动 Chrome。"
            f"原始错误：{exc}"
        ) from exc

    if not isinstance(payload, list):
        raise BrowserExtractionError("Chrome DevTools 返回了非预期的标签页列表。")

    tabs: list[BrowserTab] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "page":
            continue
        websocket_url = str(item.get("webSocketDebuggerUrl") or "")
        url = str(item.get("url") or "")
        if not websocket_url or url.startswith(("devtools://", "chrome://")):
            continue
        tabs.append(
            BrowserTab(
                title=str(item.get("title") or ""),
                url=url,
                websocket_url=websocket_url,
            )
        )
    return tabs


def select_tab(
    tabs: list[BrowserTab],
    url_contains: str | None = None,
    title_contains: str | None = None,
) -> BrowserTab:
    candidates = tabs
    if url_contains:
        candidates = [tab for tab in candidates if url_contains in tab.url]
    if title_contains:
        candidates = [tab for tab in candidates if title_contains in tab.title]

    if not candidates:
        available = "\n".join(f"- {tab.title} | {tab.url}" for tab in tabs[:10]) or "- 没有页面标签页"
        raise BrowserExtractionError(
            "没有 Chrome 标签页符合指定筛选条件。\n"
            f"可用标签页：\n{available}"
        )
    if len(candidates) > 1:
        available = "\n".join(f"- {tab.title} | {tab.url}" for tab in candidates[:10])
        raise BrowserExtractionError(
            "有多个 Chrome 标签页符合条件。请添加 --tab-title-contains 或缩小 --tab-url-contains 的范围。\n"
            f"匹配的标签页：\n{available}"
        )
    return candidates[0]


def evaluate_runtime_expression(tab: BrowserTab, expression: str, timeout: float = 10.0) -> Any:
    request_id = 1
    websocket = create_connection(
        tab.websocket_url,
        timeout=timeout,
        origin=devtools_origin(tab.websocket_url),
    )
    try:
        websocket.send(
            json.dumps(
                {
                    "id": request_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                }
            )
        )
        while True:
            message = json.loads(websocket.recv())
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise BrowserExtractionError(f"Chrome Runtime.evaluate 失败：{message['error']}")
            result = message.get("result", {})
            if "exceptionDetails" in result:
                raise BrowserExtractionError("Chrome 页面脚本抛出了异常。")
            return result.get("result", {}).get("value")
    finally:
        websocket.close()


def extract_page_text(
    debug_url: str = DEFAULT_DEBUG_URL,
    url_contains: str | None = None,
    title_contains: str | None = None,
    timeout: float = 10.0,
) -> BrowserPageText:
    tab = select_tab(
        fetch_tabs(debug_url=debug_url, timeout=timeout),
        url_contains=url_contains,
        title_contains=title_contains,
    )
    raw_value = evaluate_runtime_expression(tab, EXTRACT_PAGE_SCRIPT, timeout=timeout)
    if not isinstance(raw_value, str):
        raise BrowserExtractionError("Chrome 页面提取返回了非字符串结果。")

    return page_text_from_payload(raw_value, fallback_title=tab.title, fallback_url=tab.url)


def extract_front_chrome_text(timeout: float = 10.0) -> BrowserPageText:
    try:
        completed = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", CHROME_JXA_SCRIPT, EXTRACT_PAGE_SCRIPT],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise BrowserExtractionError("当前系统无法使用 osascript。") from exc
    except subprocess.TimeoutExpired as exc:
        raise BrowserExtractionError("读取 Chrome 前台标签页超时。") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip()
        if "not allowed" in message.lower() or "javascript" in message.lower():
            message += (
                "\n请启用 Chrome 的“查看 > 开发者 > 允许来自 Apple 事件的 JavaScript”，"
                "然后重新运行命令。"
            )
        raise BrowserExtractionError(f"无法读取 Chrome 前台标签页：{message}") from exc

    return page_text_from_payload(completed.stdout.strip())


def page_text_from_payload(
    raw_value: str,
    fallback_title: str = "浏览器页面",
    fallback_url: str = "",
) -> BrowserPageText:
    payload = json.loads(raw_value)
    text = clean_browser_text(str(payload.get("text") or ""))
    if not text:
        raise BrowserExtractionError("所选标签页没有提供可读取的可见文本。")
    return BrowserPageText(
        title=str(payload.get("title") or fallback_title or "浏览器页面").strip(),
        url=str(payload.get("url") or fallback_url),
        selector=str(payload.get("selector") or "unknown"),
        text=text,
    )


def clean_browser_text(
    text: str,
    noise_line_patterns: list[str] | None = None,
) -> str:
    patterns = noise_line_patterns or GENERIC_NOISE_LINE_PATTERNS
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    previous = ""
    for raw_line in normalized.split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        if line == previous:
            continue
        if is_noise_line(line, patterns):
            continue
        lines.append(line)
        previous = line

    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def is_noise_line(line: str, patterns: list[str] | None = None) -> bool:
    return any(
        re.search(pattern, line, flags=re.IGNORECASE)
        for pattern in (patterns or GENERIC_NOISE_LINE_PATTERNS)
    )


def devtools_origin(websocket_url: str) -> str:
    parsed = urllib.parse.urlparse(websocket_url)
    scheme = "https" if parsed.scheme == "wss" else "http"
    return f"{scheme}://{parsed.netloc}"

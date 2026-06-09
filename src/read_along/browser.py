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

DEFAULT_DEBUG_URL = 'http://127.0.0.1:9222'

GENERIC_NOISE_LINE_PATTERNS = [
    r'^返回$',
    r'^分享$',
    r'^评论$',
    r'^下载$',
    r'^复制链接$',
    r'^登录$',
    r'^注册$',
    r'^客服$',
    r'^Copyright\b',
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

CHROME_JXA_URL_FILTER_SCRIPT = """
function run(argv) {
  const jsCode = argv[0];
  const filters = JSON.parse(argv[1] || '[]');
  const chrome = Application('Google Chrome');
  if (chrome.windows.length === 0) {
    throw new Error('没有已打开的 Chrome 窗口。');
  }

  function valueOf(property) {
    try {
      return property();
    } catch (error) {
      return property;
    }
  }

  const availableTabs = [];
  for (let windowIndex = 0; windowIndex < chrome.windows.length; windowIndex += 1) {
    const tabs = chrome.windows[windowIndex].tabs;
    for (let tabIndex = 0; tabIndex < tabs.length; tabIndex += 1) {
      const tab = tabs[tabIndex];
      const url = String(valueOf(tab.url) || '');
      const title = String(valueOf(tab.title) || '');
      if (!url || url.startsWith('chrome://') || url.startsWith('devtools://')) {
        continue;
      }
      availableTabs.push({ title, url, tab });
    }
  }

  for (const filter of filters) {
    const candidates = availableTabs.filter((item) => item.url.includes(filter));
    if (candidates.length === 1) {
      return candidates[0].tab.execute({ javascript: jsCode });
    }
    if (candidates.length > 1) {
      const matched = candidates
        .slice(0, 10)
        .map((item) => `- ${item.title} | ${item.url}`)
        .join('\\n');
      throw new Error(`有多个 Chrome 标签页符合目标 URL。请关闭重复目标页后重试。\\n匹配的标签页：\\n${matched}`);
    }
  }

  const available = availableTabs
    .slice(0, 10)
    .map((item) => `- ${item.title} | ${item.url}`)
    .join('\\n') || '- 没有页面标签页';
  throw new Error(
    '没有 Chrome 标签页符合目标 URL。请先在 Chrome 打开目标页面，再回到 Read Along 点击导入。' +
    `\\n可用标签页：\\n${available}`
  );
}
""".strip()


@dataclass(frozen=True)
class BrowserTab:
    """Chrome DevTools 标签页描述。"""

    title: str
    url: str
    websocket_url: str


@dataclass(frozen=True)
class BrowserPageText:
    """从浏览器页面抽取出的可见正文。"""

    title: str
    url: str
    selector: str
    text: str


class BrowserExtractionError(RuntimeError):
    """浏览器页面正文抽取失败。"""

    pass


def fetch_tabs(debug_url: str = DEFAULT_DEBUG_URL, timeout: float = 5.0) -> list[BrowserTab]:
    """从 Chrome DevTools 获取可用页面标签页。"""
    endpoint = f'{debug_url.rstrip("/")}/json/list'
    request = urllib.request.Request(endpoint, headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as exc:
        raise BrowserExtractionError(
            f'无法连接 Chrome DevTools：{endpoint}。请先使用 --remote-debugging-port 启动 Chrome。原始错误：{exc}'
        ) from exc

    if not isinstance(payload, list):
        raise BrowserExtractionError('Chrome DevTools 返回了非预期的标签页列表。')

    tabs: list[BrowserTab] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get('type') != 'page':
            continue
        websocket_url = str(item.get('webSocketDebuggerUrl') or '')
        url = str(item.get('url') or '')
        if not websocket_url or url.startswith(('devtools://', 'chrome://')):
            continue
        tabs.append(
            BrowserTab(
                title=str(item.get('title') or ''),
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
    """根据 URL 或标题筛选唯一标签页。"""
    candidates = tabs
    if url_contains:
        candidates = [tab for tab in candidates if url_contains in tab.url]
    if title_contains:
        candidates = [tab for tab in candidates if title_contains in tab.title]

    if not candidates:
        available = '\n'.join(f'- {tab.title} | {tab.url}' for tab in tabs[:10]) or '- 没有页面标签页'
        raise BrowserExtractionError(f'没有 Chrome 标签页符合指定筛选条件。\n可用标签页：\n{available}')
    if len(candidates) > 1:
        available = '\n'.join(f'- {tab.title} | {tab.url}' for tab in candidates[:10])
        raise BrowserExtractionError(
            '有多个 Chrome 标签页符合条件。请添加 --tab-title-contains 或缩小 --tab-url-contains 的范围。\n'
            f'匹配的标签页：\n{available}'
        )
    return candidates[0]


def evaluate_runtime_expression(tab: BrowserTab, expression: str, timeout: float = 10.0) -> Any:
    """在指定 Chrome 标签页中执行 Runtime.evaluate。"""
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
                    'id': request_id,
                    'method': 'Runtime.evaluate',
                    'params': {
                        'expression': expression,
                        'awaitPromise': True,
                        'returnByValue': True,
                    },
                }
            )
        )
        while True:
            message = json.loads(websocket.recv())
            if message.get('id') != request_id:
                continue
            if 'error' in message:
                raise BrowserExtractionError(f'Chrome Runtime.evaluate 失败：{message["error"]}')
            result = message.get('result', {})
            if 'exceptionDetails' in result:
                raise BrowserExtractionError('Chrome 页面脚本抛出了异常。')
            return result.get('result', {}).get('value')
    finally:
        websocket.close()


def extract_page_text(
    debug_url: str = DEFAULT_DEBUG_URL,
    url_contains: str | None = None,
    title_contains: str | None = None,
    timeout: float = 10.0,
) -> BrowserPageText:
    """通过 Chrome DevTools 抽取匹配页面的可见正文。"""
    tab = select_tab(
        fetch_tabs(debug_url=debug_url, timeout=timeout),
        url_contains=url_contains,
        title_contains=title_contains,
    )
    raw_value = evaluate_runtime_expression(tab, EXTRACT_PAGE_SCRIPT, timeout=timeout)
    if not isinstance(raw_value, str):
        raise BrowserExtractionError('Chrome 页面提取返回了非字符串结果。')

    return page_text_from_payload(raw_value, fallback_title=tab.title, fallback_url=tab.url)


def extract_front_chrome_text(timeout: float = 10.0) -> BrowserPageText:
    """通过 AppleScript 读取 Chrome 前台标签页正文。"""
    return _extract_chrome_text_with_jxa(
        script=CHROME_JXA_SCRIPT,
        args=[EXTRACT_PAGE_SCRIPT],
        timeout=timeout,
        action='读取 Chrome 前台标签页',
    )


def extract_chrome_text_by_url_filters(
    url_filters: list[str],
    timeout: float = 10.0,
) -> BrowserPageText:
    """通过 AppleScript 在所有 Chrome 标签页中查找匹配 URL 的页面正文。"""
    filters = [item for item in url_filters if item]
    if not filters:
        raise BrowserExtractionError('缺少目标 URL 筛选条件。')

    return _extract_chrome_text_with_jxa(
        script=CHROME_JXA_URL_FILTER_SCRIPT,
        args=[EXTRACT_PAGE_SCRIPT, json.dumps(filters, ensure_ascii=False)],
        timeout=timeout,
        action='查找 Chrome 目标标签页',
    )


def _extract_chrome_text_with_jxa(
    *,
    script: str,
    args: list[str],
    timeout: float,
    action: str,
) -> BrowserPageText:
    try:
        completed = subprocess.run(
            ['osascript', '-l', 'JavaScript', '-e', script, *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise BrowserExtractionError('当前系统无法使用 osascript。') from exc
    except subprocess.TimeoutExpired as exc:
        raise BrowserExtractionError(f'{action}超时。') from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or '').strip()
        if 'not allowed' in message.lower() or 'javascript' in message.lower():
            message += '\n请启用 Chrome 的“查看 > 开发者 > 允许来自 Apple 事件的 JavaScript”，然后重新运行命令。'
        raise BrowserExtractionError(f'无法{action}：{message}') from exc

    return page_text_from_payload(completed.stdout.strip())


def page_text_from_payload(
    raw_value: str,
    fallback_title: str = '浏览器页面',
    fallback_url: str = '',
) -> BrowserPageText:
    """将页面脚本返回的 JSON 文本转换为正文对象。"""
    payload = json.loads(raw_value)
    text = clean_browser_text(str(payload.get('text') or ''))
    if not text:
        raise BrowserExtractionError('所选标签页没有提供可读取的可见文本。')
    return BrowserPageText(
        title=str(payload.get('title') or fallback_title or '浏览器页面').strip(),
        url=str(payload.get('url') or fallback_url),
        selector=str(payload.get('selector') or 'unknown'),
        text=text,
    )


def clean_browser_text(
    text: str,
    noise_line_patterns: list[str] | None = None,
) -> str:
    """清理浏览器可见文本中的重复行和噪声行。"""
    patterns = noise_line_patterns or GENERIC_NOISE_LINE_PATTERNS
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    lines: list[str] = []
    previous = ''
    for raw_line in normalized.split('\n'):
        line = re.sub(r'\s+', ' ', raw_line).strip()
        if not line:
            if lines and lines[-1]:
                lines.append('')
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
    return '\n'.join(lines)


def is_noise_line(line: str, patterns: list[str] | None = None) -> bool:
    """判断单行文本是否符合噪声模式。"""
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in (patterns or GENERIC_NOISE_LINE_PATTERNS))


def devtools_origin(websocket_url: str) -> str:
    """根据 DevTools WebSocket URL 生成 Origin。"""
    parsed = urllib.parse.urlparse(websocket_url)
    scheme = 'https' if parsed.scheme == 'wss' else 'http'
    return f'{scheme}://{parsed.netloc}'

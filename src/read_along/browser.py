from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

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

_EXTRACT_PAGE_SCRIPT_TEMPLATE = r"""
(() => {
  const preferredSelectors = __PREFERRED_SELECTORS__;
  const preferredTitleSelectors = __PREFERRED_TITLE_SELECTORS__;
  const fallbackSelectors = [
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

  function candidatesFor(selectors) {
    const candidates = [];
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) {
        if (!isVisible(node)) continue;
        const text = textOf(node);
        if (text.length < 80) continue;
        candidates.push({ selector, text, length: text.length });
      }
    }
    candidates.sort((a, b) => b.length - a.length);
    return candidates;
  }

  function firstText(selectors) {
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) {
        if (!isVisible(node)) continue;
        const text = textOf(node);
        if (text) return text;
      }
    }
    return '';
  }

  const preferredCandidates = candidatesFor(preferredSelectors);
  const fallbackCandidates = candidatesFor(fallbackSelectors);
  const candidates =
    preferredSelectors.length > 0 ? preferredCandidates : fallbackCandidates;
  const bodyText = textOf(document.body);
  const best =
    candidates[0] ||
    (preferredSelectors.length > 0
      ? { selector: preferredSelectors[0], text: '', length: 0 }
      : { selector: 'body', text: bodyText, length: bodyText.length });

  const preferredTitle = firstText(preferredTitleSelectors);
  const title = preferredTitleSelectors.length > 0
    ? preferredTitle
    : textOf(document.querySelector('h1')) || document.title || '';
  const ready = Boolean(
    best.text && (preferredTitleSelectors.length === 0 || preferredTitle)
  );

  return JSON.stringify({
    ready,
    title,
    url: location.href,
    selector: best.selector,
    text: best.text
  });
})()
""".strip()


def build_extract_page_script(
    preferred_selectors: tuple[str, ...] = (),
    *,
    preferred_title_selectors: tuple[str, ...] = (),
) -> str:
    """构建页面正文抽取脚本，可优先使用来源提供的正文容器。"""
    selectors = json.dumps(preferred_selectors, ensure_ascii=False)
    title_selectors = json.dumps(preferred_title_selectors, ensure_ascii=False)
    return _EXTRACT_PAGE_SCRIPT_TEMPLATE.replace('__PREFERRED_SELECTORS__', selectors).replace(
        '__PREFERRED_TITLE_SELECTORS__',
        title_selectors,
    )


CHROME_JXA_URL_SCRIPT = """
function run(argv) {
  const targetUrl = argv[0];
  const preferredSelectors = JSON.parse(argv[1] || '[]');
  const jsCode = argv[2];
  const chrome = Application('Google Chrome');
  if (chrome.windows.length === 0) {
    throw new Error('没有已打开的 Chrome 窗口。');
  }

  const window = chrome.windows[0];
  const tab = chrome.Tab({ url: targetUrl });
  window.tabs.push(tab);

  try {
    for (let attempt = 0; attempt < 100; attempt += 1) {
      delay(0.1);
      try {
        const rawValue = tab.execute({ javascript: jsCode });
        const payload = JSON.parse(rawValue || '{}');
        if (payload.url && payload.url !== 'about:blank' && payload.ready) {
          return rawValue;
        }
      } catch (error) {
        // 页面仍在导航或尚未允许执行脚本时继续等待。
      }
    }
    const selectors = preferredSelectors.length > 0 ? preferredSelectors.join(', ') : '通用正文容器';
    throw new Error(`等待目标页面正文超时（${selectors}）：${targetUrl}`);
  } finally {
    tab.close();
  }
}
""".strip()


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


def extract_chrome_url_text(
    url: str,
    *,
    preferred_selectors: tuple[str, ...] = (),
    preferred_title_selectors: tuple[str, ...] = (),
    timeout: float = 15.0,
) -> BrowserPageText:
    """在已登录 Chrome 会话中新建临时标签页，访问 URL 并抽取正文。"""
    return _extract_chrome_text_with_jxa(
        script=CHROME_JXA_URL_SCRIPT,
        args=[
            url,
            json.dumps(preferred_selectors, ensure_ascii=False),
            build_extract_page_script(
                preferred_selectors,
                preferred_title_selectors=preferred_title_selectors,
            ),
        ],
        timeout=timeout,
        action='在 Chrome 中打开并读取目标 URL',
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

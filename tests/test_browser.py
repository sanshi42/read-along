import json
import subprocess
import urllib.error

import pytest

from read_along import browser
from read_along.browser import (
    EXTRACT_PAGE_SCRIPT,
    BrowserExtractionError,
    BrowserTab,
    clean_browser_text,
    devtools_origin,
    extract_chrome_text_by_url_filters,
    fetch_tabs,
    page_text_from_payload,
    select_tab,
)


def test_extract_page_script_uses_body_only_as_fallback() -> None:
    assert "candidates.push({ selector: 'body'" not in EXTRACT_PAGE_SCRIPT
    assert "const best = candidates[0] || { selector: 'body'" in EXTRACT_PAGE_SCRIPT


def test_clean_browser_text_drops_repeated_generic_noise_lines() -> None:
    raw = """
第一段正文解释核心概念。
第一段正文解释核心概念。

分享
第二段正文给出应用场景。
"""

    cleaned = clean_browser_text(raw)

    assert '分享' not in cleaned
    assert cleaned.count('第一段正文解释核心概念。') == 1
    assert '第二段正文给出应用场景。' in cleaned


def test_select_tab_requires_narrow_match() -> None:
    tabs = [
        BrowserTab('课程 A', 'https://www.dedao.cn/course/a', 'ws://127.0.0.1:9222/a'),
        BrowserTab('课程 B', 'https://www.dedao.cn/course/b', 'ws://127.0.0.1:9222/b'),
    ]

    with pytest.raises(BrowserExtractionError):
        select_tab(tabs, url_contains='dedao.cn')

    selected = select_tab(tabs, url_contains='/course/b')
    assert selected.title == '课程 B'


def test_fetch_tabs_preserves_original_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_open(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError('connection refused')

    monkeypatch.setattr(browser.urllib.request, 'urlopen', fail_to_open)

    with pytest.raises(BrowserExtractionError) as exc_info:
        fetch_tabs()

    message = str(exc_info.value)
    assert '无法连接 Chrome DevTools' in message
    assert 'connection refused' in message


def test_devtools_origin_matches_websocket_endpoint() -> None:
    assert devtools_origin('ws://127.0.0.1:9222/devtools/page/1') == 'http://127.0.0.1:9222'
    assert devtools_origin('wss://example.test/devtools/page/1') == 'https://example.test'


def test_page_text_from_payload_cleans_without_saving_source() -> None:
    raw = json.dumps(
        {
            'title': '测试课时',
            'url': 'https://www.dedao.cn/course/article',
            'selector': 'main',
            'text': '返回\n\n第一段正文。\n\n分享\n第二段正文。',
        },
        ensure_ascii=False,
    )

    page = page_text_from_payload(raw)

    assert page.title == '测试课时'
    assert page.url == 'https://www.dedao.cn/course/article'
    assert page.selector == 'main'
    assert page.text == '第一段正文。\n\n第二段正文。'


def test_extract_chrome_text_by_url_filters_passes_filters_to_jxa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_args: list[str] = []

    def fake_run(
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        captured_args.extend(args)
        payload = json.dumps(
            {
                'title': '得到课程单篇',
                'url': 'https://www.dedao.cn/course/article?id=obyr',
                'selector': 'article',
                'text': '正文第一句。正文第二句。',
            },
            ensure_ascii=False,
        )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=payload, stderr='')

    monkeypatch.setattr(browser.subprocess, 'run', fake_run)

    page = extract_chrome_text_by_url_filters(
        ['www.dedao.cn/course/article?id=obyr', 'www.dedao.cn/course/article'],
    )

    assert captured_args[:4] == ['osascript', '-l', 'JavaScript', '-e']
    assert json.loads(captured_args[-1]) == [
        'www.dedao.cn/course/article?id=obyr',
        'www.dedao.cn/course/article',
    ]
    assert page.title == '得到课程单篇'
    assert page.url == 'https://www.dedao.cn/course/article?id=obyr'
    assert page.text == '正文第一句。正文第二句。'

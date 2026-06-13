import json
import subprocess

import pytest

from read_along import browser
from read_along.browser import (
    build_extract_page_script,
    clean_browser_text,
    extract_chrome_url_text,
    page_text_from_payload,
)


def test_extract_page_script_uses_body_only_as_fallback() -> None:
    script = build_extract_page_script()

    assert "candidates.push({ selector: 'body'" not in script
    assert "? { selector: preferredSelectors[0], text: '', length: 0 }" in script
    assert ": { selector: 'body', text: bodyText, length: bodyText.length }" in script


def test_extract_page_script_prefers_requested_content_selector() -> None:
    script = build_extract_page_script(
        ('.article-body',),
        preferred_title_selectors=('.article-title',),
    )

    assert 'const preferredSelectors = [".article-body"];' in script
    assert 'const preferredTitleSelectors = [".article-title"];' in script
    assert 'preferredSelectors.length > 0 ? preferredCandidates : fallbackCandidates' in script
    assert 'preferredTitleSelectors.length > 0' in script


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


def test_extract_chrome_url_text_passes_target_url_and_closes_temp_tab(
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

    page = extract_chrome_url_text(
        'https://www.dedao.cn/course/article?id=obyr',
        preferred_selectors=('.article-body',),
        preferred_title_selectors=('.article-title',),
    )

    assert captured_args[:4] == ['osascript', '-l', 'JavaScript', '-e']
    assert 'chrome.Tab({ url: targetUrl })' in captured_args[4]
    assert 'tab.close()' in captured_args[4]
    assert captured_args[-3] == 'https://www.dedao.cn/course/article?id=obyr'
    assert json.loads(captured_args[-2]) == ['.article-body']
    assert 'const preferredTitleSelectors = [".article-title"];' in captured_args[-1]
    assert page.title == '得到课程单篇'
    assert page.url == 'https://www.dedao.cn/course/article?id=obyr'
    assert page.text == '正文第一句。正文第二句。'

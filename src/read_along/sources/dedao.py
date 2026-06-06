from __future__ import annotations

import urllib.parse

from read_along.browser import GENERIC_NOISE_LINE_PATTERNS, clean_browser_text


DEDAO_HOSTS = {"dedao.cn", "www.dedao.cn"}

DEDAO_NOISE_LINE_PATTERNS = [
    r"^写留言$",
    r"^发布$",
    r"^点赞$",
    r"^收藏$",
    r"^上一讲$",
    r"^下一讲$",
    r"^上一节$",
    r"^下一节$",
    r"^已学完$",
    r"^上次学到$",
    r"^课程介绍$",
    r"^课程目录$",
    r"^全部留言$",
    r"^我的留言$",
    r"^知识城邦$",
    r"^得到$",
]


def supports_url(url: str) -> bool:
    """Return whether this adapter handles the URL."""
    hostname = urllib.parse.urlparse(url).hostname or ""
    return hostname in DEDAO_HOSTS or hostname.endswith(".dedao.cn")


def clean_text(text: str) -> str:
    """Remove generic and Dedao-specific visible-page noise."""
    return clean_browser_text(text, GENERIC_NOISE_LINE_PATTERNS + DEDAO_NOISE_LINE_PATTERNS)

from read_along.sources.dedao import clean_text, supports_url


def test_supports_dedao_urls_only() -> None:
    assert supports_url('https://www.dedao.cn/course/article')
    assert supports_url('https://m.dedao.cn/article')
    assert not supports_url('https://example.com/dedao.cn/article')


def test_clean_text_drops_dedao_specific_noise() -> None:
    raw = """
得到
课程目录
第一段正文解释核心概念。

分享
下一讲
第二段正文给出应用场景。
"""

    cleaned = clean_text(raw)

    assert '得到' not in cleaned
    assert '课程目录' not in cleaned
    assert '下一讲' not in cleaned
    assert '分享' not in cleaned
    assert '第一段正文解释核心概念。' in cleaned
    assert '第二段正文给出应用场景。' in cleaned

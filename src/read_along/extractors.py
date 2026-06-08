from __future__ import annotations

import re

import pymupdf

# --- 正则表达式 ---

# 常见噪声模式：简短导航标签、社交分享按钮、评论区标题和翻页提示等
_NOISE_LINE_PATTERNS = [
    re.compile(r'^\s*(上一篇|下一篇|下一章|下一节|返回目录|回顶部|返回首页)\s*$'),
    re.compile(r'^\s*(分享|收藏|点赞|评论|举报|投诉|赞赏|打赏|关注)\s*$'),
    re.compile(r'^\s*(网友评论|用户留言|精选留言|全部留言|最新评论|热门评论)\s*$'),
    re.compile(r'^\s*(登录|注册|退出|设置|搜索|扫码|手机看|APP看)\s*$'),
    re.compile(r'^\s*(更多|加载更多|展开全文|收起)\s*$'),
    re.compile(r'^\s*(Copyright|©|版权所有|All Rights Reserved|隐私政策|用户协议).*\s*$'),
    # 单个字符或纯符号行
    re.compile(r'^\s*[^\w\u4e00-\u9fff]+\s*$'),
    # 极短行（1 个字符）
    re.compile(r'^\s*\w\s*$'),
]

# 全角空格和不换行空格
_SPACE_REPLACEMENTS = {'\u3000': ' ', '\xa0': ' '}


def pdf_page_texts(file_path: str) -> list[tuple[int, str]]:
    """提取 PDF 每一页的文本。

    返回由 (页码, 文本) 元组组成的列表。PDF 不包含可提取文本时
    抛出 ValueError，这通常表示 PDF 是未经过 OCR 的扫描文件。
    """
    doc = pymupdf.open(file_path)
    pages: list[tuple[int, str]] = []

    page_count = len(doc)
    for page_num in range(page_count):
        page = doc[page_num]
        text = page.get_text()
        text = normalize_whitespace(text)
        pages.append((page.number + 1, text))

    doc.close()

    total = sum(len(page_text) for _, page_text in pages)
    if total == 0:
        raise ValueError('PDF 不包含可提取文本，可能是未经过 OCR 的扫描文件。')

    return pages


def normalize_whitespace(text: str) -> str:
    """合并空白字符（包括制表符和不换行空格）并去除首尾空白。"""
    for old, new in _SPACE_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_text(text: str) -> str:
    """移除提取文本中的常见噪声模式。

    删除符合已知噪声模式的行，包括导航、社交按钮、评论区标题和版权声明等，
    并删除连续重复行。
    """
    lines = text.split('\n')
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            # 保留空行作为段落分隔符
            if filtered and filtered[-1] != '':
                filtered.append('')
            continue
        if _is_noise_line(stripped):
            continue
        filtered.append(stripped)

    # 删除末尾空行
    while filtered and filtered[-1] == '':
        filtered.pop()

    return '\n'.join(filtered)


def _is_noise_line(line: str) -> bool:
    """检查单行文本是否符合已知噪声模式。"""
    for pattern in _NOISE_LINE_PATTERNS:
        if pattern.match(line):
            return True
    return False


def split_paragraphs(text: str) -> list[str]:
    """使用连续换行边界将文本拆分为段落。

    将一个或多个空行视为段落分隔符。
    """
    normalised = text.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', normalised)
    return [block.strip() for block in blocks if block.strip()]


def split_sentences(text: str, *, max_length: int = 120) -> list[str]:
    """将文本块拆分为句子并过滤噪声。

    识别中文句末标点（。！？；）和英文句末标点（.?!;）。
    过滤过短的噪声句，并在中文逗号位置拆分过长句子。
    """
    if not text:
        return []

    chinese_break = re.compile(r'(?<=[。！？；])')
    english_break = re.compile(r'(?<=[.?!;])(?=\s|$)')

    parts = chinese_break.split(text)

    sentences: list[str] = []
    for part in parts:
        subs = english_break.split(part)
        for sub in subs:
            stripped = sub.strip()
            if not stripped:
                continue
            if len(stripped) > max_length and _contains_cjk(stripped):
                split = _split_long_sentence(stripped, max_length)
                sentences.extend(split)
            else:
                sentences.append(stripped)

    # 过滤噪声句子
    return [s for s in sentences if not _is_noise_sentence(s)]


def _contains_cjk(text: str) -> bool:
    """检查文本是否包含 CJK 字符。"""
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))


def _split_long_sentence(text: str, max_length: int) -> list[str]:
    """在中文逗号（，）位置拆分过长句子。

    在可能的情况下，使每个拆分片段至少包含 20 个字符。
    """
    # 按中文逗号拆分
    parts = re.split(r'(?<=，)', text)
    result: list[str] = []
    buf = ''

    for part in parts:
        if len(buf) + len(part) <= max_length:
            buf += part
        else:
            if buf:
                result.append(buf.strip())
            buf = part

    if buf.strip():
        result.append(buf.strip())

    return result if result else [text]


def _is_noise_sentence(sentence: str) -> bool:
    """检查句子是否为噪声，包括过短、纯符号或符合已知模式的句子。"""
    stripped = sentence.strip()
    if not stripped:
        return True

    # 纯标点或符号，不包含 CJK 字符、ASCII 字母或数字
    has_content = re.search(r'[\u4e00-\u9fff\w]', stripped)
    if not has_content:
        return True

    # 匹配已知噪声模式
    if _is_noise_line(stripped):
        return True

    # 单个 CJK 字符（可能带标点）通常属于噪声
    no_punct = re.sub(r'[。！？；，…、.?!;,\s]+', '', stripped)
    if len(no_punct) <= 1 and re.search(r'[\u4e00-\u9fff]', no_punct):
        return True

    return False


def structure_text(text: str) -> list[list[str]]:
    """将原始文本结构化为段落和句子。

    处理流程：清理噪声 -> 拆分段落 -> 将各段落拆分为句子。

    返回段落列表，每个段落由句子字符串列表组成。
    """
    cleaned = clean_text(text)
    paragraphs = split_paragraphs(cleaned)
    return [split_sentences(para) for para in paragraphs if para.strip()]

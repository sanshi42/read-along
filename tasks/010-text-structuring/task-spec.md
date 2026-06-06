# Task 010：文本结构化

## Task ID

`010-text-structuring`

## Task Title

增强文本结构化管线：噪声清洗、合理化段落检测、改进句子切分。

## Backlog Reference

`MVP-005`：文本结构化。让导入材料的段落和句子组织更合理，去除明显噪声。

## Goal

改进从原始文本到结构化段落/句子的整个管线，使 PDF 导入产生的材料不再"每页一段落"，而是按逻辑段落分拆，句子过滤噪声并处理过长句。

## Scope

- 增强 `extractors.py`：
  - `clean_text`：去除常见导航词、按钮词、评论区标记等噪声模式。
  - `split_sentences`：过滤空串和过短噪声句（< 2 有效字符）；对超长句（> 120 字符）按中文逗号二次切分。
  - `structure_text`：组合清洗 → 段落切分 → 句子切分 → 噪声过滤的完整管线。
- 更新 `importers.py`：
  - 对每页 PDF 文本先用 `structure_text` 拆成逻辑段落，再按段落存储。
  - `source_label` 改为 `"Page N, Block M"` 形式，保留页码和段落位置信息。
- 不改变 API 接口和 `MaterialDetail` 返回结构。

## Non-goals

- 不做得到专用清洗规则（留给 MVP-005 完成后的特定来源优化）。
- 不做基于 LLM 的段落/句子边界检测。
- 不改变 PDF 文本提取方式（仍用 PyMuPDF 逐页）。

## Implementation Notes

- 噪声模式使用正则黑名单：匹配行首/行尾的常见噪声短语。
- `structure_text` 返回 `list[list[str]]`：外层是段落，内层是句子。
- 长句二次切分仅在中国逗号（，）处分拆，且每段至少 20 字符。
- 句子过滤保留至少一个中文字符或单词作为有效内容。

## Acceptance Criteria

- PDF 导入后，同一页内的多个逻辑段落能被拆成多个 `Paragraph`。
- 明显噪声（如单字行、纯符号行、"上一篇""下一篇"等）不出现在段落和句子中。
- 超过 120 字符的中文句子按逗号合理分拆。
- 段落和句子顺序与原文一致。

## Test Plan

- 单元测试：`clean_text` 噪声清理、`split_sentences` 长句切分和噪声过滤、`structure_text` 完整管线。
- 更新 `test_importers.py`：验证多段落页面能产生多个 paragraph。

## Completion Notes

(待完成后填写)

## Completion Notes

已完成。

- 增强 `extractors.py`：
  - `clean_text`：按行过滤噪声模式（导航词"上一篇/下一篇"、分享按钮、评论区标题、版权声明、单字符行、纯符号行），保留空白行作为段落分隔。
  - `split_sentences`：新增 `max_length` 参数，超长句（> 120 字符）按中文逗号（，）二次切分；过滤空串、纯标点句、单字 CJK 句。
  - `structure_text`：组合 `clean_text → split_paragraphs → split_sentences` 的完整管线。
  - `_is_noise_sentence`：改进单字 CJK 检测（剥离标点后判断）。
- 更新 `importers.py`：
  - 对每页 PDF 文本使用 `structure_text` 拆成逻辑段落，不再"每页一段落"。
  - `source_label` 改为"Page N, Block M"格式。
- 新增测试 21 个，覆盖噪声清洗、长句切分、单字 CJK 过滤、管线集成和段落拆分。
- 全量 102 个测试、ruff、mypy 全部通过。

```text
uv run --no-editable pytest                    102 passed
uv run --no-editable ruff check .              All checks passed!
uv run --no-editable mypy src tests            Success: no issues found in 26 source files
```

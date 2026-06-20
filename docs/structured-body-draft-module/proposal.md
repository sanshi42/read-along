---
status: done
priority: P1
created: 2026-06-20
---

# 结构化正文 Draft Module Proposal

## Goal

加深结构化正文 Draft Module，让段落正文等于句子序列这一不变量由 Draft 自己拥有，而不是由导入端和材料库分别维护。

目标完成后，导入端只提交句子序列和来源标记；材料库保存路径消费已经成形的 Draft，不再需要检查段落正文与句子列表是否同步。

## Boundary

### In

- 收缩 `ReadingMaterialDraftParagraph` Interface：句子序列是输入，段落正文由句子序列派生。
- 更新 PDF、URL 导入端和测试构造，不再手写 `text=' '.join(sentences)`。
- 移除材料库中对段落正文与句子序列同步的重复校验，保留空正文、空句子和来源标记校验。
- 增加或调整聚焦于 Draft Interface 的测试。

### Out

- 改变结构化正文清洗、分句或排序规则。
- 改变 `content_hash` 算法。
- 改变数据库中的段落和句子持久化结构。
- 重构来源文本到结构化正文 pipeline。

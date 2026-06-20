# 结构化正文 Draft Module Tasks

## Task 1: Draft Paragraph Interface

Goal: 让 `ReadingMaterialDraftParagraph` 从句子序列派生段落正文，并通过测试覆盖该 Interface。

Depends on: none

Verification: 模型测试覆盖不再传入 `text` 也能读取派生正文，且 `model_dump()` 不暴露派生正文。

Status: Done

## Task 2: 导入端和保存路径接入

Goal: 更新 PDF、URL 导入端和测试构造，材料库保存路径继续写入相同段落正文。

Depends on: Task 1

Verification: 导入器和材料库测试继续通过。

Status: Done

## Task 3: 整体验证

Goal: 完成 Topic 级验证并关闭 Topic。

Depends on: Task 2

Verification: 运行 `make check`。

Status: Done

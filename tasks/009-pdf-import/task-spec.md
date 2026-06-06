# Task 009：PDF 导入

## Task ID

`009-pdf-import`

## Task Title

实现文本型 PDF 上传与结构化导入。

## Backlog Reference

`MVP-004`：PDF 导入。使学习者可以上传文本型 PDF 并将其导入为阅读材料。

## Goal

提供 PDF 上传与导入功能：接收 PDF 文件、提取文本、按段落和句子结构化存储，返回材料详情。

## Scope

- 新增 `src/read_along/extractors.py`：基础文本清洗、段落切分、句子切分。
- 新增 `src/read_along/importers.py`：PDF 导入流程入口。
- 新增 `POST /api/import/pdf` 端点，接受 multipart 上传，返回材料详情。
- 使用 PyMuPDF 逐页提取文本；每页作为一个段落，页码作为 `source_label`。
- 每个段落按中文标点（。！？；）和英文标点（.?!;）做基础句子切分。
- 导入的文件保存到 `uploads/` 目录。
- 无法提取有效文本时返回错误。

## Non-goals

- 不做扫描版 PDF OCR（超出 MVP scope）。
- 不做 `import_jobs` 后台异步导入（本任务同步完成导入）。
- 不做文本噪声清洗和高级段落检测（留给 MVP-005）。

## Implementation Notes

- PyMuPDF 的 `page.get_text()` 返回 UTF-8 字符串。
- 材料 ID 使用 `generate_material_id("pdf", filename)` 生成。
- `content_hash` 用全文清洗后文本的 SHA-256 生成。
- 上传文件以 `material_id` 重命名避免冲突。
- 句子切分后过滤空串和仅含空白字符的串。

## Acceptance Criteria

- 可上传文本型 PDF，返回包含 material、paragraphs、sentences 的详情。
- 上传后材料出现在列表中。
- 段落和句子顺序与原文一致。
- 扫描版或无文本 PDF 上传失败并返回错误。
- 上传同一 PDF 两次不产生重复材料（待 MVP-015 完整体现）。

## Test Plan

- 单元测试：`extractors.py` 的段落/句子切分函数。
- API 测试：POST /api/import/pdf 成功/失败路径。
- 手工验收：上传一个文本型 PDF 并检查返回结构。

## Completion Notes

(待完成后填写)

## Completion Notes

已完成。

- 新增 `src/read_along/extractors.py`：提供文本清洗（`normalize_whitespace`）、段落切分（`split_paragraphs`）、句子切分（`split_sentences`）和 PDF 页文本提取（`pdf_page_texts`）。
- 新增 `src/read_along/importers.py`：提供 `import_pdf()` 函数，完整流程：PyMuPDF 逐页提取文本 → 生成 material_id → 创建材料 → 每页一个段落 → 段落内句子切分 → 返回 `MaterialDetail`。
- 新增 `POST /api/import/pdf` 端点：接受 multipart PDF 上传，调用 `import_pdf` 后返回 JSON 材料详情。扫描版或空 PDF 返回 422 错误。
- 更新 `api.py`：新增 `AppState`、`init_app_state()`、`get_storage_paths()`、`get_repository()` 依赖注入。
- 更新 `cli.py`：启动时调用 `init_app_state()` 初始化数据库和存储路径。
- 新增依赖：`pymupdf`、`python-multipart`。
- 新增 `tests/test_extractors.py`（23 个测试）和 `tests/test_importers.py`（6 个测试），覆盖文本切分、PDF 提取、导入成功/失败路径。

验证结果：

```text
uv run --no-editable pytest                    81 passed
uv run --no-editable ruff check .              All checks passed!
uv run --no-editable mypy src tests            Success: no issues found in 26 source files
```

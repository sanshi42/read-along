# Task 008：稳定内容 ID 生成

## Task ID

`008-stable-content-ids`

## Task Title

实现材料、段落和句子的稳定 ID 生成，确保确定性和顺序变化场景下的唯一性。

## Backlog Reference

`MVP-003`：数据模型；在现有 SQLite schema 和 repository 基础上补齐稳定 ID 生成算法，使同一来源始终产生相同材料 ID，段落和句子 ID 在材料范围内唯一且可复现。

## Goal

提供确定性 ID 生成函数，使同一 (source_type, source_uri) 组合始终产生相同 material_id，同一材料中同一 index 的段落或句子始终产生相同的 paragraph_id / sentence_id。

## Scope

- 新增 `src/read_along/ids.py`，提供三个函数：
  - `generate_material_id(source_type, source_uri)` -> `str`
  - `generate_paragraph_id(material_id, index)` -> `str`
  - `generate_sentence_id(material_id, index)` -> `str`
- 材料 ID 基于 `source_type` + `source_uri` 的 SHA-256 摘要生成，前缀 `mat_`。
- 段落和句子 ID 基于 material_id 和全局顺序 index 生成，格式分别为 `{material_id}_p_{index:05d}` 和 `{material_id}_s_{index:07d}`。
- 覆盖确定性测试、唯一性测试和边界 index（零、大值）测试。

## Non-goals

- 不修改现有 repository、models、db schema 或 API。
- 不在本任务中将 ID 生成集成到导入流程或 repository 调用方。
- 不实现基于内容哈希的段落/句子 ID（第一版用 index 足够）。

## Implementation Notes

- 材料 ID 在导入开始前即可计算（不依赖 content_hash），确保 import_job 创建时已有确定性 ID。
- 段落和句子的全局 index 由导入流程在切分后按顺序分配；ID 生成函数本身只做格式化。
- SHA-256 使用标准库 `hashlib`，截断前 8 个 hex 字符，加上 `mat_` 前缀。
- 材料来源 URI 中可能含 Unicode 字符，编码前统一使用 UTF-8。

## Acceptance Criteria

- 相同 source_type 和 source_uri 多次调用 `generate_material_id` 返回相同值。
- 不同 source_uri 产生的 material_id 不同。
- 相同 material_id 和 index 多次调用 `generate_paragraph_id` / `generate_sentence_id` 返回相同值。
- 生成的 ID 符合 SQLite schema 的 TEXT PRIMARY KEY 要求（非空、非纯数字）。
- ID 格式清晰可读，便于调试（如 `mat_a1b2c3d4_p_00001`）。

## Test Plan

- 确定性：相同输入产生相同输出。
- 唯一性：不同输入产生不同输出。
- 格式：验证 material_id 以 `mat_` 开头且总长合理；paragraph/sentence ID 包含 material_id 和格式化 index。
- 边界：index 为 0、int 最大值、material_id 含特殊字符均不抛异常。
- 运行验证命令。

## Completion Notes

(待完成后填写)

## Completion Notes

已完成。

- 新增 `src/read_along/ids.py`，提供三个确定性 ID 生成函数：
  - `generate_material_id(source_type, source_uri)`：SHA-256 摘要 + `mat_` 前缀，同一来源始终产生相同 ID。
  - `generate_paragraph_id(material_id, index)`：嵌入材料 ID 和五位零填充 index，如 `mat_a1b2c3d4_p_00001`。
  - `generate_sentence_id(material_id, index)`：同段落模式，七位零填充 index。
- 新增 `tests/test_ids.py`，21 个测试覆盖确定性、唯一性、格式、Unicode、零/大值 index 和全局唯一性。
- 未修改 repository、models、db schema 或 API；ID 生成函数为独立模块，供后续导入流程和 repository 调用方使用。

验证结果：

```text
uv run --no-editable pytest                    52 passed
uv run --no-editable ruff check .              All checks passed!
uv run --no-editable mypy src tests            Success: no issues found in 22 source files
uv run --no-editable read-along --help         passed
git diff --check                               passed
```

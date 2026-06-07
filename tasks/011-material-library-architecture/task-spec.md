# Task 011：深化材料库持久化 Module 设计

## Task ID

`011-material-library-architecture`

## Task Title

深化材料库持久化 Module 设计。

## Backlog Reference

支撑 `MVP-002`、`MVP-003`、`MVP-004`、`MVP-013`、`MVP-015` 和 `MVP-020` 的共同材料库行为。

## Goal

明确一个深材料库持久化 Module 的责任、Interface、不变量和错误语义，使 PDF、网页和得到导入 Module 不需要理解 SQLite、事务、ID 分配或材料详情组装。

## Scope

- 明确材料库持久化 Module 拥有的完整持久化生命周期。
- 明确导入 Module 与材料库持久化 Module 之间的 seam。
- 明确阅读材料、结构化正文和材料库领域术语。
- 明确正文等价性、重复导入、失败回滚、完整读取和删除语义。
- 记录最终设计决策，为后续独立实现任务提供输入。

## Non-goals

- 不修改现有 Python 实现。
- 不修改 SQLite schema。
- 不实现 PDF、网页、得到、TTS、阅读进度或删除材料功能。
- 不扩大 MVP 范围。

## Implementation Notes

- 材料库持久化 Module 拥有阅读材料的原子保存、完整读取、重复判断和删除生命周期。
- 导入 Module 只提供来源事实、源文件和结构化正文。
- 材料库持久化 Module 负责生成 ID、分配顺序、设置初始音频状态和时间戳。
- `content_hash` 基于结构化清洗后的正文计算，而不是来源 Adapter 提供的原始提取文本。
- 重复导入按来源身份和结构化正文分别判断：
  - 来源相同且结构化正文相同：返回现有阅读材料。
  - 来源不同但结构化正文相同：为现有阅读材料新增来源身份并返回该阅读材料，避免重复正文。
  - 来源相同但结构化正文不同：返回冲突错误，不自动覆盖正文、阅读进度或音频。
- 刷新已有来源属于后续独立能力，不隐含在导入行为中。
- 一篇阅读材料可以关联多个来源身份：
  - 每个来源身份保存 `source_type`、稳定 `source_key`、展示与回查用 `source_uri` 和可选内部源文件。
  - URL 的 `source_key` 使用规范化 URL：移除 fragment，规范化 scheme、host 和默认端口，保留 path 和 query。
  - PDF 的 `source_key` 使用上传文件字节的 SHA-256，`source_uri` 保留原文件名。
  - 任一已记录来源身份后续对应不同结构化正文时，返回 `SourceChangedError`。
  - 阅读材料保留首次导入的标题，新增来源身份不覆盖标题。
  - 书架和阅读视图展示首次导入的主来源，同时可以返回全部来源身份。
  - 删除阅读材料时删除全部来源身份及其内部源文件。
  - 为现有阅读材料新增来源身份时，不复制新的源文件，该来源身份的内部源文件为空。
  - 后续实现需要新增类似 `material_sources` 的表，替代 `materials` 上的单一来源字段。
  - `materials.content_hash` 唯一，每篇阅读材料恰好有一个主来源，同一 `source_type` 和 `source_key` 只能对应一个来源身份，来源身份不会被导入行为重新指向其他阅读材料。
- 阅读材料只表示已成功原子保存的结果：
  - 目标 `materials` 模型删除 `status` 和 `error_message`。
  - 导入状态和错误信息全部属于导入任务 Module。
- 原子保存和失败语义：
  - 调用返回成功前，阅读材料对调用方完全不可见。
  - 阅读材料、来源身份、段落和句子在一个 SQLite 事务中保存。
  - PDF 等源文件先写入临时位置，再移动到最终路径。
  - 任一步失败都回滚数据库并清理临时文件。
  - 进程意外中断最多留下孤立文件，不留下部分可见阅读材料；启动时清理孤立文件。
  - 导入失败直接返回错误，不持久化 `failed` 阅读材料；失败记录由未来的导入任务 Module 负责。
- 外部读取 Interface 只提供两种视图：
  - 书架视图：按最近更新时间列出阅读材料摘要，包含标题、主来源和进度摘要。
  - 阅读视图：按 ID 返回完整 `MaterialDetail`，包含有序段落、有序句子和阅读进度。
- 不向通用调用方暴露独立的段落和句子列表读取；TTS 等流程所需的细粒度查询属于材料库 Module 的内部 Interface。
- 删除生命周期：
  - `delete(material_id)` 是材料库持久化 Module 的唯一删除 Interface。
  - 数据库中的阅读材料、结构化正文和阅读进度在一个事务中删除。
  - 源文件与未来音频缓存由材料库 Module 在事务提交后尽力清理。
  - 文件清理失败不恢复数据库记录；记录可重试的孤立文件清理任务。
  - 删除不存在的阅读材料视为成功，保证操作幂等。
  - 删除不提供保留音频缓存选项。
- 阅读进度属于材料库持久化 Module 的外部 Interface：
  - 调用方提供 `material_id`、`sentence_id` 和 `playback_rate`。
  - Implementation 验证阅读材料存在、句子属于该阅读材料且倍速有效。
  - Implementation 设置更新时间并原子覆盖当前进度。
  - 调用方不提供时间戳，也不直接操作阅读进度记录。
- 保存 Interface 接收不含持久化字段的 `ReadingMaterialDraft`：
  - 来源事实：`source_type`、`source_uri`、`title` 和可选源文件。
  - 结构化正文：有序段落；每段包含 `text`、可选 `source_label` 和有序句子文本。
  - Draft 不包含 `source_key`、任何 ID、全局顺序、`content_hash`、状态、时间戳、音频状态、音频路径或阅读进度。
  - Implementation 验证段落与句子非空，并验证段落文本和句子内容一致。
  - Implementation 生成 `source_key` 和所有持久化字段。
- 源文件所有权：
  - `source_file` 可选；PDF 提供，网页和得到通常不提供。
  - 调用方始终保留原文件所有权；材料库 Module 不移动或删除调用方文件。
  - 保存时，材料库 Module 将源文件复制到自身临时路径，在数据库事务提交前原子重命名到最终路径。
  - 数据库提交失败时删除最终文件；进程中断最多留下可清理的孤立文件。
  - 成功或失败后，调用方都可以自行清理原文件。
  - 保存成功后，材料库 Module 独占管理内部副本。
  - 重复导入返回现有阅读材料时，不保存新的源文件副本。
- 外部 Interface 只暴露可操作的领域错误：
  - `InvalidDraftError`：结构化正文为空、不一致或字段非法。
  - `SourceChangedError`：来源相同但结构化正文不同。
  - `MaterialNotFoundError`：读取或保存进度时阅读材料不存在。
  - `InvalidProgressError`：句子不属于阅读材料或倍速非法。
  - SQLite、文件复制和事务失败等 Implementation 错误统一为 `MaterialLibraryError`，保留原始原因用于日志。
  - 删除保持幂等，不产生 `MaterialNotFoundError`；重复导入返回现有阅读材料，不作为错误。

### Final Interface

```python
class MaterialLibrary:
    def save(self, draft: ReadingMaterialDraft) -> MaterialDetail: ...
    def list_shelf(self) -> list[MaterialSummary]: ...
    def get(self, material_id: str) -> MaterialDetail: ...
    def save_progress(
        self,
        material_id: str,
        sentence_id: str,
        playback_rate: float,
    ) -> ReadingProgress: ...
    def delete(self, material_id: str) -> None: ...
```

这个 Interface 是 PDF、网页、得到导入、书架、阅读页和进度保存共同使用的外部 seam。SQLite 连接、细粒度查询、事务、ID 生成、时间戳、文件布局和孤立文件清理全部位于 Implementation 内。

## Acceptance Criteria

- `CONTEXT.md` 定义本轮设计使用的领域术语。
- 材料库持久化 Module 的责任与非责任清楚。
- Interface 的输入、输出、不变量和错误模式清楚。
- 重复导入、失败回滚、完整读取和删除语义清楚。
- 后续实现可拆成独立小任务，不需要重新决定核心语义。

## Test Plan

- 检查设计与 `docs/mvp-scope.md`、`docs/product-backlog.md` 和 `docs/tech-design.md` 对齐。
- 检查没有引入 MVP 范围外能力。
- 检查领域术语与架构术语使用一致。

## Completion Notes

已完成材料库持久化 Module 设计。

- 确认材料库 Module 拥有阅读材料的完整持久化生命周期。
- 确认 `content_hash` 基于结构化正文计算，一篇阅读材料可关联多个来源身份。
- 确认来源身份使用稳定 `source_key`，并保留 `source_uri` 用于展示和回查。
- 确认阅读材料只表示成功保存的结果，导入状态和错误归导入任务 Module。
- 确认重复导入、来源内容变化、原子保存、失败处理、读取、删除、阅读进度、保存 Draft、源文件所有权和错误模式。
- 最终外部 Interface 收敛为 `save`、`list_shelf`、`get`、`save_progress` 和 `delete`。
- 后续实现需要新增 `material_sources` 等效结构并迁移现有材料模型；本任务只完成设计，未修改 Python 实现或 SQLite schema。

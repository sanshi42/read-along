# Task 015：阅读页正文展示

## Task ID

`015-reader-page`

## Task Title

阅读页展示材料标题、来源和结构化正文，按段落和句子生成可定位节点。

## Backlog Reference

`MVP-007`：阅读页。使学习者可以在阅读页舒适地阅读材料正文。

## Goal

在现有阅读页入口基础上渲染完整的结构化正文，包括标题、来源标签、有序段落和带 `sentence_id` 的可定位句子节点，并确保长文滚动体验流畅。

## Scope

- 阅读页渲染 `MaterialDetail` 中的全部段落和句子。
- 每个句子 `<span>` 带 `id={sentence.id}`，可通过 DOM 定位。
- 句子可点击（`role="button"`、`tabIndex={0}`），更新 `currentSentenceId` state，为后续播放器接轨。
- 句子悬停时轻微透明度变化，暗示可交互。
- 导航栏改为 `position: sticky`，带半透明背景模糊，滚动时不遮挡正文。
- 正文排版：`max-width: 42rem`、字号 `1.1rem`、行高 `2`、段落间距 `1.8em`，居中。
- 加载态与错误态沿用现有实现，成功后展示正文。

## Non-goals

- 不实现 `source_label`（PDF 页码）渲染。
- 不实现播放器、句子高亮、倍速或进度保存（属于后续 MVP）。
- 不实现阅读设置（字号、行距、主题，属于 `MVP-016`）。
- 不实现 TTS 音频生成或句子音频状态 UI。
- 不新增独立前端测试框架。

## Implementation Notes

- 仅修改 `web/src/routes/ReaderPage.tsx` 和 `web/src/styles.css`。
- 句子 `<span>` 内联自然流动，不额外插入空格或换行。
- 使用 `useState` 维护 `currentSentenceId`，点击句子时更新，预留后续播放器消费。
- 导航 sticky 实现：`position: sticky; top: 0; z-index: 1; background: rgba(243, 239, 230, 0.85); backdrop-filter: blur(8px)`，底部细边。
- 复用现有 API `getMaterial()` 和 `MaterialDetail` 类型，不新增接口。
- 正文段落用 `<section>` 包裹，每段内用 `<p>` 承载句子 `<span>` 序列。

## Acceptance Criteria

- 打开已导入材料的阅读页，能看到完整正文按段落和句子展示。
- 每个句子有唯一 `id` 属性匹配后端 `sentence_id`。
- 点击任意句子不报错，控制台无异常。
- 句子悬停时有视觉反馈（透明度变化）。
- 长文滚动时导航栏始终可见，不遮挡正文标题。
- 正文排版可读：行高舒适、段落分明、宽度不溢出。
- 加载态和错误态展示正常。
- 后端全量测试、Ruff、mypy 和前端生产构建通过。
- 浏览器中验证主要交互。

## Test Plan

- 运行 `uv run --no-editable pytest`。
- 运行 `uv run --no-editable ruff check .`。
- 运行 `uv run --no-editable mypy src tests`。
- 运行 `npm run build --prefix web`。
- 启动后端和前端，在浏览器中打开已有材料的阅读页，验证正文渲染、句子可点击、导航 sticky 行为。
- 验证空材料错误态仍正常。

## Completion Notes

已完成。

- 修改 `web/src/routes/ReaderPage.tsx`：将 placeholder 替换为完整正文渲染，按段落和句子生成可定位节点。
- 每个句子 `<span>` 带 `id={sentence.id}`，支持 `role="button"`、`tabIndex={0}` 可点击交互。
- 新增 `currentSentenceId` state 和 `handleSentenceClick` callback，为后续播放器预留。
- 导航栏改为 `position: sticky`，带半透明背景模糊，长文滚动时始终可见。
- 修改 `web/src/styles.css`：新增 `.reader-content`、`.reader-paragraph`、`.reader-sentence` 样式，移除 `.reader-placeholder`。
- 正文排版：`max-width: 42rem`、字号 `1.1rem`、行高 `2`、段落间距 `1.8em`。
- 句子悬停时透明度变化，`focus-visible` 有 `outline` 反馈。
- `uv run --no-editable pytest`：115 个测试通过。
- `uv run --no-editable ruff check .`：通过。
- `uv run --no-editable mypy src tests`：通过。
- `npm run build --prefix web`：通过。

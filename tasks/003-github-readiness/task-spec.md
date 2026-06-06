# Task 003：GitHub 提交前检查

## Task ID

`003-github-readiness`

## Task Title

规范化项目规则文件并完成首次 GitHub 提交前检查。

## Backlog Reference

支撑性工作；对应首次提交前的仓库规范化和质量检查，不直接对应某个 MVP 用户故事。

## Goal

确保仓库可以作为清晰、可验证的初始版本提交到 Git，并让后续开发 Agent 能识别项目级规则文件。

## Scope

- 将根目录项目规则文件规范化为 `AGENTS.md`。
- 更新仓库内对项目级规则文件的引用。
- 检查源码、测试、配置、忽略规则和文档一致性。
- 修复检查中发现的 Chrome 正文候选选择问题。
- 为正文候选选择加入回归测试。
- 运行项目质量检查和构建验证。

## Non-goals

- 不实现新的 MVP 功能。
- 不新增前端、存储、PDF 导入或 TTS 能力。
- 不改变产品范围或技术选型。
- 不决定仓库公开范围或开源许可证。

## Implementation Notes

- `AGENTS.md` 是 Codex 等开发 Agent 识别项目级协作规则的标准文件名。
- 页面正文提取应优先选择可见正文候选，仅在没有合格候选时回退到整页 `body`。
- 当前仓库路径不包含空格，文档不再用路径空格解释 `--no-editable` 约定。

## Acceptance Criteria

- 根目录存在标准命名的 `AGENTS.md`。
- 仓库内不存在过时的项目规则文件引用。
- 页面正文脚本不会在存在合格正文候选时固定选择整页 `body`。
- Git 忽略规则排除虚拟环境、IDE 配置和工具缓存。
- 自动测试、静态检查、类型检查、CLI 入口和构建验证通过。

## Test Plan

```bash
uv run --no-editable pytest
uv run --no-editable ruff check .
uv run --no-editable mypy src tests
uv run --no-editable read-along --help
uv build --no-sources
```

另外检查 Git 状态、忽略文件和仓库内的过时项目规则文件引用。

## Completion Notes

已完成。

- 项目级规则文件和全部引用已统一为 `AGENTS.md`。
- Chrome 正文提取现在只在没有合格正文候选时回退到整页 `body`。
- 已新增回归测试，并完成首次提交前的仓库检查。

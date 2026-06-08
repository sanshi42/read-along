# AGENTS.md

## 项目工作方式

本项目采用敏捷开发，但执行时必须坚持 **一次只完成一个小任务**。不要在同一次实现中混合多个 backlog 项、多个 Sprint 目标或无关重构。

## 必读文档

开始任何任务前，先阅读并对齐这些文档：

- `docs/mvp-scope.md`：MVP 范围边界，决定做什么和不做什么。
- `docs/product-backlog.md`：用户故事、优先级、依赖和状态。
- `docs/tech-design.md`：最小技术方案和接口约定。
- `docs/sprint-plan.md`：Sprint 切分、进入条件和验收方式。
- `tasks/progress.md`：当前已完成任务、当前任务和下一步。

## 单任务规则

- 每次只选择一个最小可交付任务。
- 任务必须有独立目录：`tasks/<task-id>/`。
- 每个任务目录必须包含 `task-spec.md`。
- 任务开始前先写或更新 `task-spec.md`。
- 任务结束前必须更新 `tasks/progress.md`。
- 如果任务执行中发现范围变大，拆出新任务，不扩大当前任务。
- 如果新需求超出 `docs/mvp-scope.md`，默认放入 backlog 或 deferred，不直接实现。

## Task ID 约定

使用三位编号加短 slug：

```text
tasks/000-project-workflow/task-spec.md
tasks/001-reader-service-skeleton/task-spec.md
tasks/002-sqlite-storage/task-spec.md
```

编号按创建顺序递增，不因任务取消或延期而复用。

## task-spec.md 必须包含

- Task ID
- Task title
- Backlog reference
- Goal
- Scope
- Non-goals
- Implementation notes
- Acceptance criteria
- Test plan
- Completion notes

## progress.md 更新规则

每次任务结束时更新：

- 当前状态。
- 已完成任务列表。
- 当前任务。
- 下一步建议。
- 阻塞项。
- 最近变更记录。

## 开发边界

- 第一版只做个人本地 macOS Web App。
- 不做批量课程抓取。
- 不绕过登录或付费权限。
- 不保存账号密码、Cookie 或导出的浏览器凭据。
- 不做 OCR。
- 不做 LLM 改写、总结或出题。
- 不做多端同步、账号系统或公网部署。

## 技术约束

- Python 应用包使用扁平结构 `src/read_along/`，不增加重复的 `reader` 子包。
- 前端新增在 `web/`。
- 本地数据默认放在 `~/.local/share/read-along/`。
- 配置环境变量使用 `READ_ALONG_` 前缀。
- 得到专用逻辑放在 `src/read_along/sources/dedao.py`，通用层保持来源无关。
- 后端默认监听 `127.0.0.1:8765`。
- 运行 Python 项目命令时优先使用 uv 默认 editable mode，例如 `uv run ...`；仅部署或打包场景考虑 `--no-editable`。

## 验收原则

- 文档任务需要检查文件存在、内容结构清楚、与现有 scope/backlog/tech design 对齐。
- 代码任务必须有合适的测试或明确说明无法自动测试的原因。
- 前端任务完成后需要能在浏览器中验证主要交互。
- 不要把未完成项描述为完成；未完成内容写入 `tasks/progress.md` 的下一步或阻塞项。

## Agent skills

### Issue tracker

Issue 和 PRD 使用 GitHub 仓库 `sanshi42/read-along` 管理。详见 `docs/agents/issue-tracker.md`。

### Triage 标签

使用五个默认 triage 标签。详见 `docs/agents/triage-labels.md`。

### 领域文档

本仓库采用 single-context 布局。详见 `docs/agents/domain.md`。

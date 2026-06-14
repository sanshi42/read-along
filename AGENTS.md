# AGENTS.md

## 工作方式

- 默认使用中文沟通。
- 用户只需要描述目标；Topic 生命周期和 Task 调度由 Agent 自动维护。
- 一次可以完成并验证的小任务直接实现，不创建 Topic。
- 需要两个以上独立可验证 Task、依赖排序、并行执行或跨多次执行维护上下文的复杂目标，自动创建 Topic。
- 开始开发任务前扫描 `docs/*/proposal.md`，确认是否存在 Active Topic；同一时刻最多只有一个 Active Topic。
- 新请求属于当前 Active Topic 的 Goal 时，更新其 Boundary、计划和任务图后继续执行。
- 独立的新复杂目标到来时，在安全检查点暂停旧 Active Topic，再创建并执行新 Topic；独立的小任务直接实现，不修改旧 Topic。
- 用户说“继续”时，自动推进 Active Topic；没有 Active Topic 时，按优先级、状态和创建时间选择 Draft 或 Paused Topic。
- 持续领取 Ready Task，直到 Topic 自动进入 Done 或 Paused；多个 Ready Task 互不冲突且工具可用时，自动并行执行。
- 全部 Task 完成后运行 Topic 级验证；通过后自动标记 Done，失败则创建修复 Task 并继续执行。
- Agent 默认不读取或修改 `docs/ideas.md`，只有用户明确要求整理时才处理。
- 发现 Draft 或 Paused Topic 可能过时，只提出关闭建议；标记 Closed 需要用户确认。
- 涉及领域语言或架构决策时，阅读 `CONTEXT.md` 和相关 `docs/adr/`。
- 不主动扩大当前 Boundary，不混入无关重构。

## Topic 文档

- Topic 状态和优先级记录在 `docs/<topic>/proposal.md` 的 YAML Front Matter：

```yaml
---
status: draft
priority: P2
created: 2026-06-14
---
```

- 状态使用 `draft`、`active`、`paused`、`done` 或 `closed`；优先级使用 `P0` 至 `P3`，默认 `P2`。
- Draft 只有 `proposal.md`；首次开始执行时补齐 `plan.md` 和 `tasks.md`。Active 和 Paused Topic 使用完整三文件。
- `proposal.md` 只记录 Topic 状态、优先级、Goal 和 Boundary，不写实现细节。
- `plan.md` 只记录实现方案、关键决策和 Topic 级验证，不重复维护 Task 顺序。
- `tasks.md` 使用 `Depends on` 表达依赖图；每个 Task 只保留 `Goal`、`Depends on`、`Verification` 和 `Status`。
- Task 状态使用 `Pending`、`In Progress`、`Done` 或 `Blocked`；领取时临时增加 `Claimed by`，完成或重置后移除。
- Pending Task 的全部依赖均为 Done 时自动成为 Ready Task，不手写 Ready 状态。
- Active Topic 有未完成 Task，但没有 Ready 或 In Progress Task 时，记录阻塞原因并自动标记为 Paused。
- Done 和 Closed 只做逻辑归档，不移动或删除 Topic 目录；Done 不重新打开，后续复杂改进创建新 Topic。
- 不创建额外 Topic 注册表，不在 `AGENTS.md` 中写死具体 Topic。
- 迁移到本规则前已经完成的 Topic 可以保留旧版 `plan.md` 和 `tasks.md` 格式，但 `proposal.md` 必须补充可扫描的 YAML Front Matter。

没有 Active Topic 时，用户说“继续”按以下顺序选择 Topic：

1. 优先级更高的 Topic 优先。
2. 相同优先级时，Paused 优先于 Draft。
3. 状态和优先级相同时，创建时间更早的优先。

## 验证方式

- 后端或跨栈变更：运行 `make check`。
- 前端交互变更：除自动检查外，在浏览器中验证主要交互。
- 文档变更：检查链接、文件布局和内容之间没有互相冲突。
- 不要把未验证或未完成的内容描述为完成。

## Git 约定

- 未经用户明确要求，不主动 commit、push 或改写 Git 历史。

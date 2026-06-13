# AGENTS.md

## 工作方式

- 默认使用中文沟通。
- 开始任务前阅读 `docs/read-along-mvp/proposal.md`、`plan.md` 和 `tasks.md`。
- 涉及领域语言或架构决策时，阅读 `CONTEXT.md` 和相关 `docs/adr/`。
- 一次只完成 `tasks.md` 中的一个最小 Task，不混入无关重构。
- 不主动扩大当前 Boundary；新想法记录到 `tasks.md`，不要直接实现。
- 完成任务后运行验证，并更新 `tasks.md` 的 Status、验证结果和下一步。
- 如果一个 Topic 出现多个独立目标，拆成新的 `docs/<topic>/` 三文件目录，不增加流程文件。

## Topic 文档

每个 Topic 默认只包含：

```text
docs/<topic>/
  proposal.md
  plan.md
  tasks.md
```

- `proposal.md`：记录 Goal 和 Boundary，不写实现细节。
- `plan.md`：记录 Milestone、关键实现取舍和验证方式。
- `tasks.md`：记录当前 Task、近期 Task、完成摘要和阻塞项。

每个 Task 只保留 `Goal`、`Boundary`、`Verification` 和 `Status`。不为 Task 创建独立目录或规格文件。

## 验证方式

- 后端或跨栈变更：运行 `make check`。
- 前端交互变更：除自动检查外，在浏览器中验证主要交互。
- 文档变更：检查链接、文件布局和内容之间没有互相冲突。
- 不要把未验证或未完成的内容描述为完成。

## Git 约定

- 未经用户明确要求，不主动 commit、push 或改写 Git 历史。

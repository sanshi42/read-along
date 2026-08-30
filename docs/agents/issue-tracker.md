# Issue tracker：GitHub

本仓库的 Issue 和规格使用 GitHub Issues 管理。所有操作使用 `gh` CLI。

## 约定

- **创建 Issue**：`gh issue create --title "..." --body "..."`。多行正文使用 heredoc。
- **读取 Issue**：`gh issue view <number> --comments`，同时获取标签，并按需用 `jq` 筛选评论。
- **列出 Issue**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，按需添加 `--label` 和 `--state` 筛选条件。
- **评论 Issue**：`gh issue comment <number> --body "..."`。
- **添加或移除标签**：`gh issue edit <number> --add-label "..."` 或 `gh issue edit <number> --remove-label "..."`。
- **关闭 Issue**：`gh issue close <number> --comment "..."`。

在仓库克隆目录中运行命令时，由 `gh` 从 `git remote -v` 自动推断仓库。

## 将 Pull Request 作为 triage 入口

**PRs as a request surface: no.**

设为 `yes` 时，外部 PR 使用与 Issue 相同的标签和状态：

- **读取 PR**：`gh pr view <number> --comments`，并用 `gh pr diff <number>` 获取 diff。
- **列出待 triage 的外部 PR**：运行 `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，只保留 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE`。
- **评论、标记或关闭**：使用 `gh pr comment`、`gh pr edit --add-label`、`gh pr edit --remove-label` 和 `gh pr close`。

GitHub 的 Issue 和 PR 共用编号。遇到 `#42` 时，先运行 `gh pr view 42`，失败后再运行 `gh issue view 42`。

## 技能约定

- 技能要求“发布到 issue tracker”时，创建 GitHub Issue。
- 技能要求“获取相关 ticket”时，运行 `gh issue view <number> --comments`。

## Wayfinder 操作

- **Map**：使用一个带 `wayfinder:map` 标签的 Issue，正文保存 Notes、Decisions-so-far 和 Fog。
- **Child ticket**：优先使用 GitHub sub-issue；不可用时，在 Map 的任务列表中引用，并在 Child 顶部写入 `Part of #<map>`。使用 `wayfinder:<type>` 标签，其中 type 为 `research`、`prototype`、`grilling` 或 `task`。
- **Blocking**：优先使用 GitHub 原生 Issue dependencies。创建依赖时使用 blocker 的数据库数字 ID，而不是 Issue 编号或 `node_id`；不可用时，在 Child 顶部写入 `Blocked by: #<n>, #<n>`。
- **Frontier query**：按 Map 顺序列出未关闭 Child，排除仍有开放 blocker 或已有 assignee 的项，选择首个剩余项。
- **Claim**：`gh issue edit <n> --add-assignee @me`，这是会话的第一次写操作。
- **Resolve**：评论结论、关闭 Child，并在 Map 的 Decisions-so-far 中追加上下文链接。

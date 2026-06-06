# Issue tracker：GitHub

本仓库的 Issue 和 PRD 使用 GitHub Issues 管理。所有操作使用 `gh` CLI。

## 约定

- **创建 Issue**：使用 `gh issue create --title "..." --body "..."`。多行正文使用 heredoc。
- **读取 Issue**：使用 `gh issue view <number> --comments`，并通过 `jq` 筛选评论和获取标签。
- **列出 Issue**：使用 `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，按需添加 `--label` 和 `--state` 筛选条件。
- **评论 Issue**：使用 `gh issue comment <number> --body "..."`。
- **添加或移除标签**：使用 `gh issue edit <number> --add-label "..."` 或 `gh issue edit <number> --remove-label "..."`。
- **关闭 Issue**：使用 `gh issue close <number> --comment "..."`。

在仓库克隆目录中运行命令时，`gh` 会自动从 `git remote -v` 推断仓库。

## 当技能要求“发布到 issue tracker”时

创建一个 GitHub Issue。

## 当技能要求“获取相关 ticket”时

运行 `gh issue view <number> --comments`。

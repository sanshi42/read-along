# AGENTS.md

## 项目概览

- Read Along 是本地优先的个人 Web App，把单篇网页或文本型 PDF 转成可朗读、可断点续读的阅读材料。
- 后端使用 Python 3.12、FastAPI、Typer、SQLModel、SQLite 和 uv。
- 前端使用 React 19、Vite、TypeScript、React Router、lucide-react 和 npm。
- 默认本地 TTS 后端是 Sherpa ONNX Kokoro；在线 TTS 只作为用户显式配置的可选后端。

## 常用命令

```bash
make setup          # 安装依赖并安装 pre-commit hook
make dev            # 同时启动 API 和 Web
make dev-api        # 只启动 FastAPI
make dev-web        # 只启动 Vite
make check          # 本地快速完整门禁
make check-browser  # 真实浏览器烟测
make format         # 格式化 Python 和渐进式 Web 文件
make pre-commit     # 全量运行 pre-commit
```

后端默认监听 `http://127.0.0.1:8765`，前端默认监听 `http://127.0.0.1:5173`。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `src/read_along/api.py` | FastAPI 路由和 HTTP 错误映射 |
| `src/read_along/material_library.py` | 材料库对外门面 |
| `src/read_along/material_views.py` | 阅读材料摘要、详情、导航和播放位置装配 |
| `src/read_along/material_audio.py` | 句子音频缓存和生成流程 |
| `src/read_along/repository.py` | SQLite repository |
| `src/read_along/importers.py` | URL/PDF 导入入口 |
| `src/read_along/tts/` | TTS 配置、下载和后端适配器 |
| `web/src/api.ts` | 前端 API 类型和 fetch 封装 |
| `web/src/routes/ReaderPage.tsx` | 阅读页页面组合，当前前端架构热点 |
| `web/src/routes/readerPlaybackSession.ts` | 阅读页临时朗读状态机 |
| `web/smoke/` | Playwright 浏览器烟测 |

更完整的系统说明见 `docs/architecture.md`、`docs/code-layout.md`、`docs/testing.md` 和 `docs/frontend-guidelines.md`。

## 工程规则

- 新增或修改行为时优先测试先行；bug 修复应添加能复现问题的回归测试。
- Python 使用 Ruff、Pyrefly 和 pytest；Web 使用 TypeScript strict mode、Biome、Node.js test runner 和 Playwright smoke tests。
- 前端 Biome formatter 当前渐进接入，只覆盖 smoke/config/manifest 文件；不要把全量格式化和功能改动混在一起。
- TypeScript 不使用 `any`，优先使用 `unknown`、明确类型或泛型。
- 保持 `MaterialLibrary`、REST API、CLI、数据库 schema 和前端 API 类型的公开行为稳定；内部拆分不得改变这些接口。
- 涉及阅读页 UI 时，优先保持现有 class name、可访问名称、键盘操作和移动端布局稳定。

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

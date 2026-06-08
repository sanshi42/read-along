# Vibe Coding 起始 Prompt

你是参与本项目的开发 Agent。开始任何实现前，先阅读本提示词和项目输入文档，确认当前任务边界，再按单任务规则推进。

## 必读输入

先阅读以下文件，并以它们作为事实来源：

- `AGENTS.md`
- `tasks/progress.md`
- `docs/mvp-scope.md`
- `docs/product-backlog.md`
- `docs/tech-design.md`
- `docs/sprint-plan.md`
- 当前任务目录下的 `tasks/<task-id>/task-spec.md`

如果这些文档之间冲突，优先级为：

1. `docs/mvp-scope.md`
2. 当前任务 `task-spec.md`
3. `AGENTS.md`
4. `docs/tech-design.md`
5. `docs/product-backlog.md`
6. `docs/sprint-plan.md`
7. `tasks/progress.md`

## 当前工程理解

仓库和应用名均为 `Read Along`，技术标识使用 `read-along` / `read_along`。这是一个完整应用，不以可复用 Python 库为产品目标。

- macOS 优先的个人本地 Web App。
- 用户导入单篇网页 URL 或文本型 PDF。
- 系统清洗正文，按段落和句子结构化保存。
- 默认用 macOS `say` 生成句子级音频。
- 前端提供阅读、播放、暂停、上一句、下一句、倍速、当前句高亮和进度恢复。
- 不保存 Cookie、账号密码或导出的浏览器凭据。
- 不绕过登录或付费权限。
- 不做批量课程抓取、OCR、LLM 总结/改写、多端同步、公网部署。
- 不保留旧名称或旧学习笔记功能的兼容层。
- Chrome 会话桥接属于通用网页导入基础设施。
- 得到专用规则作为来源适配器放在 `src/read_along/sources/dedao.py`。

## 技术方向

后端：

- 使用扁平 Python 应用包 `src/read_along/`。
- 使用 FastAPI + Uvicorn。
- 默认监听 `127.0.0.1:8765`。
- 本地数据默认放在 `~/.local/share/read-along/`。
- 存储使用 SQLite 和本地文件目录，不引入 SQLAlchemy。
- PDF 使用 PyMuPDF。
- 网页导入使用 Scrapling；登录态页面通过用户手动登录的专用 Chrome 会话桥接读取可见正文。
- TTS 先实现 macOS `say` 适配器，保留后续本地神经 TTS 适配接口。

前端：

- 新增在 `web/`。
- 使用 Vite + React + TypeScript。
- MVP 不引入复杂状态库，优先使用 React hooks 和局部状态。
- 页面至少包括书架页、导入入口、阅读页和播放器区域。

命令形态：

```bash
make dev
```

运行 Python 项目命令时优先使用 uv 默认 editable mode，例如 `uv run ...`；仅部署或打包场景考虑 `--no-editable`。

## 多 Agent 开发方式

后续开发会使用多 Agent 协作。所有 Agent 必须遵守以下规则：

- 一次只实现一个最小任务，不在同一轮混合多个 backlog 项或无关重构。
- 每个任务必须先创建或更新 `tasks/<task-id>/task-spec.md`。
- 每个 Agent 开始前必须读取“必读输入”和当前任务规格。
- Agent 之间通过任务目录、`tasks/progress.md` 和最终变更说明交接上下文。
- 不要假设其他 Agent 的未提交计划已经完成，只相信仓库里的文件和可运行检查结果。
- 如果发现当前任务范围变大，拆出后续任务，不扩大当前任务。
- 如果发现需求超出 `docs/mvp-scope.md`，默认写入 backlog 或 deferred，不直接实现。
- 不要覆盖其他 Agent 或用户已经做出的无关改动。

建议多 Agent 角色分工：

- Orchestrator Agent：选择下一个最小任务，维护 `task-spec.md`、`tasks/progress.md` 和 backlog 状态。
- Backend Agent：实现 FastAPI、SQLite、导入、TTS、文件服务和后端测试。
- Frontend Agent：实现 React 阅读器、播放器、状态持久化和前端测试。
- QA Agent：补齐 `pytest`、`ruff`、`pyrefly`、前端构建/测试和手动验收脚本。
- Reviewer Agent：检查范围漂移、安全边界、测试缺口和文档同步。

同一任务内可以由多个 Agent 协作，但必须有一个任务负责人保持范围一致，并在任务完成时统一更新 `tasks/progress.md`。

## 当前推荐起点

以 `tasks/progress.md` 为准，选择其中列出的下一个最小任务。不要根据历史任务规格重复实现已经完成的工作。

## 任务执行流程

每个任务按这个顺序推进：

1. 阅读必读输入。
2. 确认当前任务 ID、backlog 引用、目标、范围和非目标。
3. 创建或更新 `tasks/<task-id>/task-spec.md`。
4. 做最小实现。
5. 增加与风险匹配的测试。
6. 运行质量检查。
7. 更新 `tasks/progress.md`。
8. 汇报完成内容、验证结果、遗留风险和下一步建议。

## 测试与质量门槛

后续测试会加入 `ruff` 和 `pyrefly` 检测。每个代码任务都要尽量满足以下检查：

```bash
uv run pytest
uv run ruff check .
uv run pyrefly check
```

如果 `ruff` 或 `pyrefly` 尚未加入项目依赖或配置，负责相关基线任务的 Agent 应更新 `pyproject.toml`，把它们加入 dev 依赖并提供合理的最小配置。不要只在口头说明里假设它们存在。

后续如果前端已经创建，还应根据实际脚本运行：

```bash
npm run build
npm test
```

如果某项检查因为环境限制无法运行，必须明确说明原因，并保留可复现的命令。

## 实现边界

必须坚持：

- MVP 只做个人本地 macOS Web App。
- 只处理单篇网页或文本型 PDF。
- 只处理用户有权访问的内容。
- 登录态网页只通过用户手动登录的专用 Chrome 会话桥接读取可见正文。
- 不保存 Cookie、账号密码或导出的浏览器凭据。
- 不调用隐藏接口绕过访问限制。
- 不保存或导出可公开分发的课程包。
- 第一版不使用 LLM 改写、总结或出题。
- 第一版不做 OCR、批量抓取、多端同步、账号系统、公网部署。

## 开发取舍

优先做简单、可验证、可回滚的实现：

- 用 SQLite 标准库或轻量封装，不引入 ORM。
- 用规则清洗和句子切分，不引入 LLM。
- 用句子级音频文件换取高亮、跳句和缓存简单性。
- 用 `say` 先跑通本地 TTS，再保留适配器扩展点。
- 前端先完成核心阅读和播放闭环，再做视觉打磨。

不要提前实现 deferred 项，也不要为了未来扩展引入复杂框架。

## 完成定义

一个任务只有同时满足以下条件才算完成：

- 当前 `task-spec.md` 的 acceptance criteria 已满足，或未满足项已明确写成阻塞/后续任务。
- 有必要的自动测试或明确的不可自动测试说明。
- 已运行适用的质量检查，至少包括 `pytest`；如果已配置，则包括 `ruff` 和 `pyrefly`。
- 没有扩大到当前任务非目标。
- `tasks/progress.md` 已更新。
- 最终说明列出改动文件、验证命令和剩余风险。

## 首轮给开发 Agent 的启动指令

请先读取 `tasks/progress.md`，选择其中推荐的下一个最小任务。创建对应 `task-spec.md` 后再实现，完成后运行适用检查并更新进度。

# Project Progress

最后更新：2026-06-07

## 当前状态

项目已进入 MVP Sprint 1 的 PDF 导入阶段。`MVP-001` `MVP-002` `MVP-003` `MVP-004` 均已完成。PDF 上传、PyMuPDF 文本提取、段落/句子结构化导入的完整流程已打通。Sprint 1 的下一个目标是 `MVP-005` 文本结构化。

## 已完成

| Task ID | Task | Status | Output |
| --- | --- | --- | --- |
| 000 | 建立单任务推进工作流 | Done | `AGENTS.md`、`tasks/progress.md`、`tasks/000-project-workflow/task-spec.md` |
| 001 | Read Along 后端服务骨架 | Done | `src/read_along/`、`read-along serve`、`GET /api/health`、`tasks/001-reader-service-skeleton/task-spec.md` |
| 002 | 统一为 Read Along | Done | 全仓库改名、扁平 Python 包、旧功能清理、得到来源适配器 |
| 003 | GitHub 提交前检查 | Done | 规范化 `AGENTS.md`、修复 Chrome 正文候选选择、验证项目基线 |
| 004 | 配置与本地存储路径 | Done | `READ_ALONG_HOME` 配置、默认数据目录、SQLite/上传/音频/日志路径 |
| 005 | SQLite schema 初始化 | Done | SQLite 连接、五张核心表、索引、外键和幂等初始化 |
| 006 | 核心数据 Repository 基线 | Done | 材料、段落、句子和阅读进度的持久化读写与顺序查询 |
| 007 | 核心数据模型 DTO | Done | 核心 Pydantic DTO、状态枚举、材料详情嵌套结构、repository 类型返回 |
| 008 | 稳定内容 ID 生成 | Done | `ids.py` 确定性 ID 生成、material/paragraph/sentence ID、21 个自动测试 |
| 009 | PDF 导入 | Done | `extractors.py` 文本提取与切分、`importers.py` PDF 导入流程、`POST /api/import/pdf`、29 个测试 |

## 当前任务

无。`009-pdf-import` 已完成。

## 下一步

`MVP-004` PDF 导入已完成。建议继续 Sprint 1 的下一个最小任务：

1. `010-text-structuring`：实现通用文本结构化——改进段落检测、噪声清理、句子边界检测，为 URL 导入做准备。

推荐先完成 `010-text-structuring`，它依赖 MVP-003 数据模型，是 Sprint 1 从 PDF 导入通向通用文本导入的桥梁。

## 阻塞项

无。

## 最近变更记录

- 2026-06-07：完成 PDF 导入，新增 `extractors.py`（文本清洗、段落/句子切分、PDF 页文本提取）、`importers.py`（PDF 导入流程）、`POST /api/import/pdf` API 端点，29 个测试，ruff+mypy 全部通过。
- 2026-06-07：完成稳定内容 ID 生成，新增 `ids.py` 提供材料/段落/句子的确定性 ID 生成函数，覆盖 21 个测试。
- 2026-06-06：完成核心数据模型 DTO，新增状态枚举和材料详情嵌套结构，并让 repository 读取结果返回正式模型。
- 2026-06-06：完成核心数据 repository，支持材料、段落、句子和阅读进度的持久化读写、顺序查询与进度覆盖更新。
- 2026-06-06：完成 SQLite schema 初始化，新增五张核心表、必要索引、外键约束、级联删除和持久化测试。
- 2026-06-06：完成本地数据目录配置和存储路径布局，支持 `READ_ALONG_HOME` 覆盖，并新增目录创建测试。
- 2026-06-06：将项目级规则文件规范化为 `AGENTS.md`，并完成首次 GitHub 提交前检查。
- 2026-06-06：修复 Chrome 页面正文候选总被整页 `body` 覆盖的问题，并新增回归测试。
- 2026-06-06：项目统一改名为 Read Along；包结构扁平化为 `src/read_along/`；CLI 改为 `read-along serve`。
- 2026-06-06：删除旧学习笔记流水线、Ollama 依赖、相关测试、样例和输出；保留 Chrome 桥接并新增得到来源适配器。
- 2026-06-06：API 测试显式依赖 `httpx2`；pytest、ruff、mypy 和非 editable CLI 入口验证通过。
- 2026-06-05：完成 `001-reader-service-skeleton`，新增 Read Along FastAPI app、健康检查、`serve` CLI 和测试。
- 2026-06-05：新增 `fastapi`、`uvicorn` 运行依赖，以及 `ruff`、`mypy` 质量检查配置。
- 2026-06-05：新增根目录项目协作规则文件，后续规范化为 `AGENTS.md`。
- 2026-06-05：新增 `tasks/progress.md`，记录当前进度、已完成任务和下一步。
- 2026-06-05：新增 `tasks/000-project-workflow/task-spec.md`，记录本次文档工作流任务规格。

## 维护规则

- 每完成一个任务，都必须更新"已完成""当前任务""下一步"和"最近变更记录"。
- 如果任务未完成，必须在"当前任务"或"阻塞项"说明原因。
- 如果创建新任务，必须先创建对应的 `tasks/<task-id>/task-spec.md`。
- 如果 backlog 状态变化，需要同步更新 `docs/product-backlog.md`。

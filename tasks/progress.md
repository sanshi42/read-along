# Project Progress

最后更新：2026-06-07

## 当前状态

Sprint 1 全部七个任务均已完成，阅读页正文展示已落地，结构化正文可按段落和句子阅读。下一步进入 Sprint 2：网页导入与得到单篇支持。

## 已完成

| Task ID | Task | Status | Output |
| --- | --- | --- | --- |
| 000 | 建立单任务推进工作流 | Done | `AGENTS.md`、`tasks/progress.md`、`tasks/000-project-workflow/task-spec.md` |
| 001 | Read Along 后端服务骨架 | Done | `src/read_along/`、`read-along serve`、`GET /api/health` |
| 002 | 统一为 Read Along | Done | 全仓库改名、扁平 Python 包、旧功能清理、得到来源适配器 |
| 003 | GitHub 提交前检查 | Done | 规范化 `AGENTS.md`、修复 Chrome 正文候选选择、验证项目基线 |
| 004 | 配置与本地存储路径 | Done | `READ_ALONG_HOME` 配置、默认数据目录、SQLite/上传/音频/日志路径 |
| 005 | SQLite schema 初始化 | Done | SQLite 连接、五张核心表、索引、外键和幂等初始化 |
| 006 | 核心数据 Repository 基线 | Done | 材料、段落、句子和阅读进度的持久化读写与顺序查询 |
| 007 | 核心数据模型 DTO | Done | 核心 Pydantic DTO、状态枚举、材料详情嵌套结构、repository 类型返回 |
| 008 | 稳定内容 ID 生成 | Done | `ids.py` 确定性 ID 生成、material/paragraph/sentence ID、21 个测试 |
| 009 | PDF 导入 | Done | `extractors.py`、`importers.py`、`POST /api/import/pdf`、29 个测试 |
| 010 | 文本结构化 | Done | 增强 `extractors.py`（噪声清洗、长句切分、噪声过滤）、`structure_text` 管线、改进段落检测、21 个新测试 |
| 011 | 深化材料库持久化 Module 设计 | Done | `CONTEXT.md`、材料库 Interface、多来源身份、稳定来源键、原子保存与错误语义、技术方案更新 |
| 012 | 统一代码与测试说明文本为中文 | Done | `src/` 与 `tests/` 中文说明文本、CLI/API 用户文案、PDF 中文来源标签、104 个测试 |
| 013 | 实现材料库持久化 Module | Done | `MaterialLibrary`、Draft、多来源身份、原子保存、读取、进度、删除、PDF 导入接入 |
| 014 | 前端骨架 | Done | React + Vite + TypeScript、真实书架页、阅读页入口、材料只读 API |
| 015 | 阅读页正文展示 | Done | 阅读页段落/句子渲染、可定位句子节点、可点击句子、sticky 导航、正文排版 |

## 当前任务

无。`015-reader-page` 已完成。

## 下一步

Sprint 1 全部完成。进入 Sprint 2：网页导入与得到单篇支持：

1. `MVP-013` 网页导入：输入公开网页 URL 抽取正文导入阅读器。

## 阻塞项

无。

## 最近变更记录

- 2026-06-07：完成阅读页正文展示；阅读页按段落和句子渲染结构化正文，句子节点可定位可点击，sticky 导航，正文排版落地，115 个测试通过。
- 2026-06-07：完成前端骨架；新增 React + Vite + TypeScript、真实书架页、阅读页入口和材料只读 API，浏览器验收通过，115 个测试通过。
- 2026-06-07：完成材料库持久化 Module；新增 Draft、多来源身份、稳定来源键、原子保存、读取、进度和删除，并将 PDF 导入接入材料库，111 个测试通过。
- 2026-06-07：开始实现材料库持久化 Module；范围包含 Draft、多来源身份、原子保存、读取、进度、删除和 PDF 导入接入。

- 2026-06-07：完成代码与测试说明文本中文化；翻译注释、docstring、内部错误、CLI/API 用户文案和 PDF 来源标签，保留协议契约、代码标识符、英文测试夹具和第三方原始错误，104 个测试通过。
- 2026-06-07：开始统一代码与测试说明文本为中文；明确保留代码标识符、协议固定值、英文处理测试夹具和第三方原始错误。
- 2026-06-06：完成材料库持久化 Module 设计，收敛 Draft、外部 Interface、多来源身份、稳定来源键、成功材料模型、重复导入、原子保存、读取、进度、删除、源文件所有权和错误模式。
- 2026-06-06：开始深化材料库持久化 Module 设计；确认该 Module 拥有完整持久化生命周期，`content_hash` 基于结构化正文计算，并新增领域词汇表。
- 2026-06-07：完成文本结构化，增强 `extractors.py`（`clean_text` 噪声清洗、长句逗号切分、单字/纯符号句过滤、`structure_text` 管线），`import_pdf` 改用逻辑段落拆分，新增 21 个测试，102 全量通过。
- 2026-06-07：完成 PDF 导入，新增 `extractors.py`（文本清洗、段落/句子切分、PDF 页文本提取）、`importers.py`（PDF 导入流程）、`POST /api/import/pdf` API 端点，29 个测试。
- 2026-06-07：完成稳定内容 ID 生成，新增 `ids.py` 提供材料/段落/句子的确定性 ID 生成函数，覆盖 21 个测试。
- 2026-06-06：完成核心数据模型 DTO，新增状态枚举和材料详情嵌套结构，并让 repository 读取结果返回正式模型。
- 2026-06-06：完成核心数据 repository，支持材料、段落、句子和阅读进度的持久化读写、顺序查询与进度覆盖更新。
- 2026-06-06：完成 SQLite schema 初始化，新增五张核心表、必要索引、外键约束、级联删除和持久化测试。
- 2026-06-06：完成本地数据目录配置和存储路径布局，支持 `READ_ALONG_HOME` 覆盖，并新增目录创建测试。
- 2026-06-06：将项目级规则文件规范化为 `AGENTS.md`，并完成首次 GitHub 提交前检查。
- 2026-06-06：修复 Chrome 页面正文候选总被整页 `body` 覆盖的问题，并新增回归测试。
- 2026-06-06：项目统一改名为 Read Along；包结构扁平化为 `src/read_along/`；CLI 改为 `read-along serve`。
- 2026-06-05：完成 `001-reader-service-skeleton` 等早期任务。

## 维护规则

- 每完成一个任务，都必须更新"已完成""当前任务""下一步"和"最近变更记录"。
- 如果任务未完成，必须在"当前任务"或"阻塞项"说明原因。
- 如果创建新任务，必须先创建对应的 `tasks/<task-id>/task-spec.md`。
- 如果 backlog 状态变化，需要同步更新 `docs/product-backlog.md`。

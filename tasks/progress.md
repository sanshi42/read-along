# Project Progress

最后更新：2026-06-13

## 当前状态

数据库兼容策略已精简。应用只创建新数据库或接受当前真实六表结构；其他现有数据库保持不变并拒绝启动，不再自动识别、修复、备份或接管历史结构。

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
| 016 | 公开网页 URL 导入 | Done | Scrapling 抓取公开网页、URL 导入 API、书架导入表单、121 个测试 |
| 017 | 得到单篇 URL 抽取目标验证 | Done | `scrapling[fetchers]` 依赖、得到 URL 清洗接入、目标 URL 直抓边界确认、123 个测试 |
| 018 | 修复公开网页和得到 Chrome 导入失败 | Done | 文档正文容器优先抽取、Chrome 标签页 query/path 重试、前台 Chrome fallback、目标公开 URL 复验、127 个测试 |
| 019 | 开发工具链基线 | Done | `Makefile`、pre-commit local hooks、Pyrefly 迁移、Ruff 规则、uv editable mode 开发命令 |
| 020 | 修复真实本地环境 URL 导入回归 | Done | 导入方式 UI 恢复、Chrome 目标标签页选择、旧库 schema 迁移与残留外键修复、公开网页和得到单篇 URL 验证、131 个测试 |
| 023 | 设计 SQLModel 数据库架构与迁移方案 | Done | SQLModel/Alembic 职责、已知 schema 指纹、无损接管、启动迁移、备份策略和五步实施拆分 |
| 024 | 建立 SQLModel 与 Alembic baseline | Done | SQLModel 表模型、`UTCDateTime`、Alembic baseline revision、真实 SQLite schema/metadata 一致性测试、143 个测试 |
| 025 | 精简数据库 schema 启动校验 | Done | 删除历史自动修复与诊断，非当前真实六表数据库拒绝启动，146 个测试 |

## 当前任务

无。`025-historical-schema-diagnostics` 已按精简范围完成。

## 下一步

1. 继续 Sprint 2：用已登录 Chrome 复验目标得到单篇 URL，通过后将 `MVP-014` 标记为 `Done`。
2. 补齐 `MVP-015` 的清晰重复导入反馈。

## 阻塞项

无代码阻塞。

## 最近变更记录

- 2026-06-13：完成数据库 schema 启动校验精简；撤回历史诊断提交，删除旧库自动迁移、半迁移修复、诊断模块和诊断命令，只接受新库或当前真实六表结构，真实默认库冒烟校验和 `make check` 通过。
- 2026-06-13：撤回复杂历史 schema 诊断方向，开始在同一 `025` 任务内精简为当前真实六表启动校验；删除旧库自动修复、独立诊断和后续自动接管计划，不新增任务序号。
- 2026-06-10：完成 SQLModel 与 Alembic baseline；新增 `UTCDateTime`、六张业务表的 SQLModel 实体、Alembic 配置和 baseline revision，真实文件 SQLite 测试覆盖 metadata/schema 一致性、特殊约束和 UTC 时间跨 Session 读取；生产启动和 Repository 未切换，`make check` 通过。
- 2026-06-10：完成 SQLModel 数据库架构设计；补齐已知 schema 状态、五步实施拆分和下一最小任务，修正技术方案中“不引入 SQLAlchemy”的旧取舍，并删除已过时的起始 prompt。
- 2026-06-09：开始设计 SQLModel 数据库架构；确认采用 SQLModel 描述运行时表模型、Alembic 管理 schema 演进，并要求无损接管全部现有本地数据库和已知旧 schema。
- 2026-06-09：确认应用启动时自动执行 Alembic 迁移；存在待执行迁移时先备份 SQLite 文件，迁移失败拒绝启动，新数据库同样通过 Alembic 创建。
- 2026-06-09：确认 SQLModel 数据库表模型与领域/API DTO 分离；Repository 负责转换，API 和材料库外部调用方不直接操作数据库实体。
- 2026-06-09：确认数据库继续作为关键结构不变量的最终防线；保留唯一约束、部分唯一索引、复合外键、级联删除和 `CHECK` 约束，特殊约束通过显式 Alembic revision 和 schema 测试保证。
- 2026-06-09：确认材料库 Module 持有 SQLModel `Session` 和事务边界；Repository 只执行细粒度读写，不自行提交、回滚或关闭 Session，API 不直接操作业务 Session。
- 2026-06-09：确认完整材料读取采用显式 SQLModel 查询并在 Session 内组装 DTO；不依赖 Relationship 默认懒加载，避免 N+1 查询和脱离 Session 的数据库实体。
- 2026-06-09：确认数据库时间字段迁移为 UTC `datetime`，API 保持 ISO 8601 表现，旧时间文本严格解析；识别到 SQLite 不原生保存时区，后续需明确 UTC 适配方式。
- 2026-06-09：确认通过 SQLAlchemy `UTCDateTime` TypeDecorator 保证 SQLite 时间语义；拒绝无时区值，写入转换为 UTC，读取恢复 UTC 时区。
- 2026-06-09：确认保留全部现有字符串稳定 ID 和材料库生成权；不改用自增整数、UUID 或隐藏代理主键，保持数据、缓存路径和前端定位兼容。
- 2026-06-09：确认枚举字段使用 Python `StrEnum` 和 SQLite 字符串列加显式 `CHECK`；不使用 SQLAlchemy 原生 Enum，允许值变化必须经过 Alembic migration。
- 2026-06-10：确认删除级联由 SQLite 外键执行，ORM Relationship 使用 `passive_deletes=True`，并通过 Engine 连接事件确保每个连接启用外键约束。
- 2026-06-10：确认材料库写操作保留 `BEGIN IMMEDIATE`，SQLite 启用 WAL 并设置 5 秒 `busy_timeout`；耗时准备工作尽量移到写锁前，最终文件重命名继续与事务提交协调。
- 2026-06-10：确认迁移备份使用 SQLite backup API，仅在存在待执行 migration 时创建；成功迁移前备份保留最近 3 个，失败迁移备份永久保留，schema 迁移不备份源文件和音频。
- 2026-06-10：确认历史接管编排器严格识别已知历史 schema；未知或损坏状态生成备份和具体诊断后拒绝迁移与启动，不进行猜测性修复或静默丢弃数据。
- 2026-06-10：确认使用启动迁移编排器接管历史库并标记 SQLModel baseline；Alembic revision 链保持干净，只负责 baseline 及后续正常 schema 演进。
- 2026-06-10：确认业务运行时代码禁止裸 SQL；历史接管、Alembic、SQLite PRAGMA、`BEGIN IMMEDIATE` 和必要 schema 校验可在数据库基础设施中受控使用。
- 2026-06-10：确认 `import_jobs` 仅纳入 SQLModel baseline schema 和历史数据无损迁移；本次重构不新增导入任务业务 Repository 或 API。
- 2026-06-10：确认所有数据库集成测试必须通过生产迁移编排器和 Alembic 创建真实文件 SQLite；禁止 `create_all()` 和内存数据库绕过真实路径，并检查 metadata/schema 漂移。
- 2026-06-10：确认 SQLModel 表模型只声明服务于所有权和被动删除的最小 Relationship；不建立完整 ORM 对象图，不通过 relationship cascade 保存整篇材料。
- 2026-06-09：整体修复真实本地环境 URL 导入回归；书架页恢复公开网页/已登录 Chrome 两种导入方式，Chrome fallback 可按目标 URL 搜索所有普通标签页；新增旧 `materials` 单表迁移并修复 `material_sources` 残留旧外键；公开网页在临时库、真实默认库和当前 API 导入成功，得到单篇 Chrome 模式在临时库完整导入成功，in-app browser 验证 UI，`make check` 全量通过。
- 2026-06-08：完成开发工具链基线；开发命令改为 uv 默认 editable mode，新增 `Makefile` 一键启动和检查入口，新增 pre-commit local hooks，使用 `pyrefly init` 从 mypy 自动迁移到 Pyrefly 并移除 mypy，配置 Ruff isort、Google docstring 和 single quote，`make dev` 冒烟验证通过，`make check` 全量通过。
- 2026-06-08：修复公开网页和得到 Chrome 导入失败；在 `main` 上恢复 `mode=chrome` 导入路径，公开网页优先抽取 `.prose` 等正文容器，得到 Chrome 标签页先按完整 query 匹配、再按 host/path 重试，DevTools 不可用时回退读取前台 Chrome 标签页并校验 host/path；真实 01MVP URL 导入成功，新增回归测试，`MVP-014` 进入 `Review`。
- 2026-06-07：完成指定得到单篇 URL 的 URL-only 抽取验证；补齐 Scrapling fetchers 依赖，得到 URL 导入前接入专用清洗，目标 URL 直抓确认返回 SPA 空壳无正文，新增明确错误提示，123 个测试通过，Ruff、mypy 和前端构建通过。
- 2026-06-07：完成公开网页 URL 导入；新增 Scrapling 抓取和正文候选抽取、`POST /api/import/url`、书架页 URL 导入表单，`MVP-013` 标记完成，121 个测试通过，Ruff、mypy、前端构建和浏览器验收通过。
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

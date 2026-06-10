# Task ID

`023-sqlmodel-database-architecture`

# Task title

设计 SQLModel 数据库架构与迁移方案

# Backlog reference

- MVP-002：本地存储
- MVP-003：数据模型
- 支撑后续所有需要持久化的 MVP 故事

# Goal

参照 FastAPI 最佳实践项目，重新设计数据库持久化部分，使 SQLModel 成为表结构和查询模型的主要描述方式，Alembic 成为 schema 演进机制，并确保现有本地数据库无损迁移。

# Scope

- 明确 SQLModel 表模型、领域 DTO、Session、事务和材料库 Module 的职责边界。
- 明确 Alembic 接管当前 schema 和已知旧 schema 的迁移策略。
- 明确应用启动、数据库备份和迁移失败时的行为。
- 明确从裸 SQL 实现迁移到 SQLModel 的任务拆分与验收方式。
- 更新相关技术设计和必要 ADR。

# Non-goals

- 本任务不实现 SQLModel 表模型或 Alembic 迁移。
- 不修改当前 SQLite 数据。
- 不改变材料库领域语义、API 契约或 MVP 范围。
- 不顺带实现导入任务、TTS、播放器或其他 backlog 项。

# Implementation notes

- 现有本地数据库及全部已知旧 schema 数据必须无损保留。
- SQLModel 应成为运行时表模型和查询的主要描述方式。
- SQLModel 数据库表模型与材料库领域/API DTO 分离：`db_models.py` 只放数据库实体，`models.py` 保留领域模型和 API DTO。
- Repository 负责数据库实体与领域模型之间的转换，API 不直接暴露数据库实体。
- 材料库 Module 的公开操作拥有 SQLModel `Session` 和事务边界；Repository 不得自行提交、回滚或关闭 `Session`。
- API 只调用材料库公开 Interface，不直接注入或操作业务 `Session`。
- 完整材料读取使用显式 SQLModel 查询并在 Session 内组装 DTO，不依赖 Relationship 默认懒加载，避免 N+1 查询和脱离 Session 的实体。
- SQLModel 表模型只声明最小 Relationship，不建立完整对象图，也不通过 relationship cascade 保存整篇材料。
- 数据库继续强制全部关键结构不变量，包括唯一约束、部分唯一索引、复合外键、级联删除和 `CHECK` 约束。
- SQLModel 无法可靠自动生成的约束必须在 Alembic revision 中显式定义，并通过真实 SQLite schema 测试验证。
- 时间字段迁移为带 UTC 时区语义的 `datetime`；API 保持 ISO 8601 表现，桥接迁移严格解析现有时间文本。
- SQLite 时间字段统一使用 SQLAlchemy `TypeDecorator` 类型 `UTCDateTime`，拒绝无时区值并保证读回带 UTC 时区。
- 保留现有字符串稳定 ID 和材料库生成权，不引入自增整数、UUID 或隐藏代理主键。
- 枚举字段使用 Python `StrEnum` 和 SQLite 字符串列加显式 `CHECK`，不使用 SQLAlchemy 原生 `Enum` 类型。
- 删除级联由 SQLite 外键执行，Relationship 使用 `passive_deletes=True`；每个 Engine 连接必须启用 `PRAGMA foreign_keys = ON`。
- 材料库写操作保留 `BEGIN IMMEDIATE`；SQLite 启用 WAL，并设置 5 秒 `busy_timeout`。
- 哈希计算和临时文件复制尽量在写锁前完成，最终文件重命名继续与数据库提交协调。
- Alembic 应成为唯一 schema 创建和演进机制。
- 需要提供桥接迁移，接管最早期单表 schema、当前六表 schema，以及已知的半迁移状态。
- 桥接迁移使用明确 schema 指纹识别已知历史状态；未知或损坏状态生成备份和诊断后停止，不做猜测性修复。
- 使用启动迁移编排器接管历史库并标记 baseline；Alembic revision 链只负责 baseline 及后续正常 schema 演进。
- 业务运行时代码禁止裸 SQL；仅数据库基础设施和迁移允许受控使用，并要求集中、参数化、说明原因和测试覆盖。
- `import_jobs` 仅纳入 SQLModel schema 和无损迁移，不在本次重构中新增业务 Repository 或 API。
- 所有数据库集成测试必须使用生产迁移编排器和 Alembic 创建真实文件 SQLite；禁止 `create_all()` 和内存数据库绕过真实路径。
- 应用启动时自动执行迁移；有待执行迁移时先备份 SQLite 文件，迁移失败则拒绝启动。
- 迁移备份使用 SQLite backup API，仅在有待执行迁移时创建；成功备份保留最近 3 个，失败迁移备份永久保留。
- 新数据库同样通过 Alembic 创建，不使用 `SQLModel.metadata.create_all()`。
- 迁移成功后移除 `db.py` 中手写 schema 创建和修复逻辑。

# Acceptance criteria

- 技术方案明确 SQLModel、Session、Alembic 和材料库 Module 的职责。
- 技术方案明确材料库拥有事务边界，Repository 不自行提交。
- 技术方案明确数据库表模型与领域/API DTO 的分离边界。
- 技术方案明确完整视图的显式查询、DTO 组装和关系加载策略。
- 技术方案明确最小 Relationship 和显式持久化策略。
- 技术方案明确现有数据库无损迁移、备份和失败行为。
- 技术方案明确应用启动时自动迁移，新库和旧库使用同一条 Alembic 演进路径。
- 技术方案明确迁移备份位置、一致性、创建时机、保留和清理策略。
- 设计覆盖 SQLite 外键、复合约束、部分唯一索引和旧 schema 接管。
- 设计明确已知 schema 指纹、异常数据诊断和未知状态拒绝策略。
- 设计明确历史接管编排器与常规 Alembic revision 链的职责边界。
- 设计明确业务查询和数据库基础设施的裸 SQL 使用边界。
- 设计明确 `import_jobs` 的 schema 接管范围与业务非目标。
- 设计明确生产与测试共用数据库创建路径，以及 metadata/schema 漂移检查。
- 设计明确数据库是关键结构不变量的最终防线。
- 设计明确时间字段的 UTC 语义、旧数据迁移和 SQLite 适配方式。
- 设计明确现有稳定 ID、缓存路径和外部引用保持兼容。
- 设计明确枚举字段的 Python 表达、数据库约束和迁移规则。
- 设计明确数据库级联删除、ORM 被动删除和 SQLite 外键启用方式。
- 设计明确 SQLite 并发、锁等待、写事务和文件操作的协调方式。
- 后续实现可以拆成独立小任务，不需要重新决定核心迁移策略。

# Test plan

- 对照 `docs/mvp-scope.md`、`docs/product-backlog.md` 和 `docs/tech-design.md` 检查范围。
- 对照当前 `db.py`、`repository.py`、`models.py` 和参考项目检查职责覆盖。
- 使用具体旧库场景检查迁移设计是否会丢失材料、来源身份、正文或进度。

# Completion notes

进行中。

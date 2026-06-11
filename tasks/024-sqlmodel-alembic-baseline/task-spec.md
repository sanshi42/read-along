# Task ID

`024-sqlmodel-alembic-baseline`

# Task title

建立 SQLModel 与 Alembic baseline

# Backlog reference

- MVP-002：本地存储
- MVP-003：数据模型
- `023-sqlmodel-database-architecture` 的数据库重构第一步

# Goal

建立可独立验证的 SQLModel 目标表模型和 Alembic baseline，使空数据库可以通过 Alembic 创建完整目标 schema，并验证真实 SQLite schema 与 SQLModel metadata 一致。

# Scope

- 添加 SQLModel 和 Alembic 运行依赖。
- 实现 SQLite 使用的 `UTCDateTime` SQLAlchemy 类型。
- 为六张现有业务表建立 SQLModel 表模型。
- 在 SQLModel metadata 中表达唯一约束、复合外键、部分唯一索引、级联删除和 `CHECK` 约束。
- 添加 Alembic 配置、环境和 baseline revision。
- 新增真实文件 SQLite 测试，验证 Alembic baseline schema、SQLModel metadata 和 `UTCDateTime` 行为。

# Non-goals

- 不切换现有 `initialize_database()` 生产启动路径。
- 不修改或接管现有本地数据库。
- 不实现历史 schema 诊断、备份或接管编排器。
- 不将现有 Repository 或材料库事务切换到 SQLModel Session。
- 不改变现有 API、领域 DTO 或材料库行为。

# Implementation notes

- `db_types.py` 只负责 SQLAlchemy 自定义数据库类型；`UTCDateTime` 拒绝无时区值，写入前转为 UTC，读出后恢复 `timezone.utc`。
- `db_models.py` 只放 `table=True` 的 SQLModel 数据库实体，不复用或替代 `models.py` 中的领域/API DTO。
- 表模型保留现有字符串稳定 ID，并对身份、哈希和枚举字段声明兼容长度。
- 枚举字段使用现有 `StrEnum` 值和字符串列，不使用 SQLAlchemy 原生 `Enum`。
- SQLModel metadata 和 baseline revision 都必须表达当前设计要求的数据库不变量。
- Relationship 只表达材料所有权和被动删除所需的最小关系，不通过 relationship cascade 保存完整材料。
- Alembic baseline 只负责从空数据库创建目标 schema；历史数据库接管属于后续任务。
- 测试通过 Alembic 在真实文件 SQLite 上建库，不使用 `SQLModel.metadata.create_all()` 或内存数据库。

# Acceptance criteria

- `pyproject.toml` 和 `uv.lock` 包含 SQLModel 与 Alembic。
- `UTCDateTime` 拒绝无时区 `datetime`，将有时区值规范化为 UTC，并在跨 Session 读取后保留 UTC 时区。
- SQLModel metadata 包含六张业务表及设计要求的列、索引、唯一约束、外键和 `CHECK` 约束。
- Alembic baseline 可以从空文件创建六张业务表和 `alembic_version`。
- Alembic 创建后的真实 SQLite schema 与 SQLModel metadata 一致。
- 现有生产启动和 Repository 仍使用当前实现，现有测试不回归。

# Test plan

- 先运行新增 SQLModel/Alembic 测试，确认在实现前因模块和配置缺失而失败。
- 运行新增定向测试，验证 baseline schema、metadata 一致性、复合约束和 `UTCDateTime` 跨 Session 行为。
- 运行 `make check`，验证后端测试、Ruff、Pyrefly 和前端构建。

# Completion notes

已完成。

- 添加 SQLModel、Alembic 和 SQLAlchemy 间接依赖并更新 `uv.lock`。
- 新增 `UTCDateTime`，拒绝无时区时间，写入时规范化为 UTC，读取时恢复 `timezone.utc`。
- 新增六张业务表的 SQLModel 数据库实体，包含命名唯一约束、复合外键、部分唯一索引、`CHECK` 约束和最小被动删除 Relationship。
- 新增 Alembic 配置、环境和 `0001_sqlmodel_baseline` revision；生产启动和现有 Repository 未切换。
- 新增真实文件 SQLite 测试，验证空库升级、revision、metadata/schema 一致性、特殊 SQLite 约束和 UTC 时间跨 Session 读取。
- `make check` 通过：Ruff、格式、Pyrefly、143 个后端测试和前端构建均成功。

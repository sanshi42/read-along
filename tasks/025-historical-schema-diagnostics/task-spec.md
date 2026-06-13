# Task ID

`025-historical-schema-diagnostics`

# Task title

精简数据库 schema 启动校验

# Backlog reference

- MVP-002：本地存储
- MVP-003：数据模型
- `023-sqlmodel-database-architecture` 的数据库兼容边界调整

# Goal

删除复杂的历史数据库识别和自动修复方向，只允许新建数据库或当前真实六表结构数据库启动；其他现有数据库保持不变并明确拒绝启动。

# Scope

- 删除 `db.py` 中旧五表迁移和半迁移自动修复代码。
- 为当前手写六表 schema 生成紧凑签名，并在打开现有数据库时严格比较。
- 新数据库继续通过当前手写六表 `SCHEMA` 创建。
- 现有数据库结构不匹配时抛出明确错误，不修改数据库文件。
- 将数据库结构错误转为清晰的 CLI 启动失败提示。
- 删除历史 schema 诊断模块、诊断命令和相关测试。
- 同步技术方案、ADR 和项目进度。

# Non-goals

- 不识别、迁移、修复或备份旧五表、半迁移、Alembic baseline 或其他非当前六表数据库。
- 不提供独立数据库诊断命令。
- 不切换生产启动到 Alembic。
- 不切换 Repository 或材料库事务到 SQLModel Session。
- 不新增任务序号。

# Implementation notes

- 当前真实六表结构以 `src/read_along/db.py` 中的 `SCHEMA` 为唯一生产兼容结构。
- schema 签名比较 `sqlite_master` 中的表、索引及标准化建表 SQL，避免维护第二份字段和约束清单。
- 仅当数据库文件不存在时创建 schema；已存在的空数据库也视为不兼容。
- 初始化失败必须保留现有数据库文件原样，并提示用户先移走或删除文件。
- SQLModel 与 Alembic baseline 保留为已完成的独立技术基线，但不自动接管现有生产数据库。

# Acceptance criteria

- 不存在数据库文件时创建当前六表结构。
- 当前真实六表数据库可重复初始化且保留数据。
- 旧五表、半迁移、已存在空数据库和被修改的六表结构均抛出 `DatabaseSchemaError`。
- 不兼容数据库初始化失败后文件内容保持不变。
- `read-along serve` 遇到不兼容数据库时输出清晰错误并返回非零退出码。
- 不再存在历史 schema 自动修复代码、独立诊断模块或 `diagnose-db` 命令。
- 现有 Repository、材料库和 API 行为不回归。

# Test plan

- 先将旧迁移测试改为拒绝启动测试，确认因 `DatabaseSchemaError` 缺失而失败。
- 运行 `uv run pytest tests/test_db.py tests/test_cli.py`，验证新库、当前六表和拒绝路径。
- 对真实默认本地数据库执行初始化冒烟检查，确认当前六表结构可接受。
- 运行 `make check`，验证后端测试、Ruff、Pyrefly 和前端构建。

# Completion notes

已完成。

- 撤回并删除复杂历史 schema 诊断模块、`diagnose-db` 命令和相关 fixture。
- 将 `db.py` 从约 414 行精简到约 140 行，删除旧五表迁移、半迁移修复及全部历史数据复制逻辑。
- 新数据库继续创建当前真实六表结构；现有数据库通过紧凑 schema 签名校验，不匹配时抛出 `DatabaseSchemaError` 并保持文件不变。
- `read-along serve` 会将数据库结构错误显示为明确启动失败信息。
- 真实默认本地数据库通过当前六表签名冒烟校验。
- 同步技术方案与 ADR，明确不再自动接管、修复、备份或迁移历史数据库。
- `make check` 通过：Ruff、格式、Pyrefly、146 个后端测试和前端构建均成功。

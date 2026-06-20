# 当前六表 schema Module Plan

## 实现方案

- 新增 schema policy Module，暴露当前 schema SQL、schema signature 读取、schema 支持判断和上一版 time-navigation schema 判断。
- 让 `initialize_database` 只负责打开数据库、创建新库和执行 policy 决策；迁移实现保留现有数据复制语义。
- 对 policy Interface 增加直接测试，覆盖当前结构、上一版 time-navigation 结构和不支持结构。
- 新增 ADR 记录 time-navigation 窄迁移是一个已经落地、受限且有备份的例外，并标注它不代表恢复通用自动迁移。

## 关键决策

- 本次保留已有窄迁移行为，因为 `docs/time-based-playback-navigation` 和现有测试已经把它作为用户数据兼容路径。
- 本次只加深 Module 和文档决策，不修改 schema 真相或 Alembic baseline。
- 兼容策略仍然只接受一个明确历史签名；未知 schema 继续拒绝启动并保持数据库文件不变。

## Topic 级验证

- 运行 schema policy 和数据库初始化相关 pytest。
- 运行 `make check`。

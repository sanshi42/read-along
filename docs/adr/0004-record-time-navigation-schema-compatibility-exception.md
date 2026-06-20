# 记录 time-navigation schema 窄迁移例外

Read Along 仍然默认不自动迁移任意历史数据库；未知结构、半迁移结构和缺少朗读完成状态的旧六表结构继续保持文件不变并拒绝启动。

作为受限例外，应用启动路径接受 time-navigation 之前的上一版真实六表结构，并在迁移前创建不覆盖旧文件的备份，然后只补齐 `sentences.audio_duration_seconds` 与 `reading_progress.sentence_offset_seconds` 两个新增字段对应的数据形态。这个例外已经由 `docs/time-based-playback-navigation/` 的 Boundary 明确纳入用户数据兼容路径，并通过 schema policy Module 的签名判断限制为唯一已知历史结构。

该例外不恢复通用自动迁移策略，不自动执行 Alembic，也不接管更旧或异常 SQLite 数据库。未来若新增 schema 兼容路径，必须再写新的 ADR，并为对应历史签名、备份语义和拒绝未知结构行为补充测试。

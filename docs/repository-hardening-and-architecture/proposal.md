---
status: done
priority: P1
created: 2026-06-29
---

# 仓库完善与架构对齐

## Goal

按“能力对齐 readest”的方式完善 Read Along 仓库，让它具备公开开源项目需要的治理文档、质量门禁、安全扫描、依赖更新和架构说明，同时保留现有 `uv + npm + Vite/FastAPI` 技术栈。

## Boundary

- 补齐 README、贡献指南、安全策略、issue 模板、Dependabot、CI、CodeQL、Scorecard、架构/测试/UI 文档和 Agent 工程规则。
- 保留现有 REST API、CLI 命令、数据库 schema、Pydantic/TypeScript API 数据结构和 npm 包管理方式。
- 后端只做不改变对外接口的内部职责拆分，优先拆 `MaterialLibrary` 的视图装配与句子音频缓存生成。
- 不迁移到 pnpm、Next.js、Vitest、Tauri 或 readest 的发布矩阵。
- 不处理 `docs/ideas.md`。
- 不主动提交、推送或改写 Git 历史。

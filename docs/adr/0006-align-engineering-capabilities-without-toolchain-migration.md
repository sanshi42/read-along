# 对齐 readest 的工程能力但不迁移前端工具链

Read Along 将借鉴 readest 的公开治理、分层 CI、安全扫描、依赖更新、工程文档和测试分层，但保留当前 `uv + npm + Vite/FastAPI` 技术栈，不迁移到 pnpm、Next.js、Vitest、Tauri 或 readest 的发布矩阵。这样可以获得成熟仓库治理能力，同时避免为当前小型本地优先应用引入不必要的包管理、路由框架和跨平台发布复杂度。

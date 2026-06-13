# Read Along MVP Plan

## Architecture

- 后端使用 FastAPI，前端使用 Vite、React 和 TypeScript。
- 阅读材料保存在本地 SQLite 和文件目录中，默认数据目录为 `~/.local/share/read-along/`。
- 公开网页通过 Scrapling 导入；用户已授权页面通过 Chrome 会话桥接读取可见正文。
- 文本型 PDF 通过 PyMuPDF 提取，不支持 OCR。
- TTS 使用 macOS `say` 适配器，按句缓存音频；播放、高亮和进度都以稳定句子 ID 为基础。
- 材料库拥有阅读材料的身份、重复判断、原子保存、完整读取和进度生命周期。

## Constraints

- Python 应用包保持扁平结构 `src/read_along/`，前端放在 `web/`。
- 配置环境变量使用 `READ_ALONG_` 前缀，后端默认监听 `127.0.0.1:8765`。
- 来源专用逻辑放在 `src/read_along/sources/`，通用导入和材料库保持来源无关。
- 正文清洗使用确定性规则，不使用 LLM 改写内容。
- 保留现有稳定材料、来源、段落和句子 ID。
- 当前生产数据库只创建或接受 `src/read_along/db.py` 定义的真实六表结构；其他现有结构保持不变并拒绝启动。
- SQLModel 与 Alembic 只作为技术基线，不自动接管或迁移当前生产数据库。
- 不引入 Celery、Redis、复杂前端状态库或生产部署基础设施。

数据库兼容边界的长期决策见 `docs/adr/`。

## Milestones

### M1: 导入与阅读基础

- Goal: 能导入文本型 PDF 和公开网页，并在书架与阅读页中查看结构化正文。
- Boundary: 本地存储、材料库、正文结构化、书架页、阅读页、公开网页导入和 Chrome 导入基础能力。
- Verification: 自动测试覆盖材料持久化和导入；浏览器可打开书架与阅读页。
- Status: Done。

### M2: 完成单篇导入闭环

- Goal: 得到单篇导入经过真实验收，重复导入时用户获得清晰反馈。
- Boundary: 只处理单篇导入验收和重复导入反馈，不增加批量抓取或导入任务进度。
- Verification: 使用公开网页、文本型 PDF 和已登录 Chrome 中的得到单篇页面完成手动验收；运行 `make check`。
- Status: Active。

### M3: 生成并缓存句子音频

- Goal: 使用 macOS `say` 为句子生成并复用本地音频。
- Boundary: TTS 适配器、句子音频缓存和音频访问 API；单句失败不阻断其他句子。
- Verification: 自动测试覆盖生成、缓存复用和失败路径；真实 macOS 环境可生成并播放单句音频。
- Status: Planned。

### M4: 完成朗读、高亮和断点续读

- Goal: 用户可以连续朗读材料，并看到同步高亮和恢复后的阅读位置。
- Boundary: 播放、暂停、上一句、下一句、自动续播、倍速、句子高亮和进度保存。
- Verification: 浏览器验证完整播放流程；刷新页面和重启服务后恢复位置；运行 `make check`。
- Status: Planned。

### M5: 阅读设置与 MVP 验收

- Goal: 完成字号、行距、明暗主题和核心闭环验收。
- Boundary: 阅读设置、本地持久化、核心错误提示和最终验收；不增加材料管理或高级学习功能。
- Verification: 三类目标材料均可完成导入、阅读、朗读和断点续读；运行 `make check`。
- Status: Planned。

## Verification

- 开发启动：`make dev`
- 全量检查：`make check`
- 格式化：`make format`
- 前端变更完成后，在浏览器中验证主要交互。
- MVP 验收至少覆盖一个公开网页、一个文本型 PDF 和一个已授权得到单篇课程页。

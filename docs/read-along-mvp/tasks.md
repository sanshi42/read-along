# Read Along MVP Tasks

## Status

导入、材料库、书架和阅读页基础能力已经可用。当前正在完成得到单篇导入的真实验收，之后进入重复导入反馈和朗读闭环。

阻塞项：无代码阻塞；得到单篇验收需要 Chrome 中存在用户已登录且有权访问的目标页面。

## Current Task

### T001: 完成得到单篇导入验收

- Goal: 确认用户已授权的得到单篇课程页可以通过 Chrome 会话完整导入为阅读材料。
- Boundary: 复验现有 Chrome 导入流程；只修复阻止该验收的问题，不扩展批量抓取、凭据保存或导入任务进度。
- Verification: 在已登录 Chrome 中打开目标单篇页面，从书架发起 Chrome 导入，确认正文可在阅读页打开且不包含明显导航或评论噪声；运行 `make check`。
- Status: Ready。

## Next Tasks

### T002: 补齐重复导入反馈

- Goal: 重复导入相同来源或相同正文时，用户能清楚知道系统复用了已有阅读材料。
- Boundary: 复用现有材料库重复判断，只补齐必要 API 和 UI 反馈。
- Verification: 覆盖相同来源、相同正文和来源内容变化三条路径；运行 `make check` 并在浏览器验证反馈。
- Status: Planned。

### T003: 实现单句 macOS say TTS 适配器

- Goal: 为单个句子可靠生成本地音频。
- Boundary: `say` 可用性检测、单句生成和清晰失败结果，不实现批量队列。
- Verification: 自动测试覆盖成功和失败路径；真实 macOS 环境生成一条可播放音频。
- Status: Planned。

### T004: 实现句子音频缓存与访问 API

- Goal: 已生成句子音频可以复用并由前端访问。
- Boundary: 按阅读材料和句子缓存音频，提供必要 API，不实现独立任务进度。
- Verification: 重复请求不重新生成音频；缺失和失败路径有明确结果；运行 `make check`。
- Status: Planned。

### T005: 实现基础播放器

- Goal: 用户可以播放、暂停并切换上一句或下一句。
- Boundary: 只实现句子级播放控制和自动进入下一句，不处理高亮与进度保存。
- Verification: 浏览器验证播放、暂停、切句和自动续播；运行 `make check`。
- Status: Planned。

### T006: 同步句子高亮、倍速和阅读进度

- Goal: 播放状态与正文高亮同步，并在刷新或重启后恢复位置。
- Boundary: 当前句高亮、倍速和进度保存，不增加逐字高亮。
- Verification: 浏览器验证高亮和倍速；刷新页面与重启服务后恢复位置；运行 `make check`。
- Status: Planned。

### T007: 完成阅读设置与 MVP 验收

- Goal: 提供基础阅读设置并完成 MVP 核心闭环验收。
- Boundary: 字号、行距、明暗主题、必要错误提示和最终验收，不增加材料管理或高级学习功能。
- Verification: 公开网页、文本型 PDF 和得到单篇页面均完成导入、阅读、朗读与断点续读；运行 `make check`。
- Status: Planned。

## Done

- 将项目开发流程精简为单一 Topic 的 `proposal.md`、`plan.md` 和 `tasks.md`。
- 建立 FastAPI 服务、配置、本地存储路径和开发工具链。
- 建立阅读材料领域模型、稳定内容 ID、材料库和 SQLite 持久化。
- 实现文本型 PDF 导入、正文清洗和段落/句子结构化。
- 实现书架页、阅读页和材料只读 API。
- 实现公开网页导入、得到来源清洗和 Chrome 会话导入基础能力。
- 建立 SQLModel/Alembic 技术基线，并精简为当前真实六表数据库启动校验。

# 代码布局

本文说明仓库目录和重要模块职责。系统级数据流见 [architecture.md](architecture.md)。

## 根目录

| 路径 | 职责 |
| --- | --- |
| `src/read_along/` | Python 后端、CLI、领域模型、导入、材料库、数据库和 TTS |
| `tests/` | Python 单元和集成测试 |
| `web/src/` | React 前端源码 |
| `web/test/` | 前端 Node.js test runner 测试 |
| `web/smoke/` | Playwright 浏览器烟测 |
| `docs/` | Topic 文档、ADR、工程文档和发布记录 |
| `CONTEXT.md` | 项目领域词汇 |
| `AGENTS.md` | Agent 工作规则和工程约束 |

## 后端模块

| 模块 | 职责 |
| --- | --- |
| `api.py` | FastAPI 路由、依赖注入和 HTTP 错误映射 |
| `cli.py` | Typer CLI，包含本地服务启动和 TTS 模型下载 |
| `config.py` / `storage.py` | 应用配置和本地数据目录布局 |
| `models.py` | API/领域数据模型和枚举 |
| `database_schema.py` / `db.py` / `db_models.py` | SQLite schema、初始化、SQLModel metadata |
| `repository.py` | SQLite repository，封装 SQL 读写 |
| `material_library.py` | 材料库对外门面，协调保存、读取、进度、音频和删除 |
| `material_views.py` | 阅读材料摘要、详情、导航和播放位置装配 |
| `material_audio.py` | 句子音频缓存路径、指纹、读取时长和生成流程 |
| `importers.py` / `extractors.py` / `browser.py` | URL/PDF 导入和正文提取 |
| `tts/` | TTS 配置、下载、后端协议和各后端适配器 |
| `sources/` | 特定来源的 URL 支持和正文清洗规则 |

## 前端模块

| 模块 | 职责 |
| --- | --- |
| `App.tsx` | 路由壳和跨页面阅读偏好状态 |
| `api.ts` | 后端 API 类型和 fetch 封装 |
| `routes/ShelfPage.tsx` | 书架页面、导入表单、材料列表和删除操作 |
| `routes/ReaderPage.tsx` | 阅读页页面组合，目前仍是前端最大热点 |
| `routes/readerPageViewModel.ts` | 阅读页纯 UI 决策和可测试 view-model 函数 |
| `routes/readerPlaybackTimeline.ts` | 朗读时间线、跳转、进度格式化 |
| `routes/readerAudioPreparation.ts` | 音频预加载、修复窗口和准备队列 |
| `routes/readerPlaybackSession.ts` | 阅读页临时朗读会话状态机 |
| `readingPreferences.ts` | 浏览器端阅读偏好持久化和应用 |
| `playbackModePreference.ts` | 浏览器端播放模式偏好持久化 |
| `styles.css` | 全局视觉样式和响应式布局 |

## 当前架构热点

- `MaterialLibrary` 是后端领域门面，应保持外部接口稳定；内部职责可以继续拆到小模块。
- `ReaderPage.tsx` 集中导航、正文、设置、播放器、滚动和禅模式，后续应拆组件和 hooks。
- `ShelfPage.tsx` 集中导入与列表 UI，暂不作为第一轮拆分目标。
- `readerPlaybackSession.ts` 是临时朗读状态机，继续通过前端单元测试保护行为。

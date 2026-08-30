# AGENTS.md

## 项目概览

- Read Along 是本地优先的个人 Web App，把单篇网页或文本型 PDF 转成可朗读、可断点续读的阅读材料。
- 后端使用 Python 3.12、FastAPI、Typer、SQLModel、SQLite 和 uv。
- 前端使用 React 19、Vite、TypeScript、React Router、lucide-react 和 npm。
- 默认本地 TTS 后端是 Sherpa ONNX Kokoro；在线 TTS 只作为用户显式配置的可选后端。

## 常用命令

```bash
make setup          # 安装依赖并安装 pre-commit hook
make dev            # 同时启动 API 和 Web
make dev-api        # 只启动 FastAPI
make dev-web        # 只启动 Vite
make check          # 本地快速完整门禁
make check-browser  # 真实浏览器烟测
make format         # 格式化 Python 和渐进式 Web 文件
make pre-commit     # 全量运行 pre-commit
```

后端默认监听 `http://127.0.0.1:8765`，前端默认监听 `http://127.0.0.1:5173`。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `src/read_along/api.py` | FastAPI 路由和 HTTP 错误映射 |
| `src/read_along/material_library.py` | 材料库对外门面 |
| `src/read_along/material_views.py` | 阅读材料摘要、详情、导航和播放位置装配 |
| `src/read_along/material_audio.py` | 句子音频缓存和生成流程 |
| `src/read_along/repository.py` | SQLite repository |
| `src/read_along/importers.py` | URL/PDF 导入入口 |
| `src/read_along/tts/` | TTS 配置、下载和后端适配器 |
| `web/src/api.ts` | 前端 API 类型和 fetch 封装 |
| `web/src/routes/ReaderPage.tsx` | 阅读页页面组合，当前前端架构热点 |
| `web/src/routes/readerPlaybackSession.ts` | 阅读页临时朗读状态机 |
| `web/smoke/` | Playwright 浏览器烟测 |

更完整的系统说明见 `docs/architecture.md`、`docs/code-layout.md`、`docs/testing.md` 和 `docs/frontend-guidelines.md`。

## 工程规则

- 新增或修改行为时优先测试先行；bug 修复应添加能复现问题的回归测试。
- Python 使用 Ruff、Pyrefly 和 pytest；Web 使用 TypeScript strict mode、Biome、Node.js test runner 和 Playwright smoke tests。
- 前端 Biome formatter 当前渐进接入，只覆盖 smoke/config/manifest 文件；不要把全量格式化和功能改动混在一起。
- TypeScript 不使用 `any`，优先使用 `unknown`、明确类型或泛型。
- 保持 `MaterialLibrary`、REST API、CLI、数据库 schema 和前端 API 类型的公开行为稳定；内部拆分不得改变这些接口。
- 涉及阅读页 UI 时，优先保持现有 class name、可访问名称、键盘操作和移动端布局稳定。

## 工作方式

- 默认使用中文沟通。
- 涉及领域语言或架构决策时，阅读 `CONTEXT.md`、`docs/agents/domain.md` 和相关 ADR。
- 不主动扩大当前工作范围，不混入无关重构。

## Agent skills

### Issue tracker

Issue 和规格使用 GitHub 仓库 `sanshi42/read-along` 管理。详见 `docs/agents/issue-tracker.md`。

### Triage labels

使用五个默认 triage 标签。详见 `docs/agents/triage-labels.md`。

### Domain docs

本仓库采用 single-context 布局。详见 `docs/agents/domain.md`。

## 验证方式

- 后端或跨栈变更：运行 `make check`。
- 前端交互变更：除自动检查外，在浏览器中验证主要交互。
- 文档变更：检查链接、文件布局和内容之间没有互相冲突。
- 不要把未验证或未完成的内容描述为完成。

## Git 约定

- 未经用户明确要求，不主动 commit、push 或改写 Git 历史。

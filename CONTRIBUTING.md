# 贡献指南

感谢你愿意改进 Read Along。这个项目目前以本地优先、单用户、单篇阅读材料导入和朗读为核心边界；任何改动都应先确认没有扩大这些边界。

## 开始之前

- 先搜索已有 issue 和 `docs/*/proposal.md`，避免重复工作。
- 较大的功能或架构变更请先开 issue 说明目标、边界和验证方式。
- 不要在同一个 PR 混入无关重构、格式化或依赖升级。
- 不要提交本地数据、`.env`、模型文件、生成音频或浏览器凭据。

## 开发设置

```bash
uv venv
make setup
make dev
```

后端默认监听 `http://127.0.0.1:8765`，前端默认监听 `http://127.0.0.1:5173`。

## 提交前检查

```bash
make check
```

涉及前端交互或路由时还应运行：

```bash
make check-browser
```

涉及后端材料库、导入、TTS 或数据库行为时，至少运行相关 pytest 文件；例如：

```bash
uv run pytest tests/test_material_library.py tests/test_api.py
```

## 代码约定

- Python 使用 Ruff 格式化和 lint，类型检查使用 Pyrefly。
- Web 使用 TypeScript strict mode、Biome 和 Node.js 内置 test runner。
- Web formatter 当前渐进接入，只覆盖 smoke/config/manifest 文件；不要在功能 PR 中批量格式化既有前端源码。
- 新增或修改行为时优先写测试；修复 bug 时应添加能复现问题的回归测试。
- 面向最终用户的 UI、CLI 输出和产品文案默认使用中文。
- 变量名、函数名、类名、文件名等代码标识符使用英文，并遵循项目已有命名。

## Pull Request

PR 描述应包含：

- 变更目标和边界。
- 主要实现点。
- 已运行的验证命令。
- 任何未覆盖的风险或后续工作。

未经维护者明确要求，不要 push 生成文件、模型文件、缓存目录或本地实验产物。

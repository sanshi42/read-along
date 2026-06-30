# 仓库完善与架构对齐计划

## 实现方案

1. 公开治理：补齐 README、CONTRIBUTING、SECURITY、GitHub issue 模板，并保留中文为主的公开协作语言。
2. 质量门禁：保留 `uv + npm`，新增前端 Biome 检查、浏览器烟测、分层 CI、Dependabot、CodeQL 与 Scorecard。
3. 工程文档：补齐架构、目录布局、测试分层、前端准则和 Agent 工程规则，记录不迁移前端工具链的 ADR。
4. 架构改进：保持 `MaterialLibrary` 外部接口不变，将材料视图装配拆到 `material_views.py`，句子音频缓存/生成拆到 `material_audio.py`。

## 关键决策

- readest 是能力参照，不是技术栈复制源。
- `make check` 继续作为本地快速完整门禁，浏览器烟测由 `make check-browser` 和 CI 单独运行。
- 前端 reader 当前存在未提交 WIP，本 Topic 不拆 `ReaderPage.tsx`，只在文档中标为后续热点。

## Topic 级验证

- `make check`
- `make check-browser`
- `uv run pytest tests/test_material_library.py tests/test_api.py`
- `npm run test --prefix web`
- 检查公开文档和 Agent 文档中的命令、路径、边界描述互相一致。

# Tasks

## Task 1: 公开治理文档

Goal: 补齐公开开源协作入口和 Topic 文档。

Depends on: None

Verification: README、CONTRIBUTING、SECURITY、issue 模板和 Topic 三文件存在且内容不冲突。

Status: Done

## Task 2: 质量门禁和 CI

Goal: 新增前端 Biome、浏览器烟测、分层 GitHub Actions、Dependabot、CodeQL 和 Scorecard。

Depends on: Task 1

Verification: `npm run lint --prefix web`、`npm run format:check --prefix web`、`make check`。

Status: Done

## Task 3: 工程文档和 ADR

Goal: 补齐架构、目录布局、测试、前端准则、Agent 规则和工程对齐 ADR。

Depends on: Task 1

Verification: 文档链接和命令描述一致。

Status: Done

## Task 4: 后端内部职责拆分

Goal: 保持 `MaterialLibrary` 外部接口不变，将材料视图装配和句子音频缓存生成拆到独立模块。

Depends on: Task 3

Verification: `uv run pytest tests/test_material_library.py tests/test_api.py`。

Status: Done

## Task 5: Topic 验证收尾

Goal: 运行 Topic 级验证并修正问题。

Depends on: Task 2, Task 4

Verification: `make check` 和可运行时的 `make check-browser`。

Status: Done

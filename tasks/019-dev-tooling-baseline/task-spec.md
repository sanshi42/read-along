# Task ID

019-dev-tooling-baseline

# Task title

开发工具链基线

# Backlog reference

支撑性工作；不直接对应单个 MVP 用户故事。

# Goal

统一本地开发命令、质量检查和提交前检查，让日常开发默认使用 uv 的 editable mode，并用 Pyrefly 替代 mypy。

# Scope

- 新增项目级 uv 清华镜像配置。
- 移除开发命令中的 `--no-editable`，保留部署场景说明。
- 使用 Pyrefly 自动迁移 mypy 配置，并移除 mypy 依赖和配置。
- 配置 Ruff 导入排序、Google docstring 规则和 single quote 格式化。
- 新增本仓库 local pre-commit hooks，提交时自动运行 Ruff 修复、格式化和 Pyrefly 检查。
- 新增 Makefile，提供 `setup`、`dev`、`check`、`format`、`typecheck` 和 `test` 等入口。
- 更新 README、技术方案、Sprint 计划、AGENTS 和进度记录中的工具链说明。

# Non-goals

- 不实现新的业务功能。
- 不调整前端 lint/format 工具链。
- 不在 pre-commit 中运行 pytest 或前端构建。
- 不建立 Pyrefly baseline 或批量 suppress。
- 不重写历史任务记录中的已完成命令输出。

# Implementation notes

- `make dev` 使用单个终端启动后端和前端，并在退出时清理后端进程。
- `pre-commit` 使用 `repo: local`，复用 uv 管理的 dev 依赖版本。
- `tests/**/*.py` 忽略 Ruff pydocstyle 规则，避免给测试函数补低价值 docstring。
- `D415` 对中文句号不友好，项目忽略该规则以避免中文 docstring 噪声。
- `D107` 容易要求重复描述 `__init__`，项目忽略该规则。
- 如 Pyrefly 迁移后发现类型错误，直接修复到全绿。

# Acceptance criteria

- `make dev` 可以一键启动后端和前端。
- `make check` 覆盖 Ruff、Pyrefly、pytest 和前端 build。
- `.pre-commit-config.yaml` 使用 local hooks，并且不包含 `--no-editable`。
- `pyproject.toml` 不再包含 mypy 依赖或 `[tool.mypy]`。
- 文档中的开发命令默认不使用 `--no-editable`。

# Test plan

- 运行 `uv lock`。
- 运行 `uv sync`。
- 运行 `uv run ruff check .`。
- 运行 `uv run ruff format --check .`。
- 运行 `uv run pyrefly check`。
- 运行 `uv run pytest`。
- 运行 `npm run build --prefix web`。

# Completion notes

- 已新增 `Makefile`，提供 `make setup`、`make dev`、`make check`、`make format`、`make typecheck` 和 `make test`。
- 已新增 `.pre-commit-config.yaml`，使用本仓库 `repo: local` hooks，提交时运行 Ruff 自动修复、Ruff format 和 Pyrefly 检查。
- 已在 `pyproject.toml` 配置 uv 清华镜像、Ruff isort/pydocstyle/single quote 和 Pyrefly。
- 已通过 `pyrefly init pyproject.toml --migrate-from mypy --non-interactive` 自动迁移，并移除 mypy 依赖和 `[tool.mypy]`。
- 已移除开发文档中的 `--no-editable` 默认命令，仅保留部署或打包场景说明。
- 已补齐源码 public class/function/method docstring，以满足新的 Ruff pydocstyle 规则。
- 验证：`uv lock`、`uv sync`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run pyrefly check`、`uv run pytest`、`npm run build --prefix web`、`uv run pre-commit run --all-files`、`make check` 均通过。
- 冒烟验证：`make dev` 可在同一终端启动 Vite `http://127.0.0.1:5173/` 和后端 `http://127.0.0.1:8765`；验证后已停止。

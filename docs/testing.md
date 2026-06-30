# 测试说明

Read Along 使用多层测试。默认本地门禁是 `make check`，浏览器烟测单独使用 `make check-browser`。

## Python 测试

```bash
uv run pytest
```

使用场景：

- API 路由行为。
- 材料库保存、读取、进度、删除和音频缓存。
- 数据库 schema 和约束。
- 导入器、正文提取、TTS 配置和下载。

常用聚焦命令：

```bash
uv run pytest tests/test_material_library.py tests/test_api.py
uv run pytest tests/test_importers.py tests/test_extractors.py
```

## 前端单元测试

```bash
npm run test --prefix web
```

前端测试使用 Node.js 内置 test runner 和 `--experimental-strip-types`，覆盖纯逻辑模块，例如播放模式、阅读页 view-model、音频准备、朗读时间线和书架 view-model。

测试文件位于 `web/test/*.test.ts`。优先测试可独立运行的纯函数和状态机；浏览器 DOM 交互用 smoke test 覆盖。

## 浏览器烟测

```bash
make check-browser
```

烟测会：

1. 使用临时 `READ_ALONG_HOME` 启动 FastAPI。
2. 启动 Vite 开发服务器。
3. 通过 Playwright Chromium 访问真实页面。
4. 验证 `/api/health` 代理、空书架页面和未知路由 404。

本地首次运行前可能需要安装 Chromium：

```bash
npx --prefix web playwright install chromium
```

CI 会自动安装 Chromium，并在 Python 和 Web job 通过后运行 smoke job。

## 静态检查

```bash
make lint
make format-check
make typecheck
```

- Python：Ruff lint、Ruff format、Pyrefly。
- Web：Biome lint 和渐进式 Biome format check。
- 当前 Biome formatter 只覆盖 smoke/config/manifest 文件，避免在 reader WIP 未稳定前批量改动前端源码。

## 完整本地门禁

```bash
make check
```

`make check` 运行 Python lint/format/typecheck/test、Web lint/format/test 和 Vite build。不要把未运行的检查描述为通过。

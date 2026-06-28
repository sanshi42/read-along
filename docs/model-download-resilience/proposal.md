---
status: done
priority: P1
created: 2026-06-26
---

# 模型下载可靠性 Proposal

## Goal

让本地 Kokoro 模型下载在不稳定网络下可观察、可恢复：展示进度，保留局部归档并使用 HTTP Range 续传，提供可预测的重试与强制重下入口。

## Boundary

### In

- `tts download-model kokoro` 的 Rich 终端进度显示。
- 局部归档、元数据、HTTP Range/If-Range 续传、网络重试与完整性重试。
- `--restart` 参数、回归测试和 README 使用说明。

### Out

- `.env` 自动写入、Web 设置页和其他模型 profile。
- 下载源切换、账号凭据管理和全局下载管理器。

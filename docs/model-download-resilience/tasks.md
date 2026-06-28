# 模型下载可靠性 Tasks

## Task 1：实现可恢复下载

- Goal：实现局部归档、Range 续传、来源校验、网络重试和归档完整性重试。
- Depends on：无。
- Verification：下载层回归测试。
- Status：Done。

## Task 2：接入 CLI 进度与重启参数

- Goal：提供 Rich 进度条、非交互回退和 `--restart`。
- Depends on：Task 1。
- Verification：CLI 回归测试。
- Status：Done。

## Task 3：完成文档与全量验证

- Goal：补充 README，并完成 Topic 级检查。
- Depends on：Task 1、Task 2。
- Verification：`make check`。
- Status：Done。

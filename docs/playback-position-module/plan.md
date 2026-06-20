# 阅读进度与朗读位置 Module Plan

## 实现方案

- 新增后端朗读位置 Module，负责从句子序列和阅读进度派生时间式朗读位置。
- 让材料库通过该 Module 生成 `playback_time_position`，保留现有 `playback_position` 查询路径。
- 在前端播放时间线 Module 中集中恢复锚点语义，让阅读页加载和音频预载共用同一个函数。
- 保持当前完成语义：API 的时间式朗读位置显示已到末尾；阅读页恢复朗读时从第一句开始。

## 关键决策

- 本次不引入跨语言共享代码，只让 Python 与 TypeScript Adapter 以同名测试覆盖同一语义。
- 本次不修改外部 API Interface，避免扩大到迁移或客户端兼容问题。
- `playback_completed` 仍表示最后一句自然播放完成；恢复朗读时定位到第一句 0 秒。

## Topic 级验证

- 运行后端朗读位置测试。
- 运行前端播放时间线和音频预载测试。
- 运行 `make check`。

# 禅模式阅读 Tasks

## T001: 记录禅模式领域术语与 Topic 执行文档

- Goal: 明确禅模式是阅读页临时低干扰显示状态，并补齐 Active Topic 文档。
- Depends on: None
- Verification: 检查 `CONTEXT.md`、`proposal.md`、`plan.md` 和 `tasks.md` 之间没有冲突。
- Status: Done

## T002: 实现禅模式快捷键与页面状态

- Goal: 阅读页支持导航入口、`Z` 切换、`Escape` 退出、全屏请求和全屏退出同步。
- Depends on: T001
- Verification: 前端单测覆盖快捷键 helper；浏览器验证按钮、快捷键、全屏降级和退出同步。
- Status: Done

## T003: 实现禅模式低干扰布局

- Goal: 禅模式隐藏非必要阅读 chrome，只保留正文、退出按钮和底部状态条。
- Depends on: T002
- Verification: 浏览器验证桌面、窄屏、浅色、深色、当前句定位、状态条错误和普通阅读页回归。
- Status: Done

## T004: Topic 级验证与收尾

- Goal: 完整运行自动检查并根据验证结果归档 Topic。
- Depends on: T003
- Verification: 运行 `make check`；完成浏览器交互验证；通过后标记 Topic Done。
- Status: Blocked
- Blocked: `make check` 通过，Chrome 桌面禅模式进入、`Z` 切换、`Escape` 退出、全屏失败降级、深色主题和普通播放器恢复已验证；但当前 Chrome/AppleScript 验证无法把窗口缩到 390px，窄屏真实浏览器验证未完成，因此 Topic 暂停，未标记 Done。

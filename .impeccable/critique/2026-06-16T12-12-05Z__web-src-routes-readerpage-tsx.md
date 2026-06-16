---
target: 阅读页
total_score: 25
p0_count: 0
p1_count: 2
timestamp: 2026-06-16T12-12-05Z
slug: web-src-routes-readerpage-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 3 | 播放状态、句子位置和错误重试清楚，但恢复到当前句在移动端会失效。 |
| 2 | Match System / Real World | 3 | 长读氛围和播放器模型贴合产品；标题/source 呈现仍偏文件管理感。 |
| 3 | User Control and Freedom | 2 | 返回书架、设置关闭可用；移动端“回到当前句”消失但当前句仍不可见。 |
| 4 | Consistency and Standards | 3 | token 和组件语言稳定；阅读页 H1 字距偏离设计系统。 |
| 5 | Error Prevention | 2 | 播放/进度保存有重试；固定播放器安全区不足导致关键状态被遮挡。 |
| 6 | Recognition Rather Than Recall | 2 | 主要控制可见；恢复到中段时缺少材料标题/当前位置上下文。 |
| 7 | Flexibility and Efficiency | 2 | 有句子级键盘导航；缺少全局播放快捷键、跳转/进度概览。 |
| 8 | Aesthetic and Minimalist Design | 3 | 正文中心和深色阅读气质成立；标题过强、播放器移动端占屏偏重。 |
| 9 | Error Recovery | 3 | 加载失败、音频失败、进度失败均有清晰重试入口。 |
| 10 | Help and Documentation | 2 | 阅读设置自解释；句子点击/键盘操作没有上下文提示。 |
| **Total** | | **25/40** | **Acceptable: core direction solid, but two primary-task failures need fixing.** |

## Anti-Patterns Verdict

**LLM assessment**: 不像典型 AI 生成的 SaaS 页面。它有明确的“静读书房”方向、克制的组件语言、合格的深色主题和正文中心。但阅读页也暴露出几处过度设计/欠产品化的地方：标题像品牌展示页一样大，文件名和来源重复；移动端固定播放器占屏过重；正文被语义化成大量按钮，视觉上安静，辅助技术上却很嘈杂。

**Deterministic scan**: `detect.mjs --json web/src/routes/ReaderPage.tsx` 返回 `[]`，没有发现硬性禁用模式。扫描没有覆盖我手动发现的 H1 `letter-spacing: -0.055em` 超过设计系统下限，以及移动端播放器遮挡当前句。

**Visual overlays**: overlay 注入预检失败，Codex Browser 的 Playwright evaluate 为只读环境，`document.title` 无法写入。未启动 live detector server，也没有可靠的人类可见 overlay。浏览器控制台只有既有 live-mode 日志，没有 detector 结果。

## Overall Impression

阅读页的方向是对的：正文、当前句和播放器是主角，不像后台，也没有多余装饰。最大机会是把“恢复当前句”这件事做到绝对可信，尤其是移动端；现在它在关键路径上有可见失败。

## What's Working

- 正文宽度、深色主题、宋体正文和低饱和棕色控制形成了稳定的长读氛围，和 PRODUCT.md 的“安静、可信、沉浸”一致。
- 底部播放器把状态、位置、倍速、上一句/下一句/播放放在一个地方，认知负担低。
- 阅读设置面板的三组偏好清楚，点击目标足够大，深色/浅色 token 的对比度通过 AA：深色正文对背景约 15.12:1，深色当前句约 7.30:1。

## Priority Issues

**[P1] 移动端当前句恢复不可信**

Why it matters: 我在 390×844 视口里点击/触发回到当前句后，`.return-current` 消失，但 `.reader-sentence-current` 的 rect 是 `top: 1094px, bottom: 1173px`，完全在视口外；播放器位于 `top: 704px, height: 132px`。用户以为已经回到当前位置，实际还在读错误段落。

Fix: 不要用固定的 `window.innerHeight - 120` 判断安全区。读取 `.player-bar` 实际高度和 bottom safe area，给当前句设置动态 `scroll-margin-bottom`，或用自定义 `scrollTo` 让当前句落在 `nav.bottom + margin` 和 `player.top - margin` 之间。`showReturnToCurrent` 只有在当前句真实可见后才能消失。

Suggested command: `$impeccable adapt 阅读页`

**[P1] 正文语义被暴露成 100 个按钮**

Why it matters: DOM 快照里每个句子都是 `role="button"`，屏幕阅读器会把正文读成一长串按钮，破坏“阅读”这个核心任务。虽然 roving `tabIndex` 减少了 Tab 次数，但虚拟光标仍会遇到大量按钮语义。

Fix: 保持正文为 prose 语义。只把当前可操作目标暴露为清晰控件，或提供独立的“播放此句/设为当前句”动作；如果句子必须可聚焦，ARIA label 应描述动作而不是重复整句正文。当前句状态可用 `aria-current`/`aria-live` 辅助，但不要牺牲段落阅读语义。

Suggested command: `$impeccable audit 阅读页`

**[P2] 恢复到中段时缺少材料上下文**

Why it matters: 页面会自动滚到保存句，用户看到的 sticky nav 只有“返回书架 / Read Along / 设置”。标题和来源在几屏之外；打开多篇材料时，用户需要靠记忆确认自己在哪篇、当前位置是否正确。

Fix: 滚过 header 后在 nav 中显示压缩材料标题和句子位置，例如 `6 底注… · 第 50/100 句`。不要让它抢正文层级；使用小号 UI 字体、单行省略即可。

Suggested command: `$impeccable clarify 阅读页`

**[P2] 标题层级过重且偏离设计系统**

Why it matters: `.reader-entry h1` 使用 `letter-spacing: -0.055em`，比 DESIGN.md 的 `-0.04em` 下限更紧；长中文标题加 `.pdf` 后像展示页 headline，不像阅读页材料标题。source 行又重复同一文件名，增加噪声。

Fix: 把阅读页 H1 字距收回到 `-0.04em` 或更松，桌面最大字号可从 `5.2rem` 降到更像材料标题的区间。标题去掉文件扩展名，source 行只在有真实来源差异时显示，PDF 文件名可放到元信息里。

Suggested command: `$impeccable typeset 阅读页`

**[P2] 移动端播放器状态区占屏偏重**

Why it matters: 390px 视口里播放器高约 132px，占可视高度 15% 以上；打开设置面板时，顶部面板和底部播放器同时挤压正文。加入“回到当前句”后还会增加第二行，读者要在控制层之间找正文。

Fix: 移动端把状态区压缩为一行，倍速可降级为短按钮/菜单；“回到当前句”用窄条状态 chip 或贴近正文边缘的临时提示。底部 safe area 和 reader padding 应以播放器实际高度计算。

Suggested command: `$impeccable layout 阅读页`

## Persona Red Flags

**Sam (Accessibility-Dependent User)**: 正文被宣布成大量按钮，阅读体验会变成控件遍历；当前句视觉高亮有 `aria-current`，但语义噪声太大；移动端当前句可能在播放器下方或视口外，键盘/读屏用户更难判断是否成功回到位置。

**Alex (Power User)**: 有上一句/下一句和句子焦点键盘操作，但没有明显的全局播放快捷键、跳转到第 N 句、进度概览或快速恢复确认。长文中只靠 `第 50 / 100 句` 不够高效。

**Casey (Distracted Mobile User)**: 主要播放按钮在拇指区，这是优点；但恢复位置失败和播放器占屏会让中断后回来的人读错位置。设置面板打开时屏幕同时有 nav、popover、正文、播放器四层信息。

## Minor Observations

- 颜色对比整体优秀，浅色最弱的辅助文字对画布也约 4.52:1，刚过 AA。
- 正在播放句有下划线，当前句非播放态主要靠背景色；可以加更明确的非颜色状态。
- 设置面板使用 `role="dialog"` 但不是 modal；目前可接受，但如果后续面板复杂化，应考虑 focus trap 或 popover API。
- 错误反馈集中在播放器里是好事，但长错误文案会被 `white-space: nowrap` 截断。

## Questions to Consider

- 如果用户打开阅读页时直接落在第 50 句，nav 应该显示产品名，还是显示“当前材料 + 句子进度”？
- 句子点击是核心交互还是增强交互？如果是增强交互，正文语义不应为它付出按钮化代价。
- 移动端播放器应该是常驻 dock，还是播放时常驻、暂停时更轻量？

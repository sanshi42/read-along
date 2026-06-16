---
name: Read Along
description: 安静、可信、沉浸的本地音文阅读空间
colors:
  canvas: "#f3eee4"
  surface: "#fbf8f1"
  surface-subtle: "#eee7da"
  surface-strong: "#ffffff"
  text: "#27231d"
  text-muted: "#696258"
  text-subtle: "#746b60"
  border: "#d8cfc0"
  border-strong: "#b7aa98"
  accent: "#805127"
  accent-hover: "#633b1b"
  accent-contrast: "#fffaf1"
  accent-soft: "#ead9c2"
  highlight: "#ead4a4"
  highlight-strong: "#e5b96a"
  success: "#35613e"
  success-soft: "#dce9db"
  error: "#9b3d32"
  error-soft: "#f1ded8"
  focus: "#9b672f"
  dark-canvas: "#171612"
  dark-surface: "#211f1a"
  dark-surface-subtle: "#2b2821"
  dark-surface-strong: "#312d25"
  dark-text: "#f0eadf"
  dark-text-muted: "#c1b8aa"
  dark-accent: "#d09a63"
  dark-highlight: "#5b4828"
  dark-highlight-strong: "#795522"
typography:
  display:
    fontFamily: "Songti SC, STSong, SimSun, Georgia, serif"
    fontSize: "clamp(2.6rem, 8vw, 5.2rem)"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Songti SC, STSong, SimSun, Georgia, serif"
    fontSize: "clamp(2rem, 5vw, 3rem)"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Songti SC, STSong, SimSun, Georgia, serif"
    fontSize: "1.55rem"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "Songti SC, STSong, SimSun, Georgia, serif"
    fontSize: "1.18rem"
    fontWeight: 400
    lineHeight: 2
  label:
    fontFamily: "PingFang SC, Hiragino Sans GB, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 700
    lineHeight: 1.5
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "18px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-contrast}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0 15px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.accent-contrast}"
    rounded: "{rounded.md}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0 15px"
    height: "44px"
  input:
    backgroundColor: "{colors.surface-strong}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0 13px"
    height: "46px"
  state-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
  player-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-contrast}"
    rounded: "{rounded.pill}"
    width: "50px"
    height: "50px"
---

# Design System: Read Along

## Overview

**Creative North Star: “静读书房”**

Read Along 应像一间只为一个人准备的安静书房：进入后首先看到正文，控制与状态随手可得，但不会主动争夺注意力。视觉系统借鉴微信读书对长时间阅读和夜读的克制，也借鉴得到学习清晰的音文同步与常驻播放控制，同时保持本地个人工具应有的轻量与私密。

整体采用低装饰、清晰层级和温和触感。浅色主题以暖纸张层次承载阅读，深色主题以炭黑层次降低长时间夜读刺激；棕色强调只用于主要动作、当前状态和焦点。桌面优先，窄屏完整可用；正文最大宽度约 `43rem`，产品控制采用至少 `44px` 的点击目标。

**Key Characteristics:**

- 正文始终是页面中最强、最稳定的视觉层级。
- 阅读文字使用系统宋体，控制、标签和状态使用系统黑体。
- 浅色与深色主题成对设计，不把深色主题当作单纯反色。
- 边框和色层负责大多数结构表达，阴影只用于真正浮起的控件。
- 动效只解释状态变化，并完整支持减少动态效果。

## Colors

配色像纸张、木质书桌和克制的荧光笔标记：温和但对比明确，强调色稀少而有功能。

### Primary

- **书桌棕** (`#805127`): 主要动作、链接、当前选择和关键图标；悬停加深为 `#633b1b`。
- **柔棕底色** (`#ead9c2`): 选中项和低强度强调背景，不替代主要动作色。

### Neutral

- **暖纸画布** (`#f3eee4`): 浅色主题页面背景。
- **阅读纸面** (`#fbf8f1`): 普通面板、次要按钮和材料悬停背景。
- **纯白强表面** (`#ffffff`): 输入、弹层和底部播放器等需要与画布清楚分离的控件。
- **炭墨正文** (`#27231d`): 浅色主题主要文字。
- **沉静辅助文字** (`#696258` / `#746b60`): 标签、来源与辅助说明；用于正文以外的信息层级。
- **炭黑夜读画布** (`#171612`): 深色主题页面背景；正文使用 `#f0eadf`，避免纯黑纯白的刺眼组合。

### Semantic

- **当前句标记** (`#ead4a4`): 当前句的低强度荧光笔底纹。
- **正在播放标记** (`#e5b96a`): 正在朗读句子的强底纹，必须同时配合下划线或其他非颜色提示。
- **成功** (`#35613e` / `#dce9db`): 成功反馈文字与背景。
- **错误** (`#9b3d32` / `#f1ded8`): 错误反馈文字与背景。
- **焦点** (`#9b672f`): 清晰可见的键盘焦点环。

### Named Rules

**强调色稀缺规则。** 书桌棕只用于动作、选择、焦点和状态，不用于装饰大片区域。

**成对主题规则。** 新增颜色必须同时考虑浅色和深色主题，并在各自背景上达到 WCAG AA。

## Typography

**Display Font:** `Songti SC, STSong, SimSun, Georgia, serif`  
**Body Font:** `Songti SC, STSong, SimSun, Georgia, serif`  
**Label Font:** `PingFang SC, Hiragino Sans GB, Microsoft YaHei, system-ui, sans-serif`

宋体赋予标题和正文稳定、适合长读的书页气质；黑体让控制、标签和状态保持直接、清晰。两者分工明确，不在单个组件中随意混用。

### Hierarchy

- **Display** (`600`, `clamp(2.6rem, 8vw, 5.2rem)`, `1.08`): 阅读材料标题；字距不得紧于 `-0.04em`。
- **Headline** (`600`, `clamp(2rem, 5vw, 3rem)`, `1.08`): 页面和主要区块标题。
- **Title** (`600`, 约 `1.24rem–1.55rem`, `1.35`): 材料名称和面板标题。
- **Body** (`400`, 默认 `1.18rem`, `2`): 阅读正文；提供 `1.05rem`、`1.18rem`、`1.34rem` 和 `1.72`、`2`、`2.3` 的阅读偏好组合，正文行宽不超过约 `43rem`。
- **Label** (`700`, 约 `0.72rem–0.84rem`): 控件、状态和短标签；保持直接可读，不用显示字体制造气氛。

### Named Rules

**长读优先规则。** 正文字号、行距、行宽和对比度优先服务持续阅读；标题的视觉表现不得挤压正文空间或在窄屏溢出。

## Elevation

系统默认保持扁平，通过画布、表面、强表面和分隔线建立层级。阴影只代表真正浮在内容之上的元素：阅读偏好弹层使用 `0 16px 40px rgba(61, 49, 34, 0.16)`，底部播放器使用 `0 12px 32px rgba(61, 49, 34, 0.18)`；深色主题使用更高不透明度的黑色阴影。

### Shadow Vocabulary

- **Popover** (`0 16px 40px rgba(61, 49, 34, 0.16)`): 仅用于阅读偏好等临时浮层。
- **Dock** (`0 12px 32px rgba(61, 49, 34, 0.18)`): 仅用于固定在内容上方的底部播放器。
- **Inline highlight** (`3px 0 0` / `4px 0 0`): 延展句子底纹边缘，不表达卡片高度。

### Named Rules

**默认无阴影规则。** 静态面板、材料列表、按钮和输入依靠背景与边框表达结构；不要同时使用装饰性边框和宽软阴影。

## Components

组件保持熟悉、可靠和安静。相同动作在不同页面使用相同形状、状态和图标语言。

### Buttons

- **Shape:** 普通按钮使用 `10px` 圆角，图标按钮同样使用 `10px`；播放器主按钮可使用完整圆形。
- **Primary:** 书桌棕背景、浅色文字、至少 `44px` 高；仅用于页面或控制组中的主要动作。
- **Secondary:** 阅读纸面背景与 `1px` 分隔边框，不使用阴影。
- **Hover / Active / Focus:** 悬停改变色层或边框，按下轻微缩放至 `0.97`；键盘焦点使用 `3px` 焦点环和明确偏移。
- **Disabled:** 保留形状与标签，降低不透明度并禁用交互。

### Cards / Containers

- **Corner Style:** 普通面板最大 `16px`；材料列表使用分隔行，不转换成重复卡片网格。
- **Background:** 面板使用阅读纸面，浮层和播放器使用强表面。
- **Shadow Strategy:** 静态内容无阴影；只对弹层和播放器使用命名阴影。
- **Border:** 使用 `1px` 完整边框或横向分隔线，不使用彩色侧条。
- **Internal Padding:** 紧凑控件约 `12px–18px`，主要状态面板约 `30px–64px`。

### Inputs / Fields

- **Style:** `46px` 最小高度、`10px` 圆角、强表面背景和 `1px` 分隔边框。
- **Focus:** 使用与按钮一致的 `3px` 焦点环，不只改变边框颜色。
- **Error / Disabled:** 错误采用错误文字与柔和错误底色；禁用状态保留可读标签。

### Navigation

阅读页导航保持轻薄并吸附顶部，通过半透明画布和细分隔线与正文分开。高频动作使用一致的 Lucide 线性图标；非显然动作保留文字。窄屏隐藏非关键品牌文字，但保留返回与设置能力。

### Reader Sentence

句子本身是阅读和定位的主要交互单位。默认不加装饰；悬停只轻微使用强调色。当前句使用柔和底纹，正在播放时使用更强底纹并增加下划线，键盘焦点使用独立焦点环。

### Player Dock

播放器固定在阅读区底部中央，桌面保持紧凑横向布局，窄屏重排为两行控制。播放器必须展示当前朗读位置、播放动作、上一句、下一句和倍速；错误与重试应在播放器内直接呈现。

## Do's and Don'ts

### Do:

- **Do** 让正文保持约 `43rem` 的舒适行宽，并使用用户可调字号、行距和主题。
- **Do** 为所有主要交互提供至少 `44px` 的目标尺寸、完整键盘操作和清晰焦点。
- **Do** 同时用文字、图标、下划线或结构变化表达播放、选择、错误和完成状态。
- **Do** 使用材料列表、分隔线和逐级表面组织信息，让用户快速回到阅读。
- **Do** 保持状态动效在约 `160ms–210ms`，并为 `prefers-reduced-motion` 提供近乎即时的替代。

### Don't:

- **Don't** 把界面做成企业 SaaS 仪表盘，不引入指标卡片、管理后台式侧栏或密集工具栏。
- **Don't** 使用大量玻璃效果、装饰性渐变或只为视觉冲击存在的装饰。
- **Don't** 增加分散正文注意力的动效、悬浮工具、课程目录、留言或推广区域。
- **Don't** 只依赖颜色表达播放、选择、错误或完成状态。
- **Don't** 将材料列表改为相同尺寸的重复卡片网格，也不要在卡片上使用彩色侧条。
- **Don't** 在静态按钮、输入和内容面板上同时使用边框与宽软阴影。
- **Don't** 使用大于 `16px` 的普通卡片圆角；完整胶囊只用于标签或明确的圆形控制。

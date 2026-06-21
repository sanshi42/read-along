# 阅读页最终打磨 Tasks

## Task 1: 当前句恢复可靠性

Goal: 当前句可见性和滚动目标使用实际顶部导航、底部播放器与安全边距，回到当前句后按钮只在当前句真实可见时消失。

Depends on: none

Verification: 单元测试覆盖播放器遮挡、可读区域过小和滚动目标计算；浏览器检查移动端当前句不会落在播放器下方。

Status: Done

## Task 2: 正文语义降噪

Goal: 阅读正文不再被辅助技术暴露成大量按钮，同时保留句子选择、播放和键盘路径。

Depends on: none

Verification: DOM/测试确认普通句子没有按钮语义，当前交互提示清晰；键盘与点击仍可工作。

Status: Done

## Task 3: 中段阅读上下文与标题层级

Goal: sticky nav 在标题离开视口后显示材料标题与句子进度，阅读页标题和来源信息符合设计系统层级。

Depends on: none

Verification: 单元测试覆盖标题归一化；浏览器检查桌面与移动端无溢出。

Status: Done

## Task 4: 移动端播放器密度

Goal: 移动端播放器占屏更克制，正文底部 padding 与播放器高度匹配。

Depends on: Task 1

Verification: 移动端视口检查播放器不遮挡当前句，控制目标仍不小于 44px。

Status: Done

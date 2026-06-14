# 整体前端体验优化 Tasks

## T001: 确定整体前端体验方向

- Goal: 明确产品气质、主要使用场景、信息层级、设计系统和改造深度。
- Depends on: 无。
- Verification: 设计决策与现有领域语言、产品边界和真实页面一致，并记录到 Topic 文档。
- Status: Done

## T002: 增加朗读位置 API

- Goal: 为书架提供不混淆阅读完成度的朗读位置派生数据。
- Depends on: T001。
- Verification: 模型、材料库和 API 测试覆盖无进度、当前句位置与详情响应。
- Status: Done

## T003: 建立全局设计系统与页面基础

- Goal: 建立统一的颜色、字体、间距、状态、图标、交互和响应式基础。
- Depends on: T001。
- Verification: 浏览器验证浅色、深色、390px 窄屏、统一图标、44px 控件和对比度；前端生产构建通过。
- Status: Done

## T004: 优化书架与导入体验

- Goal: 提升继续阅读、导入、状态反馈和选择阅读材料的清晰度与效率。
- Depends on: T002、T003。
- Verification: 浏览器验证空书架自动展开、非空书架默认折叠、折叠控件退出键盘交互、朗读位置、朗读完成、纵向材料列表和 390px 无横向滚动。
- Status: Done

## T005: 优化阅读与朗读体验

- Goal: 提升沉浸阅读、当前位置识别、键盘导航、阅读偏好和朗读控制体验。
- Depends on: T003。
- Verification: 浏览器验证恢复位置、唯一句子 Tab 停靠点、方向键移动焦点但不改变当前句、阅读设置关闭后焦点返回和 390px 底部播放器布局。
- Status: Done

## T006: 完成整体前端验收

- Goal: 修复跨页面一致性与验收中发现的问题，完成 Topic 级验证。
- Depends on: T004、T005。
- Verification: `make check` 通过，198 项测试及前端生产构建通过；完成桌面、390px、主题、对比度、键盘和状态页面验收。
- Status: Done

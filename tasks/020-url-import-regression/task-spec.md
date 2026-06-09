# Task ID

020-url-import-regression

# Task title

修复真实本地环境 URL 导入回归

# Backlog reference

- MVP-013：网页导入
- MVP-014：得到单篇导入
- MVP-019：错误提示

# Goal

恢复从书架页发起 URL 导入的完整可用性，使公开网页和已登录 Chrome 两种导入方式在真实本地环境中都能成功完成。

# Scope

- 恢复书架页公开网页和已登录 Chrome 两种 URL 导入方式入口，并将所选模式传给后端。
- 修复从本地应用页点击 Chrome 导入时误读 Chrome 前台本地页的问题。
- 为旧版 `materials` 单表 schema 增加幂等迁移，保留已有材料、正文、进度和导入任务。
- 修复 `material_sources` 外键仍引用已删除 `materials_legacy` 的半迁移状态。
- 新增回归测试，覆盖 UI 模式传递、Chrome 目标标签页选择和旧库迁移。
- 使用公开网页和得到单篇 URL 验证修复结果。

# Non-goals

- 不实现批量抓取、自动翻页或课程目录导入。
- 不绕过登录或付费权限。
- 不保存 Cookie、账号密码或浏览器凭据。
- 不实现重复导入完整体验。
- 不新增 TTS、播放器或阅读进度能力。

# Implementation notes

- URL 导入回归包含三个连续暴露的根因：前端缺少 Chrome 模式入口、Chrome fallback 选错标签页、旧库 schema 无法保存新材料。
- Chrome fallback 应按目标 URL 搜索所有普通标签页，不要求用户从本地应用提交后再切换前台标签页。
- 旧 schema 迁移必须保留已有数据，并确保所有来源外键最终只引用当前 `materials` 表。
- 无法可靠恢复旧 schema 中缺失的多来源身份时，为历史材料生成兼容来源身份。

# Acceptance criteria

- 书架页显示公开网页和已登录 Chrome 两种 URL 导入方式，并提交正确的 `mode`。
- 当前前台页为 Read Along 本地页面时，只要 Chrome 中存在匹配目标 URL 的标签页，Chrome 模式即可读取目标页。
- 旧 schema 数据库初始化后可以保存新 URL 材料，已有材料、正文、进度和导入任务仍可读取。
- `PRAGMA foreign_key_list(material_sources)` 只引用 `materials`，不引用 `materials_legacy`。
- 公开网页和得到单篇 URL 的真实验证通过。
- 新增回归测试和全量检查通过。

# Test plan

- 运行数据库迁移、Chrome 标签页选择和 URL 导入相关定向测试。
- 运行 `make check`。
- 使用 in-app browser 验证书架页导入方式 UI。
- 使用真实默认库和当前本地 API 验证公开网页导入。
- 使用已登录 Chrome 中的得到单篇目标页验证 Chrome 模式导入。

# Completion notes

- 恢复书架页 URL 导入方式选择，支持公开网页和已登录 Chrome，并将 `mode` 传给 `POST /api/import/url`。
- 新增 `extract_chrome_text_by_url_filters`，DevTools 未命中时通过 AppleScript 遍历 Chrome 普通标签页并按目标 URL 抽取正文。
- 新增旧版 `materials` 单表 schema 迁移，保留材料、来源、段落、句子、阅读进度和导入任务。
- 新增半迁移修复逻辑，重建仍引用 `materials_legacy` 的 `material_sources` 表并保留有效来源。
- 使用临时库验证公开网页和得到 Chrome 模式导入，使用真实默认库及当前本地 API 验证公开网页导入。
- `make check` 全量通过；in-app browser 已验证导入方式 UI。

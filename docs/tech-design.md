# Read Along MVP 技术方案

最后更新：2026-06-06

## 目标

用最小工程复杂度实现 `docs/mvp-scope.md` 定义的核心闭环：

用户导入单篇网页或文本型 PDF，系统在本机保存结构化正文，按句生成音频，在 Web 阅读器里播放、暂停、倍速、句子高亮并保存进度。

## 技术选型

| 层 | 选择 | 原因 |
| --- | --- | --- |
| 后端 | FastAPI + Uvicorn | Python 生态成熟，适合本地 API 和文件服务。 |
| 前端 | Vite + React + TypeScript | 交互复杂度适中，适合阅读器状态和播放器控制。 |
| 存储 | SQLite + 本地文件目录 | 单用户本机应用足够可靠，不需要数据库服务。 |
| PDF | PyMuPDF | 提取文本型 PDF 稳定，先不做 OCR。 |
| 网页 | Scrapling + Chrome 会话桥接 | 公开网页直接抓取；登录态页面通过用户授权的浏览器会话读取。 |
| TTS | macOS `say` 适配器 | 本机自带，无网络依赖；后续可替换为本地神经 TTS。 |
| 任务 | FastAPI BackgroundTasks + SQLite 状态 | 单用户场景不需要 Celery/Redis。 |

## 项目结构

后端使用扁平的 `read_along` 应用包；来源专用逻辑放在 `sources/`；前端单独放在 `web/`。

```text
src/read_along/
  api.py                # FastAPI app 和路由
  cli.py                # 顶层 read-along CLI
  config.py             # 本地数据目录、环境配置
  db.py                 # SQLite 初始化和连接
  models.py             # Pydantic DTO
  repository.py         # 数据读写
  browser.py            # 通用 Chrome 会话桥接
  importers.py          # URL/PDF 导入入口
  extractors.py         # 正文清洗、段落/句子切分
  tts.py                # TTS 适配器接口和 macOS say 实现
  storage.py            # 音频文件、上传文件、缓存路径
  sources/
    dedao.py            # 得到来源识别和专用清洗规则
web/
  src/
    api.ts
    App.tsx
    routes/
    components/
    player/
```

新增命令：

```bash
uv run --no-editable read-along serve
```

后端默认监听 `127.0.0.1:8765`。开发时前端用 Vite dev server；生产/本地使用时后端可静态服务 `web/dist`。

## 本地数据目录

默认数据目录：

```text
~/.local/share/read-along/
  read-along.sqlite3
  uploads/
  audio/
    <material_id>/
      <sentence_id>.aiff
  logs/
```

可通过环境变量覆盖：

```bash
READ_ALONG_HOME=/path/to/data
```

音频 MVP 使用 AIFF，原因是 macOS `say` 默认可靠输出 AIFF，浏览器可通过后端文件响应播放；如果浏览器兼容性不理想，再切换为 WAVE。

## 数据模型

### materials

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | 稳定材料 ID，基于来源和内容哈希生成。 |
| source_type | text | `url` 或 `pdf`。 |
| source_uri | text | URL 或本地上传文件名。 |
| title | text | 材料标题。 |
| status | text | `importing`、`ready`、`failed`。 |
| content_hash | text | 清洗后正文哈希，用于去重。 |
| error_message | text nullable | 导入失败原因。 |
| created_at | text | ISO 时间。 |
| updated_at | text | ISO 时间。 |

### paragraphs

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | 段落 ID。 |
| material_id | text fk | 所属材料。 |
| index | integer | 段落顺序。 |
| text | text | 段落文本。 |
| source_label | text nullable | PDF 页码或网页来源提示。 |

### sentences

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | 稳定句子 ID，如 `S000123`。 |
| material_id | text fk | 所属材料。 |
| paragraph_id | text fk | 所属段落。 |
| index | integer | 全文句子顺序。 |
| text | text | 句子文本。 |
| audio_status | text | `pending`、`ready`、`failed`。 |
| audio_path | text nullable | 本地音频路径。 |
| error_message | text nullable | TTS 失败原因。 |

### reading_progress

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| material_id | text pk | 所属材料。 |
| sentence_id | text | 当前句子。 |
| playback_rate | real | 当前倍速。 |
| updated_at | text | 更新时间。 |

### import_jobs

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | 导入任务 ID。 |
| status | text | `queued`、`running`、`done`、`failed`。 |
| material_id | text nullable | 完成后关联材料。 |
| message | text nullable | 当前状态或错误。 |
| created_at | text | 创建时间。 |
| updated_at | text | 更新时间。 |

## API 设计

所有接口放在 `/api` 下。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查。 |
| GET | `/api/materials` | 获取材料列表。 |
| POST | `/api/import/url` | 导入单篇网页 URL。 |
| POST | `/api/import/pdf` | 上传并导入文本型 PDF。 |
| GET | `/api/import-jobs/{job_id}` | 查询导入任务状态。 |
| GET | `/api/materials/{material_id}` | 获取材料、段落、句子和进度。 |
| PATCH | `/api/materials/{material_id}/progress` | 保存当前句子和倍速。 |
| DELETE | `/api/materials/{material_id}` | 删除材料和关联缓存。 |
| POST | `/api/materials/{material_id}/tts` | 后台生成缺失句子音频。 |
| GET | `/api/materials/{material_id}/sentences/{sentence_id}/audio` | 获取句子音频。 |

### 导入 URL 请求

```json
{
  "url": "https://example.com/article",
  "mode": "auto"
}
```

`mode` 取值：

- `auto`：公开网页优先用 Scrapling；失败时提示用户使用 Chrome 会话。
- `chrome`：使用专用 Chrome 会话桥接读取已授权页面。

### 材料详情响应

```json
{
  "id": "mat_xxx",
  "title": "文章标题",
  "source_type": "url",
  "source_uri": "https://example.com/article",
  "progress": {
    "sentence_id": "S000001",
    "playback_rate": 1.0
  },
  "paragraphs": [
    {
      "id": "P0001",
      "index": 1,
      "text": "段落文本",
      "sentences": [
        {
          "id": "S000001",
          "index": 1,
          "text": "第一句。",
          "audio_status": "ready"
        }
      ]
    }
  ]
}
```

## 核心流程

### URL 导入

1. 前端提交 URL。
2. 后端创建 `import_jobs`，状态为 `queued`。
3. 后台任务按 `mode` 获取页面正文：
   - `auto`：Scrapling 抓取公开网页并抽取正文。
   - `chrome`：连接用户手动启动并登录的专用 Chrome 会话，读取页面可见正文。
4. 清理导航、按钮、评论区、页脚等明显噪声。
5. 切分段落和句子，生成 `material_id`、`paragraph_id`、`sentence_id`。
6. 写入 SQLite。
7. 更新任务状态为 `done`。

### PDF 导入

1. 前端上传 PDF。
2. 后端保存到 `uploads/`。
3. PyMuPDF 逐页提取文本。
4. 若提取不到有效文本，任务失败并提示“不支持扫描版 PDF”。
5. 按段落和句子结构化后保存。

### 音频生成

1. 前端进入阅读页后调用 `POST /api/materials/{id}/tts`。
2. 后端查找 `audio_status=pending` 或失败后重试的句子。
3. 对每句调用 `say -o <audio_path> <sentence_text>`。
4. 成功后更新 `audio_status=ready`。
5. 失败只标记当前句，不阻断其他句子。

### 播放与高亮

1. 前端加载材料详情和进度。
2. 播放器从当前 `sentence_id` 请求音频。
3. `<audio>` 播放当前句音频，并高亮对应句子 DOM。
4. `ended` 事件触发后切换到下一句。
5. 每次切换句子时调用进度保存 API。
6. 倍速通过 `audio.playbackRate` 实现。

## 正文清洗与切分规则

MVP 使用规则优先，不使用 LLM。

- 清理空行、重复行、明显导航词、按钮词、评论区入口、页脚。
- 得到页面优先去除“用户留言”“全部”“精选”“上一篇”“下一篇”“回顶部”等区块。
- 段落按连续空行、页面块或 PDF 页文本块切分。
- 句子按中文 `。！？；`、英文 `.?!;` 和换行边界切分。
- 过短噪声句子丢弃；过长句子按逗号或长度阈值二次切分。
- 清洗后的正文生成 `content_hash`，用于重复导入判断。

## 前端设计

### 页面

- 书架页：
  - 展示材料标题、来源、导入时间、进度。
  - 提供 URL 导入入口和 PDF 上传入口。
- 阅读页：
  - 左侧或顶部显示材料标题和来源。
  - 主区域显示正文。
  - 底部固定播放器。
  - 当前句子使用背景色高亮。
- 设置面板：
  - 字号。
  - 行距。
  - 明暗主题。
  - 播放倍速。

### 状态管理

MVP 不引入复杂状态库。使用 React hooks 和局部状态：

- `useMaterials()`：材料列表。
- `useMaterial(materialId)`：材料详情。
- `usePlayer(material)`：播放、暂停、下一句、高亮。
- `useReaderSettings()`：本地阅读设置。

## 错误处理

- URL 不可访问：显示“网页无法访问或不支持直接抓取”。
- 登录态页面抓取失败：提示使用专用 Chrome 会话桥接，并说明不会保存 Cookie。
- PDF 无文本：显示“该 PDF 可能是扫描版，MVP 暂不支持 OCR”。
- `say` 不存在：显示“当前平台不支持 macOS say TTS”。
- 单句 TTS 失败：该句标记失败，播放器跳过或提示重试。
- 音频文件缺失：前端请求失败时触发重新生成或显示错误。

## 安全与边界

- 服务默认只绑定 `127.0.0.1`。
- 不实现用户系统。
- 不保存 Cookie、账号密码或导出的浏览器凭据。
- 不提供材料分享、导出课程包或公网访问能力。
- 登录态网页只处理用户自己有权访问的当前页面内容。
- 不绕过付费或访问限制。

## 依赖变更

Python 依赖新增：

- `fastapi`
- `uvicorn`
- `scrapling`
- `pymupdf`
- `python-multipart`

前端新增：

- `vite`
- `react`
- `react-dom`
- `typescript`

MVP 不引入：

- SQLAlchemy。
- Celery/Redis。
- Docker。
- OCR。
- LLM SDK。
- Tauri/Rust。

## 测试方案

### 后端单元测试

- SQLite 初始化和迁移。
- 段落/句子切分。
- 重复 URL 去重。
- PDF 文本提取失败路径。
- TTS 适配器在 `say` 不可用时的错误。
- 删除材料时清理音频路径。

### API 测试

- `GET /api/health`。
- 导入 URL 创建任务。
- 上传 PDF 创建任务。
- 获取材料详情。
- 更新阅读进度。
- 获取句子音频。

### 前端测试

- 空书架状态。
- 材料列表渲染。
- 阅读页句子渲染。
- 播放器状态切换。
- 当前句子高亮。
- 阅读设置持久化。

### 手动验收

- 导入一个公开网页。
- 导入一个文本型 PDF。
- 通过专用 Chrome 会话导入一个已授权得到单篇课程页。
- 播放音频并验证句子高亮。
- 刷新页面验证进度恢复。

## 实施顺序

1. 后端骨架、配置和 SQLite。
2. 数据模型、repository 和材料详情 API。
3. PDF 导入、文本结构化和阅读页基础渲染。
4. Scrapling URL 导入。
5. Chrome 会话桥接导入。
6. `say` TTS 适配器和音频缓存。
7. 前端播放器、高亮、倍速和进度保存。
8. 阅读设置、错误提示、删除材料和验收用例。

## 关键取舍

- 选择 SQLite 而非 ORM：减少 MVP 复杂度，数据模型小且稳定。
- 选择句子级音频文件：便于高亮、跳转和缓存，牺牲部分生成文件数量。
- 选择 `say` 优先：最快获得本地 TTS，后续通过适配器替换。
- 选择规则清洗而非 LLM：避免正文失真，保持朗读忠实。
- 选择本地 Web App：复用浏览器音频和文本能力，不引入桌面壳或 Rust。

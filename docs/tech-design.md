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
| 存储 | SQLite + SQLModel + Alembic + 本地文件目录 | 单用户本机应用不需要数据库服务；SQLModel 统一描述表模型，Alembic 管理 schema 演进。 |
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
  db.py                 # SQLModel Engine、Session 和 SQLite 连接配置
  db_models.py          # SQLModel 数据库表模型和关系
  models.py             # 领域模型和 API DTO
  material_library.py   # 阅读材料完整持久化生命周期
  repository.py         # SQLModel 细粒度读写，仅供材料库 Module 内部使用
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

开发命令：

```bash
make dev
```

`make dev` 在同一终端启动后端和前端。后端默认监听 `127.0.0.1:8765`，前端使用 Vite dev server。uv 本地开发默认使用 editable mode；部署或打包场景才考虑 `--no-editable`。生产/本地使用时后端可静态服务 `web/dist`。

## 本地数据目录

默认数据目录：

```text
~/.local/share/read-along/
  read-along.sqlite3
  backups/
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

## 数据库职责与演进

- SQLModel 表模型是运行时表结构、字段类型、关系和常规约束的主要描述来源。
- `db_models.py` 中只放 `table=True` 的数据库实体；`models.py` 保留材料库领域模型、Draft 和 API DTO。
- Repository 负责在数据库实体与领域模型之间转换；API 和材料库外部调用方不直接返回或操作数据库实体。
- Repository 使用 SQLModel `Session` 和查询表达式完成细粒度读写，不直接拼写常规 `SELECT`、`INSERT`、`UPDATE` 或 `DELETE` SQL。
- 材料库 Module 继续拥有事务边界、领域不变量、重复判断、完整视图组装和文件生命周期；调用方不直接操作 `Session`。
- 材料库 Module 的每个公开操作创建并关闭自己的 `Session`，统一决定 `commit` 或 `rollback`。
- Repository 只执行查询、`add`、`delete` 和必要的 `flush`，不得自行 `commit`、`rollback` 或关闭 `Session`。
- API 不把 `Session` 作为业务依赖直接传给路由；API 只调用材料库公开 Interface。
- SQLModel 表模型可以声明 `Relationship` 表达实体关系，但材料库读取不依赖默认懒加载行为。
- 表模型只声明服务于所有权、被动删除和必要导航的最小 Relationship，不建立完整 ORM 对象图。
- `MaterialRow` 可以声明来源、段落、句子和进度关系；子实体只保留必要的材料反向关系。
- `ParagraphRow` 与 `SentenceRow`、`ReadingProgressRow` 与 `SentenceRow`、`ImportJobRow` 与 `MaterialRow` 不依赖 Relationship 导航完成业务行为。
- 禁止通过 ORM relationship cascade 保存整篇阅读材料；Repository 继续显式插入各数据库实体。
- 完整阅读材料通过显式 SQLModel 查询批量读取材料、来源、段落、句子和进度，并在 `Session` 关闭前组装为领域/API DTO。
- 查询设计必须避免逐段或逐句懒加载造成 N+1 查询；数据库实体不跨越 `Session` 生命周期。
- Alembic 是数据库 schema 创建和演进的唯一机制。应用代码不再使用 `CREATE TABLE IF NOT EXISTS` 或启动时临时修补 schema。
- SQLModel 无法完整表达或 Alembic 无法可靠自动生成的 SQLite 约束，例如复合外键、部分唯一索引和表重建迁移，必须在 Alembic revision 中显式定义并测试。
- 业务运行时代码禁止裸 SQL；Repository 和材料库业务查询必须使用 SQLModel 或 SQLAlchemy 表达式。
- 裸 SQL 仅允许用于历史 schema 接管、Alembic revision、SQLite PRAGMA、`BEGIN IMMEDIATE` 和 SQLAlchemy 无法表达的 schema 校验。
- 允许的裸 SQL 必须集中在数据库基础设施模块，禁止字符串插值业务数据，并通过针对性测试验证；代码需说明无法使用 SQLModel 或 SQLAlchemy 表达式的原因。

### 数据库不变量

数据库继续作为关键结构不变量的最终防线，不能只依赖材料库代码提前验证。

- `materials.content_hash` 唯一。
- `(material_sources.source_type, material_sources.source_key)` 唯一。
- 每篇阅读材料最多一个主来源，通过 SQLite 部分唯一索引保证。
- 段落和句子的顺序索引在所属阅读材料内唯一。
- 句子通过复合外键保证只能引用同一阅读材料的段落。
- 阅读进度通过复合外键保证只能引用同一阅读材料的句子。
- 删除阅读材料级联删除来源身份、结构化正文和阅读进度。
- 来源类型、音频状态、导入任务状态和正数播放倍速保留 `CHECK` 约束。
- 可由 SQLModel 表模型可靠声明的约束放入模型；复合外键、部分唯一索引等特殊约束在模型元数据和 Alembic revision 中显式定义，并通过真实 SQLite schema 测试验证。

### 删除级联

- 删除级联由 SQLite 外键 `ON DELETE` 和 `ON DELETE SET NULL` 执行，不由 ORM 逐条删除子实体。
- 删除阅读材料时，Repository 只删除对应数据库实体；SQLite 级联删除来源身份、结构化正文和阅读进度，并将导入任务的材料引用设为空。
- SQLModel `Relationship` 配置 `passive_deletes=True`，避免 SQLAlchemy 为级联删除加载整篇材料的子实体。
- 每个 Engine 数据库连接都通过 SQLAlchemy 连接事件执行 `PRAGMA foreign_keys = ON`。
- 测试必须通过 SQLModel Session 执行删除，并重新查询真实 SQLite 数据验证级联结果。

### SQLite 并发与事务

- 材料库写操作保留 `BEGIN IMMEDIATE` 语义，在重复检查和插入前获取 SQLite 写锁，避免并发写入破坏原子性。
- 只读操作使用普通 SQLModel Session 事务，不提前获取写锁。
- 每个 Engine 数据库连接设置 `PRAGMA busy_timeout = 5000` 和 `PRAGMA journal_mode = WAL`，使短暂写冲突等待最多 5 秒，并允许正常写事务期间继续读取。
- 哈希计算和源文件临时副本创建尽量在获取写锁前完成，缩短写事务；最终文件重命名仍与数据库提交协调，失败时执行现有清理语义。
- 超过锁等待时间或其他数据库异常统一包装为 `MaterialLibraryError`，保留原始异常用于诊断。
- 并发测试必须覆盖同一来源、相同正文和不同正文的并发保存，不得产生重复或部分可见材料。

### 数据库测试路径

- 所有集成测试和材料库测试的 SQLite 文件必须通过与生产相同的迁移编排器和 `alembic upgrade head` 创建。
- 测试禁止使用 `SQLModel.metadata.create_all()`，避免形成绕过迁移的第二套 schema 创建路径。
- Repository 测试优先使用真实文件 SQLite，不使用与 WAL、锁、连接事件和迁移行为不同的内存数据库。
- 每种已知历史 schema 使用固定 fixture 验证无损接管；测试覆盖迁移幂等性、备份、失败拒绝启动和未知 schema 诊断。
- 增加元数据与迁移后真实 schema 的一致性测试，验证表、列、索引、外键和约束没有漂移。

### 时间字段

- 数据库表模型使用 `datetime` 表示 `created_at`、`updated_at` 等时间字段，不再让领域代码传递或解析 ISO 文本。
- 应用内时间统一为带 UTC 时区的 `datetime`；API 继续序列化为 ISO 8601，不改变接口表现。
- 历史接管编排器必须严格解析现有 ISO 时间文本并保留时间点；遇到无效历史时间时迁移失败，不静默替换。
- SQLite 不原生保存时区，不能只依赖 `DateTime(timezone=True)` 保证读回 UTC 时区。
- 项目提供 SQLAlchemy `TypeDecorator` 类型 `UTCDateTime`：拒绝无时区 `datetime`，写入前转换为 UTC，读出后恢复 `timezone.utc`。
- SQLModel 时间字段统一使用 `UTCDateTime`，并通过跨 Session 重读、排序和旧 ISO 时间迁移测试验证。

### 身份字段

- 保留现有字符串稳定 ID，不改用数据库自增整数、UUID 或隐藏代理主键。
- `material_id`、`source_id`、`paragraph_id` 和 `sentence_id` 继续由材料库根据现有规则生成；数据库不生成或改写这些 ID。
- SQLModel 字段显式定义与现有值兼容的最大长度。
- 现有材料数据、来源身份、音频缓存路径和前端句子定位继续使用相同 ID。
- `import_jobs.id` 保持现有字符串身份策略；本次数据库重构不扩大到导入任务身份变更。

### 枚举字段

- Python 领域模型和数据库实体使用现有 `StrEnum` 表达来源类型、音频状态和导入任务状态。
- SQLite 使用字符串列和显式 `CHECK` 约束，不使用 SQLAlchemy 原生 `Enum` 类型。
- 新增或删除允许值必须通过 Alembic revision 修改对应 `CHECK` 约束，不能仅修改 Python 枚举。
- 历史接管编排器保留当前字符串值，并在迁移前验证所有历史值都属于允许集合。

### 导入任务表范围

- `import_jobs` 纳入 SQLModel baseline schema 和历史数据库无损接管。
- 定义 `ImportJobRow`、状态字段和数据库约束，并保留 `material_id ON DELETE SET NULL`。
- 本次数据库重构不新增导入任务的业务 Repository、材料库 Interface 或 API。
- 导入任务创建、状态更新、查询和错误展示仍属于后续独立 backlog 任务。

### 接管现有本地数据库

采用 SQLModel 和 Alembic 时必须无损保留现有本地数据库，不允许通过清空并重建数据库完成切换。

- 历史接管编排器负责识别并接管来源字段仍内嵌在 `materials` 的早期 schema、当前六表 schema，以及已知的半迁移状态。
- 每个已知历史 schema 使用明确指纹识别，指纹包含表、列、索引、外键和 Alembic revision；空数据库按全新数据库处理。
- 历史接管编排器只处理明确支持的历史状态，不进行猜测性修复。
- 遇到未知列组合、缺失必要表、非法枚举值、无效时间或悬空外键时，创建备份、输出具体诊断并拒绝迁移和启动。
- 提供独立数据库诊断命令，但启动流程不得自动删除、忽略或替换异常数据。
- 启动迁移编排器负责历史库接管：识别已知 schema、迁移为 SQLModel baseline schema、校验数据与约束，然后写入 baseline Alembic revision。
- Alembic revision 链只描述 baseline 及其后的正常 schema 演进，不混入多种历史 schema 的条件分支。
- 接管完成后，所有数据库统一执行 `alembic upgrade head`；后续不再通过接管编排器修改已纳入 Alembic 管理的 schema。
- 迁移必须保留阅读材料、来源身份、结构化正文、阅读进度和导入任务。
- 应用启动时自动执行 `alembic upgrade head`，不要求本地用户手动维护数据库版本。
- 存在待执行迁移时，先创建数据库文件备份；迁移失败时保留原数据库和备份，并阻止应用使用未完成迁移的数据库启动。
- 备份放在 `backups/`，文件名包含迁移前 revision 和 UTC 时间；使用 SQLite backup API 创建一致性快照，不直接复制可能处于 WAL 状态的数据库文件。
- 仅在确实存在待执行 migration 时创建备份；成功迁移前备份自动保留最近 3 个，失败迁移对应的备份永久保留且不参与自动清理。
- schema migration 不修改上传源文件和音频缓存，因此迁移备份不包含这些文件。
- 新数据库同样通过 Alembic 从空库迁移到最新 revision，不使用 `SQLModel.metadata.create_all()`。
- Alembic 接管成功后，删除 `db.py` 中现有的手写 schema 创建、旧表复制和半迁移修复逻辑。
- 后续 schema 变化只通过新的 Alembic revision 进行，不再增加启动时条件修复分支。

已知 schema 状态及处理方式：

| 状态 | 识别要点 | 处理方式 |
| --- | --- | --- |
| 空数据库 | 不存在业务表和 `alembic_version` | 直接执行 `alembic upgrade head`，不创建备份。 |
| 早期五表 schema | 存在 `materials`、`paragraphs`、`sentences`、`reading_progress`、`import_jobs`；`materials` 仍包含来源和状态字段；不存在 `material_sources` 和 `alembic_version` | 严格校验全部表、索引、外键和数据后，转换为 baseline schema 并写入 baseline revision。 |
| 当前六表 schema | 存在 `material_sources`；`materials` 已移除早期来源和状态字段；不存在 `alembic_version` | 严格校验 schema 和数据后直接写入 baseline revision，不重写业务数据。 |
| 已知半迁移 schema | 主体已是当前六表 schema，但 `material_sources.material_id` 外键错误引用 `materials_legacy` | 重建 `material_sources`、校验数据与约束后写入 baseline revision。 |
| Alembic 管理的数据库 | 存在受支持的 `alembic_version` revision，且 schema 指纹匹配该 revision | 创建必要备份后执行待运行的正常 Alembic revisions。 |
| 未知或损坏状态 | 任一必要表、列、索引、外键、revision 或数据校验不匹配已知状态 | 创建并永久保留失败备份，输出具体诊断并拒绝启动。 |

实现中的固定 fixture 必须完整描述每个已知状态的表、列、索引、外键和代表性数据；任何只匹配部分特征的数据库都按未知状态处理。

## 数据模型

### materials

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | 稳定材料 ID，基于结构化正文哈希生成。 |
| title | text | 材料标题。 |
| content_hash | text | 清洗后正文哈希，用于去重。 |
| created_at | datetime | 带 UTC 时区语义的创建时间。 |
| updated_at | datetime | 带 UTC 时区语义的更新时间。 |

阅读材料只表示已成功原子保存的结果，不保存导入状态或导入错误。`queued`、`running`、`done`、`failed` 和错误信息属于 `import_jobs`。

### material_sources

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | 来源身份 ID。 |
| material_id | text fk | 所属阅读材料。 |
| source_type | text | `url` 或 `pdf`。 |
| source_key | text | 同一来源的稳定身份键。 |
| source_uri | text | 用于展示和回查的 URL 或上传文件名。 |
| source_path | text nullable | 材料库管理的内部源文件路径。 |
| is_primary | integer | 是否为首次导入的主来源。 |
| created_at | datetime | 带 UTC 时区语义的创建时间。 |

同一 `source_type` 和 `source_key` 只能对应一个来源身份；一篇阅读材料可以关联多个来源身份。

关键不变量：

- `materials.content_hash` 唯一，同一结构化正文只对应一篇阅读材料。
- 每篇阅读材料恰好有一个主来源。
- 来源身份一旦关联阅读材料，不会被导入行为重新指向其他阅读材料。

来源键生成规则：

- URL：规范化 URL，移除 fragment，规范化 scheme、host 和默认端口，保留 path 和 query。
- PDF：上传文件字节的 SHA-256；`source_uri` 保留原文件名。

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
| updated_at | datetime | 带 UTC 时区语义的更新时间。 |

### import_jobs

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | text pk | 导入任务 ID。 |
| status | text | `queued`、`running`、`done`、`failed`。 |
| material_id | text nullable | 完成后关联材料。 |
| message | text nullable | 当前状态或错误。 |
| created_at | datetime | 带 UTC 时区语义的创建时间。 |
| updated_at | datetime | 带 UTC 时区语义的更新时间。 |

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
  "primary_source": {
    "source_type": "url",
    "source_uri": "https://example.com/article"
  },
  "sources": [
    {
      "source_type": "url",
      "source_uri": "https://example.com/article"
    }
  ],
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

## 材料库持久化 Module

材料库持久化 Module 是阅读材料持久化的外部 seam。PDF、网页和得到导入 Module 只生成不含持久化字段的 `ReadingMaterialDraft`；调用方不理解 SQLite、事务、ID 分配、时间戳、文件布局或材料详情组装。

### 外部 Interface

```python
class MaterialLibrary:
    def save(self, draft: ReadingMaterialDraft) -> MaterialDetail: ...
    def list_shelf(self) -> list[MaterialSummary]: ...
    def get(self, material_id: str) -> MaterialDetail: ...
    def save_progress(
        self,
        material_id: str,
        sentence_id: str,
        playback_rate: float,
    ) -> ReadingProgress: ...
    def delete(self, material_id: str) -> None: ...
```

- `save` 原子保存完整阅读材料，或在重复导入时返回现有阅读材料。
- `list_shelf` 返回按最近更新时间排序的书架摘要。
- `get` 返回包含有序段落、有序句子和阅读进度的完整阅读视图。
- `save_progress` 验证材料、句子归属和倍速后原子覆盖阅读进度。
- `delete` 幂等删除阅读材料，并在提交后清理源文件和音频缓存。
- 独立段落和句子查询属于材料库 Module 的内部 Interface，不向通用调用方暴露。

### 保存 Draft

`ReadingMaterialDraft` 只包含来源事实、可选源文件和结构化正文：

- `source_type`、`source_uri`、`title`。
- 可选 `source_file`；调用方始终保留原文件所有权。
- 有序段落；每段包含正文、可选来源标记和有序句子文本。
- 不包含 ID、全局顺序、`content_hash`、状态、时间戳、音频字段或阅读进度。

材料库 Module 验证 Draft，基于来源事实生成 `source_key`，基于结构化正文计算 `content_hash`，并生成全部持久化字段。

### 重复导入

- 来源相同且结构化正文相同：返回现有阅读材料。
- 来源不同但结构化正文相同：新增来源身份并返回现有阅读材料。
- 来源相同但结构化正文不同：返回 `SourceChangedError`，不覆盖正文、进度或音频。
- 刷新已有来源是后续独立能力。
- 阅读材料保留首次导入的标题；新增来源身份不覆盖标题。
- 书架和阅读视图展示首次导入的主来源，同时可以返回全部来源身份。
- 为现有阅读材料新增来源身份时，不复制新的源文件，新增来源身份的 `source_path` 为空。

### 原子性与文件

- 调用返回成功前，阅读材料对调用方完全不可见。
- 阅读材料、来源身份、段落和句子在一个 SQLite 事务中保存。
- 源文件复制到材料库临时路径，在数据库事务提交前原子重命名到最终路径。
- 数据库提交失败时删除最终文件；进程中断最多留下可清理的孤立文件。
- 任一步失败都回滚数据库并清理临时文件。
- 进程中断不留下部分可见阅读材料；启动时清理孤立文件。
- 删除时先事务删除数据库记录，再尽力清理源文件和音频缓存；清理失败记录可重试任务。

### 错误模式

- `InvalidDraftError`：结构化正文为空、不一致或字段非法。
- `SourceChangedError`：来源相同但结构化正文不同。
- `MaterialNotFoundError`：读取或保存进度时阅读材料不存在。
- `InvalidProgressError`：句子不属于阅读材料或倍速非法。
- `MaterialLibraryError`：SQLite、文件复制、事务等 Implementation 失败。

导入失败不持久化 `failed` 阅读材料；失败状态由未来的导入任务 Module 记录。

## 核心流程

### URL 导入

1. 前端提交 URL。
2. 后端创建 `import_jobs`，状态为 `queued`。
3. 后台任务按 `mode` 获取页面正文：
   - `auto`：Scrapling 抓取公开网页并抽取正文。
   - `chrome`：连接用户手动启动并登录的专用 Chrome 会话，读取页面可见正文。
4. 清理导航、按钮、评论区、页脚等明显噪声。
5. 切分段落和句子，形成结构化正文。
6. 将来源事实和结构化正文提交给材料库持久化 Module 原子保存。
7. 更新任务状态为 `done`。

### PDF 导入

1. 前端上传 PDF。
2. 后端将上传内容保存到调用方临时文件。
3. PyMuPDF 逐页提取文本。
4. 若提取不到有效文本，任务失败并提示“不支持扫描版 PDF”。
5. 按段落和句子结构化后提交给材料库持久化 Module 原子保存。

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

- `alembic`
- `fastapi`
- `uvicorn`
- `scrapling`
- `sqlmodel`
- `pymupdf`
- `python-multipart`

前端新增：

- `vite`
- `react`
- `react-dom`
- `typescript`

MVP 不引入：

- Celery/Redis。
- Docker。
- OCR。
- LLM SDK。
- Tauri/Rust。

## 测试方案

### 后端单元测试

- SQLModel metadata 与 Alembic baseline schema 一致性。
- 新数据库创建、已知历史数据库无损接管、备份和迁移失败拒绝启动。
- SQLModel Session、SQLite 外键级联、写锁等待和并发保存。
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

## MVP 整体实施顺序

1. 后端骨架、配置和 SQLite。
2. 数据模型、repository 和材料详情 API。
3. PDF 导入、文本结构化和阅读页基础渲染。
4. Scrapling URL 导入。
5. Chrome 会话桥接导入。
6. `say` TTS 适配器和音频缓存。
7. 前端播放器、高亮、倍速和进度保存。
8. 阅读设置、错误提示、删除材料和验收用例。

## 数据库重构实施拆分

数据库重构按以下顺序拆成独立小任务。每个任务完成后现有 API 和材料库行为都必须保持可用，不允许在中间状态要求清空本地数据库。

1. **SQLModel 与 Alembic baseline**：添加依赖、`UTCDateTime`、SQLModel 表模型、Alembic 配置和 baseline revision；验证空数据库经 Alembic 创建后的真实 schema 与 metadata 一致。生产启动和 Repository 暂不切换。
2. **历史 schema 诊断**：实现只读 schema 指纹识别、数据校验和独立诊断命令；使用固定 fixture 覆盖空数据库、早期五表、当前六表、已知半迁移和未知状态。不得修改被诊断数据库。
3. **历史数据库接管与备份**：实现 SQLite backup API、保留策略和历史接管编排器；将全部已知状态无损接管到 baseline，未知或损坏状态保留备份并拒绝迁移。生产启动暂不切换。
4. **启动迁移切换**：应用启动改用历史接管编排器和 `alembic upgrade head`；新库和旧库统一走迁移路径，随后删除 `db.py` 中手写 `SCHEMA`、旧表复制和半迁移修复逻辑。Repository 暂时保持现有兼容读写。
5. **SQLModel Repository 与事务切换**：Repository 改用 SQLModel `Session` 和表达式，材料库拥有 Session、`BEGIN IMMEDIATE`、提交和回滚；移除业务运行时裸 SQL，并补齐级联删除、跨 Session UTC 时间、并发保存和完整材料批量读取测试。

第一项是推荐的下一个最小任务；它只建立可验证的目标 schema，不接触现有数据库或切换生产运行路径。

## 关键取舍

- 选择 SQLite + SQLModel + Alembic：保留单机 SQLite 的简单部署，同时统一表模型、查询和可测试的 schema 演进。
- 选择句子级音频文件：便于高亮、跳转和缓存，牺牲部分生成文件数量。
- 选择 `say` 优先：最快获得本地 TTS，后续通过适配器替换。
- 选择规则清洗而非 LLM：避免正文失真，保持朗读忠实。
- 选择本地 Web App：复用浏览器音频和文本能力，不引入桌面壳或 Rust。

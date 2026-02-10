# Linker Mind - 第二大脑 + 创作工作台

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Flask](https://img.shields.io/badge/flask-3.x-orange)
![PostgreSQL](https://img.shields.io/badge/postgresql-13+-blue)

**一个"第二大脑 + 创作工作台"系统，支持从任意来源采集内容，系统化整理，持续提炼，并支持创造性输出。**

</div>

---

## 目录

- [核心功能](#核心功能)
- [🎬 抖音视频深度分析](#🎬-抖音视频深度分析)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [数据库设计](#数据库设计)
- [API端点](#api端点)
- [内容处理器](#内容处理器)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

---

## 核心功能

### 📥 内容采集

支持10+种内容类型：

| 类型 | 来源 | 说明 |
|------|------|------|
| 网页文章 | Firecrawl | 通用网页内容抓取 |
| Twitter/X | Tavily API | 推文、长文、线程 |
| 微信公众号 | MCP WebReader | 公众号文章提取 |
| 抖音 | requests + 页面解析 | 视频信息 + 深度分析 |
| YouTube/B站 | yt-dlp | 视频元数据及字幕 |
| 电子书 | epubkit | EPUB/PDF解析 |
| 播客/音频 | whisper | 音频转文字 |
| 图片 | OCR | 图片文字提取 |

### 🎬 抖音视频深度分析

**功能特性**：

```
┌─────────────────────────────────────────────────────────────┐
│                    抖音视频分析流程                           │
├─────────────────────────────────────────────────────────────┤
│  1️⃣ 基本提取 (即时完成)                                       │
│     ├── 标题、作者、描述                                      │
│     ├── 点赞/评论/分享/收藏数据                               │
│     ├── 话题标签 (#xxx)                                       │
│     └── 封面图片 + 视频播放链接                                │
├─────────────────────────────────────────────────────────────┤
│  2️⃣ 深度分析 (可选，需视频下载)                               │
│     ├── 视频下载 (yt-dlp)                                     │
│     ├── 音频提取 (ffmpeg)                                     │
│     ├── 语音转录 (OpenAI Whisper)                             │
│     ├── LLM 分析摘要 + 关键点                                 │
│     └── 关键画面提取 (5帧均匀分布)                             │
└─────────────────────────────────────────────────────────────┘
```

**使用方式**：

```bash
# 基本提取 (默认)
POST /api/process
{"url": "https://v.douyin.com/xxx/", "enable_ai": true}

# 深度分析 (需要安装额外依赖)
POST /api/process
{"url": "https://v.douyin.com/xxx/", "enable_ai": true, "deep_analysis": true}
```

**提取的数据**：

| 数据项 | 基本提取 | 深度分析 |
|--------|---------|---------|
| 标题 | ✅ | ✅ |
| 作者 | ✅ | ✅ |
| 完整文案 | ✅ (描述) | ✅ (语音转录) |
| 统计数据 | ✅ | ✅ |
| 话题标签 | ✅ | ✅ |
| 封面图片 | ✅ | ✅ |
| 视频链接 | ✅ | ✅ |
| 时长 | ✅ | ✅ |
| 语音转录 | ❌ | ✅ |
| LLM摘要 | ❌ | ✅ |
| 关键点 | ❌ | ✅ |
| 关键画面 | ❌ | ✅ |

**依赖安装**：

```bash
# 视频下载
pip install yt-dlp

# 语音转录 (需要 Rust 编译)
pip install openai-whisper

# ffmpeg (macOS)
brew install ffmpeg
```

**注意**：抖音视频下载需要登录认证才能完整下载，无登录时使用基本提取模式。

### 🤖 AI智能分析

- **自动摘要** - DeepSeek API 生成内容摘要
- **关键点提取** - 识别核心要点
- **话题标签** - 自动生成相关话题标签
- **质量评分** - 内容质量评估

### 📚 PARA组织方法

基于 Tiago Forte 的 PARA 方法：

```
📁 Projects (项目)
   └── 有明确目标和时间范围的短期任务

📚 Areas (领域)
   └── 长期关注的职责范围

📦 Resources (资源)
   └── 未来可能用到的参考素材

🗃️ Archive (归档)
   └── 已完成或不活跃的项目
```

### 📝 渐进式总结

基于 Andy Matuschak 的渐进式总结理念：

| 层级 | 名称 | 说明 |
|------|------|------|
| Layer 1 | 高亮 | 标记重要段落 |
| Layer 2 | 加粗 | 提炼核心观点 |
| Layer 3 | 超级笔记 | 优中之优的内容 |
| Layer 4 | 自己总结 | 用自己的话总结 |
| Layer 5 | 深度思考 | 加入个人思考形成新知识 |

### 🔗 双向链接

借鉴 Roam Research/Obsidian 的链接理念：

```
[A] ──引用──▶ [B]     [A] ──相关──▶ [B]
     ◀──被引用──       ◀──相反──
```

**链接类型**：
- `reference` - 引用/参考
- `related` - 相关内容
- `opposes` - 反对/反驳
- `extends` - 延伸/扩展
- `example` - 例证
- `inspired` - 灵感来源

### 💡 创作工作台

```
┌─────────────────────────────────────────┐
│  创作项目                                │
│  ├── 素材管理 (图片/文章/视频/金句)        │
│  ├── AI大纲生成                          │
│  ├── 引用追踪                            │
│  └── 内容缺口分析                         │
└─────────────────────────────────────────┘
```

### 🌳 技能树

```
Python 技能树
├── 基础语法 (入门)
│   ├── 变量和数据类型 ⭐⭐⭐⭐⭐
│   ├── 控制流 ⭐⭐⭐⭐
│   └── 函数定义 ⭐⭐⭐⭐
├── Web 开发 (中级)
│   ├── Flask 框架 ⭐⭐⭐
│   └── API 设计 ⭐⭐⭐⭐
└── AI/ML (高级)
    ├── TensorFlow ⭐⭐⭐
    └── PyTorch ⭐⭐⭐
```

### 🕸️ 知识图谱

- 力导向图 - 展示内容关系
- 主题聚类 - 发现隐含关联
- 学习路径 - 推荐学习路线
- 时间线 - 学习历程可视化

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Layer                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Flask App  │  │ Blueprints  │  │   Jinja2 Templates │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                       Service Layer                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Content │ Node │ Note │ Link │ Inbox │ Creation │ ... │ │
│  └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      Repository Layer                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  content_repository │ node_repository │ note_repository │ │
│  └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                     Database Layer                             │
│  ┌────────────────┐  ┌────────────────────────────────────┐ │
│  │  PostgreSQL     │  │   JSONB索引 / GIN索引             │ │
│  │  (生产环境)      │  │   全文搜索支持                     │ │
│  └────────────────┘  └────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端 | Flask 3.x | Web框架 |
| 数据库 | PostgreSQL 13+ | 主数据库 |
| 备选数据库 | SQLite | 开发/测试 |
| AI分析 | DeepSeek API | 摘要/标签生成 |
| 网页抓取 | Firecrawl | 网页内容提取 |
| Twitter抓取 | Tavily API | X平台内容 |
| 抖音抓取 | requests + BeautifulSoup | 页面解析+深度分析 |
| 视频处理 | yt-dlp | 视频下载 |
| 音频转写 | OpenAI Whisper | 语音转文字 |
| 关键帧提取 | ffmpeg | 视频帧截图 |
| 前端 | D3.js + Vanilla JS | 可视化/交互 |
| 模板 | Jinja2 | HTML渲染 |

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/linker-mind.git
cd linker-mind
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件填入API密钥
```

### 4. 启动服务

```bash
# 开发模式
python run.py

# 生产模式
python run.py --prod --workers 4

# 访问 http://127.0.0.1:5000
```

### 5. 命令行使用

```bash
# 处理URL
python main.py --url https://www.anthrop.com/article

# 保存文本笔记
python main.py --text "今天学习了Python装饰器"

# 搜索内容
python main.py --search "Python 装饰器"

# 查看统计
python main.py --stats
```

---

## 项目结构

```
linker-mind/
├── app/                          # Flask应用层
│   ├── __init__.py              # 应用工厂
│   ├── blueprints/              # 路由模块 (11个Blueprint)
│   │   ├── content_bp.py        # 内容CRUD
│   │   ├── node_bp.py          # PARA组织
│   │   ├── note_bp.py           # 笔记管理
│   │   ├── link_bp.py          # 双向链接
│   │   ├── inbox_bp.py         # 收件箱
│   │   ├── creation_bp.py       # 创作项目
│   │   ├── session_bp.py        # 学习会话
│   │   ├── skill_bp.py          # 技能树
│   │   ├── graph_bp.py          # 知识图谱
│   │   ├── search_bp.py         # 搜索
│   │   └── api_bp.py           # 复合API
│   ├── templates/               # Jinja2模板
│   │   ├── index.html          # 首页/仪表盘
│   │   ├── detail.html         # 内容详情
│   │   ├── inbox.html          # 收件箱
│   │   ├── nodes.html          # PARA组织
│   │   ├── creations.html       # 创作项目
│   │   ├── skills.html         # 技能树
│   │   ├── graph.html          # 知识图谱
│   │   └── components/          # 可复用组件
│   └── utils/                   # 工具函数
│       ├── formatters.py        # 格式化函数
│       ├── pagination.py        # 分页工具
│       └── api.py              # API响应封装
│
├── services/                    # 业务逻辑层 (10+个服务)
│   ├── content_service.py       # 内容管理
│   ├── node_service.py          # 节点管理
│   ├── note_service.py          # 笔记服务
│   ├── link_service.py          # 链接服务
│   ├── inbox_service.py         # 收件箱服务
│   ├── creation_service.py      # 创作项目
│   ├── creation_assistant.py    # AI创作助手
│   ├── session_service.py       # 学习会话
│   ├── skill_service.py         # 技能服务
│   ├── graph_service.py         # 知识图谱
│   ├── search_service.py        # 搜索服务
│   ├── summary_service.py       # 总结服务
│   └── video_analysis_service.py # **视频深度分析**
│
├── repositories/                 # 数据访问层
│   ├── base.py                  # Repository基类
│   ├── content_repository.py    # 内容仓储
│   ├── node_repository.py       # 节点仓储
│   └── ...
│
├── database/                    # 数据库层
│   ├── db_interface.py         # 统一数据库接口
│   ├── connection.py             # SQLite连接
│   ├── pg_connection.py         # PostgreSQL连接
│   └── schema_pg.sql           # PostgreSQL Schema
│
├── processors/                  # 内容处理器
│   ├── content_processor.py      # 基础处理器
│   ├── twitter_processor.py     # Twitter/X处理器
│   ├── douyin_processor.py      # **抖音视频处理器** (基础+深度分析)
│   ├── video_processor.py       # 视频处理器
│   ├── book_processor.py        # 电子书处理器
│   ├── audio_processor.py       # 音频处理器
│   ├── ocr_processor.py         # OCR处理器
│   ├── weixin_processor.py      # 微信公众号
│   └── ...
│
├── static/                       # 静态资源
│   ├── css/
│   ├── js/
│   └── img/
│
├── run.py                       # 应用入口
├── main.py                      # CLI入口
├── requirements.txt             # Python依赖
├── .env                         # 环境配置
└── README.md                    # 本文档
```

---

## 数据库设计

### 核心表

#### `contents` - 内容表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | 主键 |
| source_type | VARCHAR(50) | 来源类型 |
| content_type | VARCHAR(50) | 内容类型 |
| title | VARCHAR(500) | 标题 |
| url | TEXT | 原始URL |
| raw_content | TEXT | 完整内容(Markdown) |
| summary | TEXT | AI摘要 |
| main_content | TEXT | 内容前1000字符 |
| ai_analysis | JSONB | AI分析结果 |
| metadata | JSONB | 处理元数据 |
| media | JSONB | 媒体信息(封面/图片) |
| favorited | BOOLEAN | 收藏标记 |
| archived | BOOLEAN | 归档标记 |
| reading_progress | NUMERIC | 阅读进度(0-100) |
| tags | TEXT | 标签(逗号分隔) |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### `nodes` - 组织节点表 (PARA)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | 主键 |
| node_type | VARCHAR(20) | PROJECT/AREA/RESOURCE/ARCHIVE |
| name | VARCHAR(200) | 节点名称 |
| description | TEXT | 描述 |
| parent_id | VARCHAR(64) | 父节点ID |
| status | VARCHAR(20) | ACTIVE/INACTIVE/COMPLETED/ARCHIVED |
| icon | VARCHAR(10) | 图标 |
| tags | JSONB | 标签 |
| target_date | DATE | 目标日期 |
| color | VARCHAR(20) | 颜色 |
| order_index | INT | 排序 |

#### `notes` - 笔记表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | 主键 |
| content_id | VARCHAR(64) | 关联内容ID |
| note_type | VARCHAR(50) | 笔记类型 |
| content | TEXT | 笔记内容 |
| highlights | JSONB | 高亮列表 |
| summary_layers | JSONB | 渐进式总结 |
| summary_layer | INT | 总结层次(0-5) |
| project_tags | JSONB | 项目标签 |

#### `links` - 链接表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | 主键 |
| source_id | VARCHAR(64) | 源内容ID |
| target_id | VARCHAR(64) | 目标内容ID |
| link_type | VARCHAR(50) | 链接类型 |
| context | TEXT | 上下文说明 |
| strength | FLOAT | 链接强度 |

#### `skills` - 技能表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | 主键 |
| skill_name | VARCHAR(200) | 技能名称 |
| category | VARCHAR(100) | 分类 |
| level | VARCHAR(20) | BEGINNER/INTERMEDIATE/ADVANCED/EXPERT |
| parent_ids | JSONB | 父技能ID列表 |
| description | TEXT | 描述 |

#### `learning_sessions` - 学习会话表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | 主键 |
| content_id | VARCHAR(64) | 内容ID |
| started_at | TIMESTAMP | 开始时间 |
| duration | INT | 学习时长(秒) |
| highlights_count | INT | 高亮数量 |
| notes_added | INT | 笔记数量 |
| summary_layer | INT | 总结层次 |
| comprehension | INT | 理解程度(1-5) |
| confidence | INT | 掌握信心(1-5) |
| mood | VARCHAR(50) | 学习心情 |

### 关联表

| 表名 | 说明 |
|------|------|
| node_contents | 节点-内容关联 |
| content_tags | 内容-标签关联 |
| skill_contents | 技能-内容关联 |

### PostgreSQL 特性

- **JSONB** - 存储灵活数据(ai_analysis, metadata, media)
- **GIN索引** - 支持JSONB和全文搜索
- **Trigger** - 自动更新updated_at时间戳

---

## API端点

### 内容API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 首页/仪表盘 |
| GET | `/content/<id>` | 内容详情页 |
| GET | `/api/contents` | 内容列表(分页) |
| POST | `/api/contents` | 创建内容(URL/文本) |
| POST | `/api/process` | **处理URL** |
| GET | `/api/contents/<id>` | 获取内容 |
| PUT | `/api/contents/<id>` | 更新内容 |
| DELETE | `/api/contents/<id>` | 删除内容 |
| POST | `/api/contents/<id>/favorite` | 切换收藏 |
| POST | `/api/contents/<id>/archive` | 切换归档 |
| PUT | `/api/contents/<id>/progress` | 更新阅读进度 |

**处理URL请求**：

```json
POST /api/process
{
    "url": "https://v.douyin.com/xxx/",
    "enable_ai": true,
    "deep_analysis": false  // 可选：是否进行深度分析(视频)
}
```

响应：

```json
{
    "success": true,
    "data": {
        "id": "content_xxx",
        "title": "内容标题",
        "summary": "AI摘要",
        "source_type": "douyin",
        "content_type": "article",
        "deep_analysis_enabled": false
    }
}
```

### 组织API (PARA)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/nodes` | PARA组织页面 |
| GET | `/api/nodes` | 节点列表 |
| POST | `/api/nodes` | 创建节点 |
| GET | `/api/nodes/<id>` | 节点详情 |
| PUT | `/api/nodes/<id>` | 更新节点 |
| DELETE | `/api/nodes/<id>` | 删除节点 |
| POST | `/api/nodes/<id>/contents` | 添加内容到节点 |
| DELETE | `/api/nodes/<id>/contents/<cid>` | 从节点移除内容 |
| GET | `/api/nodes/tree` | 获取树形结构 |

### 笔记API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/notes` | 笔记列表 |
| POST | `/api/notes` | 创建笔记 |
| GET | `/api/notes/<id>` | 笔记详情 |
| PUT | `/api/notes/<id>` | 更新笔记 |
| DELETE | `/api/notes/<id>` | 删除笔记 |
| POST | `/api/contents/<id>/highlights` | 添加高亮(Layer1) |
| POST | `/api/contents/<id>/summary` | 添加总结 |

### 链接API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/links` | 链接列表 |
| POST | `/api/links` | 创建链接 |
| DELETE | `/api/links/<id>` | 删除链接 |
| GET | `/api/contents/<id>/links` | 获取正向链接 |
| GET | `/api/contents/<id>/backlinks` | 获取反向链接 |
| GET | `/api/links/suggestions` | 链接建议 |

### 收件箱API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/inbox` | 收件箱页面 |
| POST | `/api/inbox` | 添加到收件箱 |
| GET | `/api/inbox` | 收件箱列表 |
| PUT | `/api/inbox/<id>` | 处理项目 |
| DELETE | `/api/inbox/<id>` | 删除 |
| GET | `/api/inbox/stats` | 统计信息 |

### 创作API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/creations` | 创作项目列表 |
| GET | `/creations/<id>` | 创作工作台 |
| POST | `/api/creations` | 创建项目 |
| PUT | `/api/creations/<id>` | 更新项目 |
| POST | `/api/creations/<id>/materials` | 添加素材 |
| POST | `/api/creations/<id>/outline` | 生成大纲 |
| POST | `/api/creations/<id>/publish` | 发布 |

### 技能API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/skills` | 技能树页面 |
| GET | `/api/skills` | 技能列表 |
| POST | `/api/skills` | 创建技能 |
| GET | `/api/skills/<id>` | 技能详情 |
| PUT | `/api/skills/<id>` | 更新技能 |
| POST | `/api/skills/<id>/contents` | 添加学习内容 |
| GET | `/api/skills/tree` | 获取技能树 |

### 知识图谱API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/graph` | 知识图谱页面 |
| GET | `/api/graph` | 力导向图数据 |
| GET | `/api/graph/cluster` | 主题聚类 |
| GET | `/api/graph/path` | 学习路径 |

### 搜索API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/search` | 统一搜索 |
| GET | `/api/search/suggestions` | 搜索建议 |

### 复合API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/dashboard` | 仪表盘数据 |
| GET | `/api/export/<format>` | 导出数据 |

---

## 内容处理器

### 处理器架构

```
ContentProcessor (抽象基类)
├── WebPageProcessor      # 网页内容
├── SocialMediaProcessor # 社交媒体
├── TwitterProcessor     # Twitter/X (Tavily)
├── DouyinProcessor      # 抖音视频 (基础 + 深度分析)
├── VideoProcessor       # 通用视频 (YouTube/B站)
├── WeixinProcessor      # 微信公众号
├── TextMemoProcessor    # 纯文本
├── BookProcessor        # EPUB/PDF
├── AudioProcessor       # 音频
├── OCRProcessor         # 图片OCR
└── ThreadProcessor      # 推文串
```

### 抖音处理器特性

```python
class DouyinProcessor(ContentProcessor):
    """抖音视频处理器 - 支持深度分析"""

    def extract(self, url_info: URLInfo, deep_analysis: bool = False) -> ProcessedContent:
        """提取抖音视频内容

        Args:
            url_info: URL信息
            deep_analysis: 是否进行深度分析(语音转录+关键帧)
        """
        # 基本提取: 即时完成
        # - 标题、作者、描述
        # - 统计数据(点赞/评论/分享)
        # - 话题标签
        # - 封面图片、视频链接

        # 深度分析: 需额外30-60秒
        # - 下载视频 (yt-dlp)
        # - 提取音频 (ffmpeg)
        # - 语音转录 (Whisper)
        # - LLM分析摘要和关键点
        # - 提取5个关键画面
```

### 处理器接口

```python
class ContentProcessor(ABC):
    @abstractmethod
    def can_process(self, url_info: URLInfo) -> bool:
        """检测是否能处理该URL"""

    @abstractmethod
    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """提取内容"""
```

### ProcessedContent 数据结构

```python
@dataclass
class ProcessedContent:
    id: str                    # 内容ID
    timestamp: str            # 处理时间
    raw_input: str            # 原始输入
    source_type: str         # 来源类型
    platform: str             # 平台

    # 内容字段
    raw_content: str         # 完整Markdown内容
    content: Dict            # 结构化内容
    media: Dict              # 媒体信息
    ai_analysis: Dict        # AI分析结果
    processing_info: Dict    # 处理元数据
```

### URL检测

```python
URLDetector.detect(url) -> URLInfo
├── url_type: WEBPAGE/TWITTER/WECHAT/DOUYIN/VIDEO/UNKNOWN
├── platform: str (twitter/weixin/bilibili/youtube...)
├── extracted_id: str (从URL提取的ID)
└── url: str (原始URL)
```

---

## 配置说明

### 环境变量

```bash
# ==================== 数据库配置 ====================
DB_TYPE=postgresql                    # sqlite 或 postgresql

# PostgreSQL 连接
PGHOST=117.72.207.52
PGPORT=5432
PGDATABASE=linker-mind
PGUSER=postgres
PGPASSWORD=your_password

# ==================== API Keys ====================
# DeepSeek AI 分析 (必需)
DEEPSEEK_API_KEY=sk-xxx

# Firecrawl 网页抓取 (必需)
FIRECRAWL_API_KEY=fc-xxx

# Tavily Twitter 抓取 (推荐)
TAVILY_API_KEY=tvly-xxx

# ==================== 应用配置 ====================
SECRET_KEY=your-secret-key
FLASK_DEBUG=false
```

### 数据库初始化

```bash
# 初始化数据库表结构
python run.py --init

# 从JSON迁移到PostgreSQL
python run.py --migrate
```

---

## 常见问题

### Q: 如何添加新的内容处理器?

1. 创建处理器类继承 `ContentProcessor`
2. 实现 `can_process()` 和 `extract()` 方法
3. 在 `ProcessorFactory.create_default()` 中注册

### Q: 为什么内容没有显示?

1. 检查数据库连接是否正确
2. 确认内容未被归档 (`archived = FALSE`)
3. 检查 `created_at` 时间戳

### Q: 如何启用AI分析?

在 `.env` 中设置 `DEEPSEEK_API_KEY`

### Q: Twitter内容提取失败?

需要配置 `TAVILY_API_KEY` 用于Twitter/X内容抓取

### Q: 图片没有显示?

1. 检查 `media` 字段是否有封面图片
2. 确认图片URL可访问
3. 检查是否跨域问题

### Q: 抖音视频深度分析需要什么?

1. **基本提取** (默认): 即时完成，无需额外依赖
   - 标题、作者、描述
   - 点赞/评论/分享/收藏数据
   - 话题标签
   - 封面图片和视频链接

2. **深度分析**: 需要安装以下依赖
   ```bash
   pip install yt-dlp openai-whisper
   brew install ffmpeg
   ```
   - 完整语音转录 (Whisper)
   - LLM智能摘要
   - 关键画面提取
   - **注意**: 抖音视频下载需要登录认证

### Q: 抖音视频下载失败?

抖音视频有版权保护，需要登录状态才能下载。解决方案：
1. 使用基本提取模式（无需登录）
2. 在浏览器中登录抖音后导出 Cookie
3. 使用浏览器扩展预处理视频

---

## 更新日志

### v2.1.0 (2026-02)

**🎬 抖音视频深度分析**

- ✨ 新增 `video_analysis_service.py` - 视频深度分析服务
- ✨ 抖音视频支持完整转录（Whisper语音识别）
- ✨ LLM智能摘要和关键点提取
- ✨ 关键画面自动提取（5帧均匀分布）
- ✨ 基本提取模式：即时完成，无需额外依赖
- ✨ 深度分析模式：完整转录，需要安装 yt-dlp + whisper + ffmpeg
- ✨ 新增 `deep_analysis` 参数支持

**🐛 修复**

- 修复抖音短链接展开问题
- 修复 Firecrawl API 对某些URL的兼容性问题
- 修复内容详情页图片显示问题

### v2.0.0 (2026-02)

- ✨ 重构为 Flask Blueprint 架构
- ✨ PostgreSQL 数据库支持
- ✨ 新增创作工作台
- ✨ 新增 PARA 组织系统
- ✨ 新增渐进式总结
- ✨ 新增双向链接
- ✨ 新增知识图谱可视化
- ✨ 新增技能树
- ✨ 首页支持封面图片展示

---

## 许可证

MIT License

---

## 贡献者

感谢所有为这个项目做出贡献的人！


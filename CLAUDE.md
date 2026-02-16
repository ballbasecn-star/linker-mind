# Linker Mind - 学习与创作版 PRD

**产品定位**: 知识沉淀 → 灵感激发 → 创作输出

> "我在网上看到优质内容（文章/视频/推文），快速收藏进来。系统帮我自动整理、提取要点、归档到项目。创作时，能快速找到灵感和参考素材。"

---

## 📐 架构决策与规范

### 数据库使用规范

**🔴 强制规则：数据库统一使用PostgreSQL**

```
项目数据库规范：PostgreSQL Only
├─ 禁止：任何新代码使用SQLite
├─ 禁止：直接导入sqlite3模块
├─ 禁止：创建本地.db文件作为数据库
└─ 要求：所有数据库操作必须通过 database/db_interface.py
```

**实施要求**：
1. **数据库连接** - 必须使用 `from database.db_interface import get_connection`
2. **SQL语法** - 所有SQL必须使用PostgreSQL语法
   - 主键：`SERIAL` 而非 `INTEGER PRIMARY KEY AUTOINCREMENT`
   - 自增：`DEFAULT nextval('table_name_id_seq')`
   - 时间类型：`TIMESTAMP` 而非 `TEXT`
   - 布尔值：`BOOLEAN` 而非 `INTEGER`

3. **禁止操作**：
   - ❌ `import sqlite3` - 禁止直接导入SQLite
   - ❌ `sqlite3.connect()` - 禁止直接创建SQLite连接
   - ❌ `sqlite_db_path` - 禁止硬编码SQLite路径

4. **监控模块** - metrics系统也必须使用PostgreSQL
   - 通过 `get_connection()` 获取连接
   - 使用统一接口方法：`insert()`, `fetchone()`, `fetchall()`

**检查清单**：
```python
# ✅ 正确示例
from database.db_interface import get_connection, DatabaseConnectionInterface

def my_function():
    db = get_connection()  # 统一接口
    result = db.fetchone("SELECT * FROM contents WHERE id = %s", (content_id,))
    return result

# ❌ 禁止示例
import sqlite3  # ❌ 禁止直接使用SQLite
conn = sqlite3.connect('local.db')  # ❌ 禁止硬编码SQLite路径
```

**违规处理**：
- 代码审查时必须检查数据库导入
- 新代码必须通过配置验证
- 违反代码将被拒绝合并

---

### 内容提取API规范

**🔴 强制规则：使用统一API客户端**

```
项目内容提取API规范：统一接口
├─ 禁止：直接导入firecrawl模块（除非作为降级方案）
├─ 禁止：硬编码特定API的调用
├─ 要求：所有内容提取必须通过 services.unified_api_client
└─ 要求：优先使用Tavily，其次Firecrawl，最后降级方案
```

**实施要求**：
1. **统一入口** - 使用 `from services.unified_api_client import get_unified_client`
2. **API优先级** - Tavily > Firecrawl > Playwright > BeautifulSoup
3. **降级机制** - 主API失败时自动切换到备用API
4. **配置方式** - 通过环境变量控制使用哪个API

**正确示例**：
```python
# ✅ 正确：使用统一客户端
from services.unified_api_client import get_unified_client

client = get_unified_client()
result = client.scrape_with_priority(url, [TAVILY, FIRECRAWL])

# ✅ 正确：处理器中调用
from content_processor import WebPageProcessor
processor = WebPageProcessor()  # 自动选择最优API
```

**禁止示例**：
```python
# ❌ 禁止：直接使用特定API
from firecrawl import Firecrawl
firecrawl = Firecrawl(api_key=key)
```

**环境变量**：
```bash
TAVILY_API_KEY=tvly-xxx    # 优先使用
FIRECRAWL_API_KEY=fc-xxx   # 备用
```

---

### 抖音远程Cookie服务规范

**🔴 强制规则：抖音内容提取必须使用远程服务**

```
抖音反爬机制严格，本地环境无法直接访问。必须使用远程服务器获取cookies。
├─ 远程服务：部署在可访问抖音的服务器上
├─ 本地调用：通过 douyin_remote_client 调用远程API
└─ 用途：获取登录cookies用于视频提取和下载
```

**架构设计**：

```
┌─────────────────┐         ┌─────────────────────────────────────────────┐
│   本地 Linker   │         │           远程服务器                      │
│   (本地 Mac)    │         │      (117.72.207.52:8080)                  │
├─────────────────┤         ├─────────────────────────────────────────────┤
│                 │   API   │                                             │
│ content_service │────────▶│  Douyin_TikTok_Download_API               │
│                 │  HTTP   │  (开源抖音API解决方案)                      │
│ douyin_processor│◀────────│  - 登录Cookies认证                        │
│                 │  JSON   │  - X-Bogus/A-Bogus签名生成                 │
│                 │         │  - 视频数据API: /api/hybrid/video_data    │
└─────────────────┘         │  - 视频下载API: /api/download              │
                            └─────────────────────────────────────────────┘
```

**工作流程**：

```
用户添加抖音链接
       ↓
content_service.create_from_url()
       ↓
检测为抖音视频 → 调用 douyin_remote_client
       ↓
远程服务使用登录Cookies调用API
       ↓
返回视频数据:
  - video_id, title, description
  - author info, statistics
  - download_url (无水印)
       ↓
douyin_processor.extract()
  - 完善元数据
  - 下载视频/深度分析
       ↓
返回提取的内容
```

**关键文件**：

| 文件 | 说明 |
|------|------|
| `services/douyin_remote_client.py` | 本地客户端，调用远程API |
| `scripts/douyin_signature.py` | 签名生成模块（同步到服务器） |
| `/root/Douyin_TikTok_Download_API/` | 服务器上的开源API解决方案 |

**远程服务API**：

```bash
# 视频数据API（需要登录Cookies）
GET http://117.72.207.52:8080/api/hybrid/video_data?url=https://v.douyin.com/xxx&minimal=false

# 视频下载API（无水印）
GET http://117.72.207.52:8080/api/download?url=https://v.douyin.com/xxx&with_watermark=false

# 响应示例（视频数据）
{
  "code": 200,
  "data": {
    "id": "7601828854176517410",
    "title": "视频标题",
    "desc": "视频描述",
    "author": {"nickname": "作者名称"},
    "statistics": {
      "play_count": 100000,
      "like_count": 5000,
      "comment_count": 100,
      "share_count": 50
    },
    "cover": {"url_list": ["https://..."]}
  }
}

# 响应示例（视频下载）
{
  "code": 200,
  "data": {
    "video_url": "https://aweme..."
  }
}
```

**Cookies配置**：

1. 从浏览器导出抖音登录Cookies（Netscape格式）
2. 配置到服务器配置文件：
   ```
   /root/Douyin_TikTok_Download_API/crawlers/douyin/web/config.yaml
   ```
3. Cookies会定期刷新，需配置自动更新机制

**自动刷新Cookies**：

```bash
# 脚本位置
scripts/auto_refresh_cookies.py

# 配置定时任务（每6小时执行一次）
0 */6 * * * cd /path/to/linker-mind && python3 scripts/auto_refresh_cookies.py >> /var/log/douyin_cookie_refresh.log 2>&1
```

**环境变量**：

```bash
# 远程服务地址
DOUYIN_API=http://117.72.207.52:8080
```

**部署远程服务**：

```bash
# 在服务器上克隆并运行
git clone https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git /root/Douyin_TikTok_Download_API
cd /root/Douyin_TikTok_Download_API
pip install -r requirements.txt

# 配置登录Cookies
vim crawlers/douyin/web/config.yaml

# 启动服务
cd /root/Douyin_TikTok_Download_API
nohup python3 start.py > douyin_api.log 2>&1 &

# 检查服务状态
curl "http://117.72.207.52:8080/api/hybrid/video_data?url=https://v.douyin.com/jkwHntr5qxw/&minimal=false"
```

**注意事项**：

1. **Cookies时效性**：抖音登录Cookies约7天有效，需定期刷新
2. **签名算法**：API请求需要X-Bogus和A-Bogus签名，由服务器自动生成
3. **登录状态**：必须使用已登录账号的Cookies，访客Cookies无法获取完整数据
4. **请求限制**：避免短时间内大量请求，可能触发限流

---

## 实施状态

### ✅ 已完成

1. **Douyin_TikTok_Download_API 部署**
   - 部署位置：服务器 117.72.207.52:8080
   - 开源抖音API解决方案，支持登录Cookies认证
   - 自动生成X-Bogus/A-Bogus签名
   - 源码位置：`/root/Douyin_TikTok_Download_API/`

2. **登录Cookies配置**
   - 从浏览器导出抖音登录Cookies
   - 配置到服务器 `config.yaml` 文件
   - 支持完整的视频数据访问

3. **视频数据API**
   - 端点：`GET /api/hybrid/video_data?url=...&minimal=false`
   - 返回：标题、描述、作者、统计数据、封面等
   - 本地客户端：`services/douyin_remote_client.py`

4. **视频下载**
   - 服务器端：`GET /api/download?url=...&with_watermark=false`
   - 本地端：`DouyinRemoteClient.download_video()` 直接下载到本地

5. **Cookies自动刷新**
   - 脚本：`scripts/auto_refresh_cookies.py`
   - 定时任务：每6小时检查并刷新
   - 使用Playwright从浏览器获取新Cookies

6. **Cookies缓存优化**
   - 本地缓存cookies，默认6小时有效
   - 减少远程服务调用次数

7. **本地深度分析流程** ✅ 新增
   - 视频下载 → Whisper转录 → LLM分析 → 关键帧提取
   - 组件：`services/video_analysis_service.py`
   - Whisper模型：large（最高准确性）
   - LLM：DeepSeek API

### ⚠️ 已知限制

1. **Cookies有效期**
   - 抖音登录Cookies约7天有效
   - 需要定期导出新Cookies并更新到服务器

2. **请求频率**
   - 避免短时间内大量请求
   - 建议添加请求间隔（>3秒）

3. **当前功能状态**
   - ✅ 获取登录Cookies
   - ✅ 提取视频基本信息（标题、描述、作者）
   - ✅ 视频统计数据（播放、点赞、评论、分享）
   - ✅ 视频封面获取
   - ✅ 无水印视频下载到本地
   - ✅ Whisper语音转录（中文）
   - ✅ LLM内容分析（摘要、关键点、话题）
   - ✅ 关键帧提取

---

### 本地深度分析使用说明

```python
from services.video_analysis_service import VideoAnalysisService

service = VideoAnalysisService()

# 完整分析流程
result = service.analyze(
    url='https://v.douyin.com/xxx/',
    enable_transcription=True,   # Whisper转录
    enable_keyframes=True,       # 关键帧提取
    num_keyframes=5,            # 提取5个关键帧
    video_metadata={
        'title': '视频标题',
        'author': '作者'
    }
)

# 结果
result.success        # 是否成功
result.transcript     # 转录文本
result.summary        # LLM摘要
result.key_points     # 关键点
result.key_frames    # 关键帧列表
result.duration       # 视频时长
```

### 本地依赖

```bash
# Mac安装
brew install ffmpeg
pip install openai-whisper yt-dlp pillow
```

### 架构说明

```
┌─────────────┐         ┌──────────────────────────────┐
│   本地       │         │       服务器                  │
│ linker-mind  │         │  117.72.207.52:8080         │
├─────────────┤         ├──────────────────────────────┤
│ 获取Cookies │  ──▶    │  仅提供API代理               │
│ 视频信息    │  ◀──    │  (Cookies认证)              │
│ 视频下载    │  ◀──    │                              │
│ 深度分析    │  ✅     │                              │
│  - Whisper  │         │                              │
│  - LLM      │         │                              │
│  - 关键帧   │         │                              │
└─────────────┘         └──────────────────────────────┘
```

---

## 一、核心场景

### 场景 1：学习知识库 📚

**用户流程**:
```
看到优质教程/文章
       ↓
    收藏到系统
       ↓
    AI 自动提取要点
       ↓
    添加学习笔记
       ↓
    关联到技能树
       ↓
    定期复习提醒
```

**核心需求**:
- 按技能/领域组织内容
- 学习进度追踪
- 知识点关联
- 间隔复习

### 场景 2：创作素材库 💡

**用户流程**:
```
刷到有启发的推文/文章
       ↓
    快速收藏 + 打标签
       ↓
    归类到创作项目
       ↓
    添加灵感笔记
       ↓
    创作时搜索素材
       ↓
    引用追踪（避免抄袭）
```

**核心需求**:
- 快速收藏（一键操作）
- 灵感标签分类
- 项目素材管理
- 创作时快速检索
- 引用来源记录

---

## 二、核心功能模块

### 2.1 内容采集（已有）

**保持现状**: 支持多平台URL采集

### 2.2 智能分析与标签（增强）

**学习导向分析**:
```json
{
  "ai_analysis": {
    // 现有字段
    "key_points": ["核心要点1", "核心要点2"],
    "summary": "内容摘要",
    "topics": ["标签1", "标签2"],

    // 学习导向字段（新增）
    "learning_outcome": "学到了什么",
    "skill_level": "入门/中级/高级",
    "prerequisites": ["前置技能1", "前置技能2"],
    "key_concepts": ["核心概念1", "核心概念2"],
    "actionable_takeaways": ["可执行收获1"],
    "suitable_for": ["学习", "参考", "教程", "灵感"],
    "quality_score": 8.5
  }
}
```

### 2.3 项目/知识库管理

**项目分组**:
```
📁 项目管理
├── 🎨 设计作品集
│   ├── 🎭 角色01 - 灵感收集
│   ├── 🎨 分镜设计参考
│   └── 📸 色彩搭配
├── 💻 技术学习
│   ├── 🐍 Python 学习
│   ├── 🤖 AI/ML 深度学习
│   └── 🌐 Web 开发
├── ✍️ 内容创作
│   ├── 📝 微信文章素材
│   ├── 🎬 视频脚本灵感
│   └── 💡 金句库
└── 📚 研究资料
    ├── 📊 行业报告
    ├── 🔬 学术论文
    └── 📰 趋势分析
```

### 2.4 笔记与灵感系统

**笔记类型**:
| 类型 | 图标 | 说明 | 示例 |
|------|------|------|------|
| 📝 学习笔记 | 学习过程中的记录 | "这个概念讲得很清楚" |
| 💡 创作灵感 | 创作时的想法 | "可以用这个角度写文章" |
| ⭐ 金句摘录 | 值得引用的句子 | 直接引用原文 |
| 🎯 可执行 | 具体的行动建议 | "可以尝试这个方案" |
| ❓ 疑问记录 | 待解决的问题 | "需要进一步研究" |
| 🔗 关联思考 | 联想到的其他内容 | "和之前看的那篇相关" |
| 📌 待深入 | 值得深入研究 | "这个话题值得深挖" |

**笔记数据结构**:
```json
{
  "note_id": "note_001",
  "content_id": "content_123",
  "note_type": "inspiration",
  "content": "这个观点很有启发性",
  "highlights": ["直接引用的原文"],
  "timestamp": "2026-02-08T15:30:00",
  "project_tags": ["设计作品集", "角色01"],
  "mood_tags": ["兴奋", "有启发"],
  "actionable": true
}
```

### 2.5 技能树/知识图谱

**技能维度示例**:
```
📊 Python 技能树
├── 📚 基础语法 (入门)
│   ├── 变量和数据类型 ⭐⭐⭐⭐⭐
│   ├── 控制流 ⭐⭐⭐⭐
│   └── 函数定义 ⭐⭐⭐⭐
├── 🌐 Web 开发 (中级)
│   ├── Flask 框架 ⭐⭐⭐
│   ├── Django 框架 ⭐⭐⭐
│   └── API 设计 ⭐⭐⭐⭐
└── 🤖 AI/ML (高级)
    ├── TensorFlow ⭐⭐⭐
    ├── PyTorch ⭐⭐⭐
    └── 模型部署 ⭐⭐⭐
```

**知识图谱关联**:
- 同一技能的不同资源关联
- 前置技能依赖关系
- 并行技能推荐
- 学习路径推荐

### 2.6 创作工作台

**创作项目管理**:
```json
{
  "project_id": "proj_001",
  "project_name": "角色01 - 灵感收集",
  "project_type": "character_design",
  "status": "collecting",
  "created_at": "2026-02-01T00:00:00",
  "target_date": "2026-03-01T00:00:00",
  "tags": ["设计", "角色设计"],
  "related_content": ["content_001", "content_002"],
  "notes": ["设计灵感笔记"]
}
```

**创作辅助功能**:
- 📋 素材清单板（收集到的素材）
- 🔀 随机灵感推荐
- 📊 创作进度追踪
- 📝 创作日志
- 🤖 AI 辅助创作（基于已有素材生成大纲）

### 2.7 搜索与检索（增强）

**创作场景搜索**:
```
🔍 灵感搜索
  "给我找一些角色设计的灵感"
  → 推荐相关图片、文章、视频

🔗 素材检索
  "我之前收藏过色彩搭配的内容"
  → 按项目/标签快速定位

📚 学习搜索
  "Python Flask 入门教程"
  → 按难度、学习顺序推荐
```

**高级筛选器**:
```
场景：为"设计角色"找灵感
筛选条件：
  ├─ 分类：设计参考
  ├─ 标签：#角色 #设计 #灵感
  ├─ 质量评分：> 7分
  ├─ 时间范围：最近3个月
  └─ 状态：已收藏
```

### 2.8 引用管理

**引用追踪**:
```json
{
  "content_id": "content_123",
  "citations": {
    "outgoing": [
      {
        "target_id": "content_456",
        "context": "参考了XX的观点",
        "usage": "inspiration"
      }
    ],
    "incoming": [
      {
        "source_id": "content_789",
        "context": "在我的文章中引用"
      }
    ]
  }
}
```

**一键引用格式化**:
```
学术格式：
[1] 作者名, 文章标题, 网站链接, 访问时间

博客格式：
来源：文章标题
链接：xxx
备注：我的想法

社交媒体：
"..."（引用原文）
via @作者名
```

---

## 三、UI/UX 设计要点

### 3.1 首页设计

```
┌─────────────────────────────────────────┐
│  🔍 [智能搜索]  |  📁 项目  |  + 新建项目   │
├─────────────────────────────────────────┤
│  快速访问                                  │
│  [待处理 15] [收藏夹 28] [最近阅读]        │
├─────────────────────────────────────────┤
│  知识雷达                                  │
│  [推荐学习] [相关内容] [灵感推荐]         │
├─────────────────────────────────────────┤
│  内容流（默认按时间）                      │
│  智能排序：[时间] [相关度] [质量] [学习进度] │
│  ┌─────────────────────────────────┐   │
│  │ [卡片] 内容卡片                   │   │
│  │ 📝 笔记: 2条  ⭐ 收藏  👁️ 已读    │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │ [卡片] 内容卡片                   │   │
│  │ 🏷️ #AI #教程  📖 阅读中            │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### 3.2 项目详情页

```
┌─────────────┬─────────────────────────────────┐
│  ← 返回     │  项目：角色01 - 灵感收集       │
│             │  状态：🔥 收集中  📅 截止：3/15   │
├─────────────┼─────────────────────────────────┤
│  📂 素材库  │  选项卡页                      │
│  ├─ 📸 图片  │  ├─ 📄 文章  ├─ 🎬 视频  ─┤  │
│  ├─ 💡 灵感  │  ├─ 📝 笔记  ─────────────┘  │
│  └─ ⭐ 收藏  │                                 │
├─────────────┼─────────────────────────────────┤
│  📊 统计    │  素材分布饼图                   │
│  │ 52 图片  │  [图片] [图片] [图片]          │
│  │  18 文章  │                                 │
│  └─ 8 视频   │                                 │
├─────────────┼─────────────────────────────────┤
│  💭 创作日志 │  ┌─────────────────────────────┐ │
│             │  │ 2024-02-08  添加了3张参考图 │ │
│  [添加日志]   │  └─────────────────────────────┘ │
│             │  [时间线展开]                   │
├─────────────┼─────────────────────────────────┤
│  🤖 AI 建议  │  "基于你的素材，建议..."      │
│             │  "可能缺少：背景参考..."       │
│  └─────────┴─────────────────────────────────┘
```

### 3.3 侧边栏（详情页）

```
┌─────────────┐
│  快速操作    │
│  ⭐ 收藏     │
│  📝 添加笔记  │
│  📁 加入项目  │
│  🔗 复制链接  │
├─────────────┤
│  学习进度    │
│  ████████░░ 60% │
│             │
│  相关技能    │
│  • UI设计    │
│  • 色彩理论  │
│  └─ 更多...  │
│             │
│  内容关联    │
│  • 引用了此  │
│  • 被引用   │
│  • 相似内容  │
└─────────────�
```

---

## 四、工作流程设计

### 4.1 学习流程

```
┌─────────────────────────────────────────┐
│  1. 发现优质内容                          │
│     → 浏览器插件/复制链接                  │
├─────────────────────────────────────────┤
│  2. 一键收藏                              │
│     → 自动提取内容、AI分析                 │
│     → 打标签、归档到技能树                 │
├─────────────────────────────────────────┤
│  3. 学习记录                              │
│     → 添加学习笔记                        │
│     → 标记进度（已读/学习中/待学）        │
├─────────────────────────────────────────┤
│  4. 知识关联                              │
│     → 关联到已有知识点                   │
│     → 建立技能依赖关系                   │
├─────────────────────────────────────────┤
│  5. 复习提醒                              │
│  → 基于艾宾浩斯曲线的复习提醒            │
│  → 定期回顾总结                        │
└─────────────────────────────────────────┘
```

### 4.2 创作流程

```
┌─────────────────────────────────────────┐
│  1. 创建项目                              │
│     → 设定项目名称、类型、目标              │
│     → 设置截止日期                        │
├─────────────────────────────────────────┤
│  2. 收集灵感                              │
│  → 快速收藏相关内容                      │
│  → 打灵感标签                            │
│  → 添加第一想法笔记                      │
├─────────────────────────────────────────┤
│  3. 整理素材                              │
│  │  ├─ 📸 图片素材                        │
│  │  ├─ 💡 灵感笔记                        │
│  │  ├─ 📝 参考文章                        │
│  │  └─ 🎬 参考视频                        │
├─────────────────────────────────────────┤
│  4. 规划结构                              │
│  → AI 基于素材建议大纲                    │
│  │  → 引用追踪（避免抄袭）                │
│  └─  → 优先级排序                          │
├─────────────────────────────────────────┤
│  5. 创作输出                              │
│  → 导出素材包（图片+笔记+引用）            │
│  → 使用引用格式化工具                   │
│  → 标记素材使用情况                      │
└─────────────────────────────────────────┘
```

---

## 五、数据模型（学习+创作版）

### 5.1 项目数据结构

```json
{
  "project_id": "proj_001",
  "project_name": "角色01 - 灵感收集",
  "project_type": "character_design",
  "description": "设计一个有趣角色的灵感收集",
  "status": "collecting",
  "created_at": "2026-02-01T00:00:00",
  "target_date": "2026-03-01T00:00:00",
  "completed_at": null,

  "metadata": {
    "tags": ["设计", "角色", "灵感"],
    "skills_involved": ["UI设计", "角色设计"],
    "difficulty": "intermediate",
    "estimated_time": "20小时"
  },

  "content": {
    "total_items": 78,
    "by_type": {
      "images": 52,
      "articles": 18,
      "videos": 8
    }
  },

  "citations": {
    "used_sources": [],
    "reference_list": []
  },

  "creation_output": {
    "final_url": null,
    "published_at": null,
    "engagement_stats": {}
  }
}
```

### 5.2 技能数据结构

```json
{
  "skill_id": "skill_python_flask",
  "skill_name": "Python Flask 框架",
  "category": "Web开发",
  "level": "intermediate",
  "parent_skills": ["python_basics", "web_fundamentals"],
  "child_skills": ["flask_api", "flask_database"],

  "learning_path": [
    {
      "order": 1,
      "content_id": "xxx",
      "title": "Flask 入门教程",
      "type": "tutorial",
      "estimated_time": "2小时",
      "completed": true
    }
  ],

  "projects": ["proj_001", "proj_002"],
  "notes_count": 12,
  "last_studied": "2026-02-05"
}
```

---

## 六、优先级排序

### P0 - 立即实施（核心学习+创作流程）

1. **项目管理系统**
   - 创建/编辑项目
   - 添加内容到项目
   - 项目列表视图
   - 项目详情页

2. **增强笔记系统**
   - 多种笔记类型
   - 快速添加笔记（弹窗/侧边栏）
   - 笔记搜索
   - 笔记高亮/引用

3. **标签增强**
   - 灵感标签库（预设+自定义）
   - 学习阶段标签
   - 项目关联标签
   - 标签快速选择

### P1 - 近期实施（提升体验）

4. **引用管理**
   - 自动追踪引用关系
   - 一键生成引用格式
   - 引用记录展示

5. **学习进度**
   - 内容状态管理（待学/学习中/已掌握）
   - 学习进度可视化
   - 学习记录时间线

6. **创作辅助**
   - 素材看板视图
   - AI素材建议
   - 素材导出

### P2 - 长期规划（智能化）

7. **技能树系统**
   - 技能依赖关系可视化
   - 学习路径推荐
   - 技能熟练度追踪

8. **知识图谱**
   - 内容关联可视化
   - 关系探索视图
   - 图谱搜索

9. **复习提醒**
   - 基于遗忘曲线的复习提醒
   - 定期回顾总结
   - 复习效果追踪

---

## 七、特色功能亮点

### 7.1 创作视角

**素材去重**:
- 自动检测相似内容
- 标注重复内容避免重复引用

**灵感组合**:
- AI 推荐内容组合
- 跨领域创意融合

**版权追踪**:
- 记录素材来源
- 引用完整性检查

### 7.2 学习视角

**学习路径**:
- 基于内容推荐学习顺序
- 自动生成课程表

**知识复用**:
- 检测不同内容的共同点
- 抽取通用知识模型

**成果可视化**:
- 学习热力图
- 技能掌握雷达图

---

## 八、下一步行动

**建议按以下顺序实施**:

**第一批（核心流程）**:
1. 项目管理系统（创建项目、归类内容）
2. 增强笔记系统（快速添加、多种类型）
3. 标签系统（灵感标签库、项目标签）

**第二批（创作辅助）**:
4. 引用管理系统
5. 素材看板视图
6. 项目统计看板

**第三批（智能化）**:
7. 内容关联推荐
8. AI 创作辅助
9. 学习路径规划

---

*文档版本: v1.3*
*最后更新: 2026-02-16*
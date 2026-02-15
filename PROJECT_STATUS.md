# Linker Mind - 项目状态文档

**更新日期**: 2026-02-09
**项目版本**: v2.0.0
**状态**: 重构中 (从单体架构向服务层架构迁移)

---

## 📋 项目概述

**Linker Mind** 是一个"第二大脑 + 创作工作台"系统，支持从任意来源采集内容，系统化整理，持续提炼，并支持创造性输出。

### 核心定位
> **Linker Mind** = 你的第二大脑 + 创作工作台

从**任意来源**捕捉内容 → 系统化整理 → 持续提炼 → 创造性输出

---

## 🏗️ 当前架构

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| **后端框架** | Flask 3.x | Python Web框架 |
| **数据库** | PostgreSQL 117.72.207.52:5432 | 生产数据库 (13张表, 73条记录) |
| **AI服务** | DeepSeek API | 内容分析 |
| **内容抓取** | Firecrawl + MCP WebReader | 多平台内容提取 |
| **前端** | D3.js + Vanilla JS | 知识图谱可视化 |

### 项目结构

```
linker-mind/
├── app/                          # Flask应用
│   ├── __init__.py              # 应用工厂
│   ├── blueprints/              # 路由模块 (11个)
│   ├── templates/               # Jinja2模板
│   ├── static/                  # 前端资源
│   └── utils/                   # 工具函数
├── services/                    # 业务逻辑层 (9个服务)
├── database/                    # 数据访问层
│   ├── db_interface.py         # 统一数据库接口
│   ├── connection.py           # SQLite连接
│   ├── pg_connection.py        # PostgreSQL连接
│   └── migration.py            # 数据迁移脚本
├── repositories/               # 数据仓储层 (新增)
├── [处理器文件]                 # 内容处理器 (10+个)
├── run.py                      # 应用入口
└── [配置文件]
```

---

## ✅ 已完成的重构工作

### Phase 1: 基础重构 (已完成)

#### 1.1 数据库层迁移
- ✅ 设计并实现PostgreSQL Schema (13张表)
- ✅ 编写数据迁移脚本 (JSON → PostgreSQL)
- ✅ 实现Repository模式
- ✅ 实现统一数据库接口 (`db_interface.py`)
- ✅ 支持SQLite回退

**迁移统计**: 73条记录 (64 contents, 1 node, 1 note, 7 skills)

#### 1.2 Blueprint架构重构
**已完成重构的Blueprint** (11个):

| Blueprint | 功能 | 服务层 | 状态 |
|-----------|------|--------|------|
| `content_bp.py` | 内容CRUD | ContentService | ✅ 已重构 |
| `node_bp.py` | PARA组织 | NodeService | ✅ 已重构 |
| `note_bp.py` | 笔记管理 | NoteService | ✅ 已重构 |
| `link_bp.py` | 双向链接 | LinkService | ✅ 已重构 |
| `inbox_bp.py` | 收件箱 | InboxService | ✅ 已重构 |
| `session_bp.py` | 学习会话 | LearningSessionService | ✅ 已重构 |
| `skill_bp.py` | 技能管理 | SkillService | ✅ 已重构 |
| `graph_bp.py` | 知识图谱 | KnowledgeGraphService | ✅ 已重构 |
| `search_bp.py` | 搜索 | EnhancedSearchService | ✅ 已重构 |
| `creation_bp.py` | 创作项目 | CreationWorkshopService | ✅ 已重构 |
| `api_bp.py` | 复合操作 | 多服务 | ✅ 已重构 |

**代码行数减少**:
- `session_bp.py`: 541 → 406行 (-25%)
- `graph_bp.py`: 435 → 265行 (-39%)
- `creation_bp.py`: 684 → 578行 (-15%)

### Phase 2: 前端重构 (已完成)

#### 2.1 统一API客户端
- ✅ 创建 `static/js/api.js` (16,330字节)
- ✅ 提供100+个API方法
- ✅ 统一错误处理
- ✅ 自动JSON序列化

#### 2.2 模板更新
已更新4个核心模板使用新API:
- ✅ `templates/index.html` - 首页/仪表盘
- ✅ `templates/dashboard_v2.html` - v2仪表盘
- ✅ `templates/detail.html` - 内容详情页
- ✅ `templates/graph.html` - 知识图谱页

### Phase 3: Bug修复 (已完成)

#### 3.1 序列化问题修复
```python
# 问题: ProcessedContent对象无法JSON序列化
# 修复: services/content_service.py:156
processed.ai_analysis = ai_result.ai_analysis  # 而非 ai_result
```

#### 3.2 数据库Schema问题
- ✅ 添加 `tags` 列到PostgreSQL `contents`表
- ✅ 添加 `tags` 列到SQLite `contents`表

#### 3.3 JSONB处理修复
```python
# 问题: psycopg2无法直接适配Python dict到JSONB
# 修复: 统一使用json_dumps()转换为JSON字符串
'ai_analysis': json_dumps(ai_analysis or {}),
'metadata': json_dumps(metadata or {}),
'tags': json_dumps(tags or []),
```

#### 3.4 模板变量修复
```python
# 问题: 模板期望`item`但路由传递`content`
# 修复: content_bp.py:107
return render_template('detail.html', item=content, ...)
```

#### 3.5 JSON响应格式修复
```python
# 问题: json_error_response()已返回(status_code, response)
# 但代码又添加了额外的status_code
# 修复: 所有blueprint中使用status_code参数
return json_error_response('msg', status_code=400)
```

#### 3.6 Markdown和图片支持
- ✅ 配置marked.js支持GFM
- ✅ 添加智能Markdown检测
- ✅ 自动转换图片URL为`<img>`标签
- ✅ 优化内容显示样式

---

## 🔄 服务层架构 (v2.0)

### 已实现的服务 (9个)

| 服务 | 文件 | 核心功能 |
|------|------|----------|
| **InboxService** | `inbox_service.py` | 快速收集工作流 |
| **NodeService** | `node_service.py` | PARA组织方法 |
| **ContentService** | `content_service.py` | 内容CRUD |
| **NoteService** | `note_service.py` | 笔记管理 |
| **LinkService** | `link_service.py` | 双向链接 |
| **CreationWorkshopService** | `creation_service.py` | 创作项目 |
| **CreationAssistant** | `creation_assistant.py` | AI创作助手 |
| **EnhancedSearchService** | `search_service.py` | 增强搜索 |
| **LearningSessionService** | `session_service.py` | 学习追踪 |
| **KnowledgeGraphService** | `graph_service.py` | 知识图谱 |
| **SkillTreeManager** | `skill_tree_manager.py` | 技能树 |

### API端点统计
- **总路由数**: 117个
- **Blueprint数量**: 11个
- **页面路由**: 10个
- **API路由**: 107个

---

## 🗄️ 数据库Schema

### PostgreSQL表结构 (13张表)

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `contents` | 内容存储 | id, title, raw_content, ai_analysis(JSONB), tags |
| `nodes` | PARA组织 | id, node_type, name, parent_id |
| `node_contents` | 内容-节点关联 | node_id, content_id |
| `notes` | 笔记 | id, content_id, note_type, summary_layer |
| `links` | 双向链接 | id, source_id, target_id, link_type |
| `learning_sessions` | 学习会话 | id, content_id, duration, comprehension |
| `review_schedules` | 复习计划 | content_id, next_review, interval |
| `creation_projects` | 创作项目 | id, project_type, outline, status |
| `citations` | 引用记录 | id, project_id, source_content_id |
| `skills` | 技能 | id, skill_name, level, parent_ids(JSONB) |
| `skill_contents` | 技能-内容关联 | skill_id, content_id, order_index |
| `inbox` | 收件箱 | id, content_id, status |
| `tags` | 标签库 | id, name, color, use_count |

### JSONB字段
- `contents.ai_analysis` - AI分析结果
- `contents.metadata` - 内容元数据
- `contents.tags` - 标签列表
- `skills.parent_ids` - 父技能ID列表

---

## 🎨 支持的内容类型

### 内容处理器 (10+个)

| 处理器 | 平台/类型 | 状态 |
|--------|----------|------|
| **WebPageProcessor** | 通用网页 | ✅ 稳定 |
| **TwitterProcessor** | Twitter/X (Tavily API) | ✅ 已修复 |
| **WeixinProcessor** | 微信公众号 | ✅ 稳定 |
| **DouyinProcessor** | 抖音 | ✅ 稳定 |
| **VideoInfoProcessor** | YouTube/B站 (yt-dlp) | ✅ 稳定 |
| **BookProcessor** | EPUB/PDF电子书 | ✅ 稳定 |
| **AudioProcessor** | MP3/M4A/播客 | ✅ 稳定 |
| **OCRProcessor** | 图片文字提取 | ✅ 稳定 |
| **SocialMediaProcessor** | 通用社交媒体 | ✅ 稳定 |
| **VideoProcessor** | 视频分析 | ✅ 稳定 |
| **TextMemoProcessor** | 文本笔记 | ✅ 稳定 |

---

## 🚀 启动方式

### 开发服务器
```bash
python run.py
# 访问 http://127.0.0.1:5000
```

### 生产服务器
```bash
python run.py --prod --host 0.0.0.0 --port 5000
```

### 数据库初始化
```bash
python run.py --init
```

### 数据迁移
```bash
python run.py --migrate
```

---

## 🔧 环境配置

### 必需的API Keys

| 服务 | 环境变量 | 用途 | 获取地址 |
|------|----------|------|----------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | AI内容分析 | [platform.deepseek.com](https://platform.deepseek.com/) |
| **Firecrawl** | `FIRECRAWL_API_KEY` | 网页抓取 | [firecrawl.dev](https://www.firecrawl.dev/) |
| **Tavily** | `TAVILY_API_KEY` | Twitter抓取(可选) | [tavily.com](https://tavily.com/) |

### 数据库配置

```bash
# PostgreSQL (生产)
DB_TYPE=postgresql
PGHOST=117.72.207.52
PGPORT=5432
PGDATABASE=linker-mind
PGUSER=postgres
PGPASSWORD=your_password

# SQLite (开发/回退)
DB_TYPE=sqlite
# 或不设置，自动使用SQLite
```

---

## 📊 当前数据统计

### 数据库记录
- **总记录数**: 73条
- **Contents**: 64条
- **Nodes**: 1个
- **Notes**: 1条
- **Skills**: 7个

### 代码统计
- **Python文件**: 30+个
- **总代码行数**: ~10,000行
- **Blueprints**: 11个
- **Services**: 9个
- **Templates**: 15+个

---

## 🐛 已知问题

### 1. 内容详情页显示问题
**状态**: ⚠️ 部分修复
- ✅ 修复模板变量 (`item` vs `content`)
- ✅ 添加Markdown支持
- ✅ 添加图片显示支持
- ⚠️ 长内容显示需要优化 (已添加max-height和滚动)

### 2. 错误处理
**状态**: ⚠️ 需改进
- ✅ 统一API响应格式
- ⚠️ 缺少 `error.html` 模板
- ⚠️ 需要更友好的错误页面

### 3. 测试覆盖
**状态**: ❌ 待实现
- 需要添加单元测试
- 需要添加集成测试

---

## 📝 下一步计划

### 优先级 P0 (立即)
1. ✅ 修复内容详情页显示
2. ✅ 完善Markdown和图片支持
3. ⚠️ 添加错误页面模板
4. ⚠️ 测试所有API端点

### 优先级 P1 (近期)
1. 实现收件箱功能界面
2. 实现PARA组织界面
3. 完善知识图谱可视化
4. 添加批量操作功能

### 优先级 P2 (长期)
1. 实现技能树可视化
2. 实现学习路径推荐
3. 实现复习提醒系统
4. 添加数据导出功能

---

## 📚 核心功能说明

### PARA组织方法
- **Projects (项目)**: 有明确目标和时间范围
- **Areas (领域)**: 长期关注的领域/职责
- **Resources (资源)**: 未来可能用到的资源
- **Archive (归档)**: 已完成/不再活跃

### 渐进式总结
- **Layer 1**: 高亮 (黄色)
- **Layer 2**: 加粗重点
- **Layer 3**: 超级笔记 (优中之优)
- **Layer 4**: 用自己的话总结
- **Layer 5**: 加入深度思考形成新内容

### CODE工作流
- **Capture**: 快速捕捉到收件箱
- **Organize**: 归类到项目/领域/资源
- **Distill**: 渐进式总结提炼精华
- **Express**: 基于素材进行创作输出

---

## 🔗 相关文档

- [产品PRD](CLAUDE.md) - 完整产品需求文档
- [PostgreSQL设置](POSTGRESQL_SETUP.md) - 数据库配置指南
- [迁移总结](MIGRATION_SUMMARY.md) - 数据迁移说明
- [实施完成报告](IMPLEMENTATION_COMPLETE.md) - 实施进度

---

**文档维护**: 本文档随项目进展持续更新
**最后更新**: 2026-02-09
**维护者**: Claude Code Assistant

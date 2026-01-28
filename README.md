# 林克 Mind (Linker Mind)

一个多模态内容提取和智能存储系统，能够解析各种链接类型（网页、X推文、微信公众号、抖音视频等），并对内容进行AI分析和结构化存储。

## 功能特性

### 支持的内容类型

| 类型 | 示例 | 处理方式 |
|------|------|----------|
| 普通网页 | `https://www.example.com` | Firecrawl 抓取 |
| Twitter/X | `https://twitter.com/user/status/123` | MCP WebReader |
| 微信公众号 | `https://mp.weixin.qq.com/s/...` | MCP WebReader |
| 抖音 | `https://www.douyin.com/video/...` | MCP WebReader |
| YouTube | `https://youtube.com/watch?v=...` | MCP Video Analyzer |
| Bilibili | `https://bilibili.com/video/...` | MCP Video Analyzer |
| 直接视频 | `https://example.com/video.mp4` | MCP Video Analyzer |
| 文本笔记 | 任意纯文本 | 直接存储 + AI分析 |

### AI 分析能力

- 自动摘要生成
- 关键点提取
- 情感分析
- 话题标签生成
- 可执行建议提取

---

## 安装配置

### 1. 环境要求

- Python 3.10+
- pip 包管理器

### 2. 安装依赖

```bash
pip install firecrawl-py openai python-dotenv requests validators
```

### 3. 配置环境变量

创建 `.env` 文件：

```bash
# Firecrawl API (网页抓取)
FIRECRAWL_API_KEY=your_firecrawl_api_key

# DeepSeek API (AI分析)
DEEPSEEK_API_KEY=your_deepseek_api_key
```

### 获取 API Keys

- **Firecrawl**: [https://www.firecrawl.dev/](https://www.firecrawl.dev/)
- **DeepSeek**: [https://platform.deepseek.com/](https://platform.deepseek.com/)

---

## 使用方法

### 交互模式 (推荐)

```bash
python main.py
```

进入交互模式后，可以使用以下命令：

```
<linker> https://example.com          # 处理URL
<linker> 这是我的笔记                  # 保存文本笔记
<linker> /search Python               # 搜索内容
<linker> /stats                       # 查看统计
<linker> /help                        # 显示帮助
<linker> /quit                        # 退出
```

### 命令行模式

```bash
# 处理单个URL
python main.py --url https://www.anthropic.com

# 保存文本笔记
python main.py --text "今天学习了Python装饰器"

# 搜索已存储的内容
python main.py --search "AI安全"

# 查看统计信息
python main.py --stats

# 禁用AI分析（仅提取内容）
python main.py --no-ai --url https://example.com
```

---

## 项目结构

```
linker-mind/
├── main.py                  # 主程序入口
├── url_detector.py          # URL类型识别模块
├── content_processor.py     # 内容处理器（Firecrawl/社交媒体/视频）
├── ai_analyzer.py          # AI分析和存储管理
├── .env                    # 环境变量配置
├── linker_data.json        # 本地存储文件
└── README.md               # 本文档
```

---

## 数据结构

存储在 `linker_data.json` 中的数据结构：

```json
{
  "id": "20260128142431",
  "timestamp": "2026-01-28T14:24:31.584973",
  "raw_input": "https://www.anthropic.com",
  "source_type": "webpage",
  "platform": "web",
  "content": {
    "title": "Anthropic - AI Safety",
    "url": "https://www.anthropic.com",
    "main_content": "# AI research and products...",
    "summary": "Anthropic's homepage highlights...",
    "metadata": {
      "description": "...",
      "author": "",
      "publish_date": "",
      "tags": ["AI safety", "Claude AI"]
    }
  },
  "media": {
    "type": "mixed",
    "images": ["https://..."],
    "videos": [],
    "screenshots": []
  },
  "ai_analysis": {
    "key_points": [
      "Anthropic focuses on AI safety",
      "Claude Opus 4.5 excels in coding"
    ],
    "sentiment": "positive",
    "topics": ["AI safety", "Claude AI", "responsible AI"],
    "actionable_items": [],
    "summary": "AI will have a vast impact on the world..."
  },
  "processing_info": {
    "method": "WebPageProcessor",
    "processing_time": 10.23,
    "success": true,
    "errors": []
  }
}
```

---

## 模块说明

### URLDetector (url_detector.py)

负责识别和分类URL类型：

```python
from url_detector import URLDetector

detector = URLDetector()
url_info = detector.detect("https://twitter.com/user/status/123")
# URLInfo(url_type=URLType.TWITTER, platform='twitter', extracted_id='123')
```

### ContentProcessor (content_processor.py)

内容处理器基类和具体实现：

- **WebPageProcessor**: 使用 Firecrawl 抓取网页
- **SocialMediaProcessor**: 处理社交媒体内容
- **VideoProcessor**: 处理视频内容
- **TextMemoProcessor**: 处理纯文本笔记

### AIAnalyzer (ai_analyzer.py)

AI分析和存储管理：

```python
from ai_analyzer import AIAnalyzer, StorageManager

analyzer = AIAnalyzer()
content = analyzer.analyze(processed_content)

storage = StorageManager()
storage.save(content)
results = storage.search("query")
```

---

## 命令参考

| 命令 | 参数 | 说明 |
|------|------|------|
| `-u, --url` | URL | 处理指定URL |
| `-t, --text` | TEXT | 保存文本笔记 |
| `-s, --search` | QUERY | 搜索已存储内容 |
| `--stats` | - | 显示统计信息 |
| `-i, --interactive` | - | 交互模式 |
| `--no-ai` | - | 禁用AI分析 |
| `-h, --help` | - | 显示帮助信息 |

---

## 示例输出

```
============================================================
🔍 Processing: https://www.anthropic.com...
============================================================

📌 Detected Type: WEBPAGE
📌 Platform: web
⚙️  Using processor: WebPageProcessor

🤖 Running AI analysis...
📁 Content saved to linker_data.json (ID: 20260128142431)

============================================================
✅ Processing Complete!
============================================================
🆔 ID: 20260128142431
📅 Time: 2026-01-28T14:24:31.584973
📌 Type: webpage (web)
📝 Summary: Anthropic's homepage highlights its mission to develop safe AI...

💡 Key Points:
   1. Anthropic focuses on AI safety and public benefit
   2. Claude Opus 4.5 excels in coding and enterprise workflows
   3. Core views include responsible scaling and policy work

🏷️  Topics: AI safety, Claude AI, responsible AI, public benefit corporation
😊 Sentiment: positive 😊

⏱️  Processing time: 10.23s
============================================================
```

---

## 开发计划

### 已完成 ✅

- [x] URL类型识别
- [x] Firecrawl网页抓取
- [x] DeepSeek AI分析
- [x] JSON本地存储
- [x] 搜索功能
- [x] 统计功能
- [x] 交互模式

### 计划中 📋

- [ ] MCP工具完整集成
- [ ] 数据库支持 (SQLite/PostgreSQL)
- [ ] 批量处理和异步队列
- [ ] Web界面 (Flask/FastAPI + React/Vue)
- [ ] 全文搜索和标签系统
- [ ] 知识图谱构建

---

## 常见问题

### Q: 为什么Firecrawl抓取失败？

A: 请检查：
1. `.env` 文件中 `FIRECRAWL_API_KEY` 是否正确
2. API Key 是否有剩余额度
3. 目标网站是否可以访问

### Q: 如何禁用AI分析以节省API费用？

A: 使用 `--no-ai` 参数：
```bash
python main.py --no-ai --url https://example.com
```

### Q: 数据存储在哪里？

A: 默认存储在当前目录的 `linker_data.json` 文件中，可以手动查看或备份。

---

## 许可证

MIT License

---

## 联系方式

如有问题或建议，欢迎提 Issue。

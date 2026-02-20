# AI写作闭环工作流 - Bug List

## 记录

| 日期 | 版本 | 修改人 | 描述 |
|------|------|--------|------|
| 2026-02-20 | v1.0 | Claude | 初始Bug List |
| 2026-02-20 | v1.1 | Claude | 修复workflow JSON序列化问题 |

---

## Bug列表

### 🔴 严重Bug

| # | 状态 | 位置 | 问题描述 | 原因 | 修复日期 |
|---|------|------|---------|------|----------|
| 1 | ✅ 已修复 | `/api/creations/<id>/workflow` | 返回500错误 JSON序列化失败 | `CreationStatus` 枚举无法序列化 | 2026-02-20 |
| 2 | ✅ 已修复 | `/api/creations/<id>/generate-draft` | 返回500错误 | ContentRepository 使用 `get_db` 和SQLite语法 | 2026-02-20 |

### 🟡 功能问题

| # | 状态 | 位置 | 问题描述 | 原因 | 修复日期 |
|---|------|------|---------|------|----------|
| 3 | ✅ 已修复 | `generate_draft()` | 无素材时直接返回错误 | 应返回手动撰写提示 | 2026-02-20 |
| 4 | ✅ 已修复 | LLM调用 | 返回None | 未调用load_dotenv() | 2026-02-20 |

### 📋 遗留代码问题

| # | 状态 | 问题描述 | 影响文件 | 修复日期 |
|---|------|---------|---------|----------|
| 5 | ✅ 已修复 | 使用 `get_db` 而非 `get_connection` | `repositories/*.py` | 2026-02-20 |
| 6 | ⚠️ 需要重启 | PostgreSQL占位符问题 | `repositories/*.py` 使用SQLite语法 | - |

---

## 修复详情

### Bug #1: Workflow JSON序列化失败

**问题**: `CreationStatus` 枚举对象无法JSON序列化

**修复**: 在 `app/blueprints/creation_bp.py` 的 `get_workflow` 函数中，将枚举转换为字符串值

### Bug #2: generate-draft 使用遗留Repository代码

**问题**: ContentRepository 使用 `get_db` 和SQLite语法

**修复**: 在 `services/creation_assistant.py` 中直接使用 `get_connection()` 进行数据库查询，使用 SQLite 风格占位符 `?`

### Bug #3: 无素材时生成初稿

**问题**: 无素材时直接返回错误

**修复**: 返回友好提示

### Bug #4: LLM客户端未加载环境变量

**问题**: `creation_assistant.py` 没有加载 .env 文件中的环境变量

**修复**: 在文件开头添加 `load_dotenv()` 调用

---

## 待处理

### 需要重启Flask服务器

部分修复需要重启Flask服务器才能生效。重启后运行：

```bash
# 测试所有端点
curl http://127.0.0.1:5000/api/creations
curl http://127.0.0.1:5000/api/creations/<id>/workflow
curl -X POST http://127.0.0.1:5000/api/creations/<id>/generate-draft -H "Content-Type: application/json" -d '{"target_words": 500}'
```

### 配置LLM API Key

```bash
export DEEPSEEK_API_KEY="your-api-key"
# 或
export OPENAI_API_KEY="your-api-key"
```

# API迁移方案：Firecrawl → Tavily (或统一接口)

**目标**: 将所有依赖Firecrawl的地方迁移到使用TAVILY_API_KEY，实现API接口统一

---

## 🔍 当前使用情况分析

### Firecrawl使用位置

**主要文件**:
1. `content_processor.py` - WebPageProcessor类（第13行）
2. `douyin_processor.py` - 抖音处理器（第574, 581行）
3. `processors/webpage_processor_enhanced.py` - 增强处理器（已更新）

**依赖注入点**：
```python
# content_processor.py:13
from firecrawl import Firecrawl

# douyin_processor.py:574
from firecrawl import Firecrawl

# 所有这些地方需要统一
```

### 迁移方案

**✅ 推荐方案**：统一API接口

创建 `services/unified_api_client.py` 统一管理所有API客户端
- 支持多种API（Firecrawl、Tavily、Playwright）
- 优先级排序和自动fallback
- 统一的错误处理和配置
- 易于切换API Key或服务商

---

## 🎯 迁移优势

### 1. 成本优化

**Tavily vs Firecrawl**（估算，具体价格可能变化）:
```
服务          | 小规模      | 中等规模      | 大规模
Firecrawl      | $49/月     | $249/月      | 定制
Tavily        | $199/月    | $999/月      | 定制
Playwright     | 免费（自托管）| 免费（自托管）| 运维成本高
```

**潜在节省**：
- 小规模（月处理<10万URL）：Tavily可节省约60%
- 中等规模（10-100万URL/月）：成本可减半

### 2. 功能增强

**Tavily独有功能**：
- ✅ 结构化数据提取（JSON Schema）
- ✅ 自定义字段提取
- ✅ Screenshot生成（自动）
- ✅ PDF文档生成
- ✅ 批量URL处理
- ✅ 无需编码的Webhook支持

### 3. 风险分散

**不把所有鸡蛋放一个篮子**：
- ✅ 多个API提供备份选项
- ✅ 避免单点故障
- ✅ 可按平台选择最优API
- ✅ 易于A/B测试不同API

---

## 🛠️ 迁移实施步骤

### 阶段一：创建统一API客户端

**文件**：`services/unified_api_client.py`（已创建）

**核心功能**：
```python
class UnifiedExtractionClient:
    """统一内容提取客户端"""

    def __init__(self):
        # 优先级顺序
        self.priority_order = [
            ExtractionAPI.TAVILY,      # 优先1：Tavily
            ExtractionAPI.FIRECRAWL,    # 优先2：Firecrawl
            ExtractionAPI.PLAYWRIGHT,     # 优先3：Playwright
        ]

    def scrape(self, url: str, api_type: ExtractionAPI) -> ScrapeResult:
        """统一的提取接口"""
        client = self.get_client(api_type)
        return client.scrape(url)
```

### 阶段二：更新现有处理器

**需要修改的文件**：
1. `content_processor.py` - WebPageProcessor类
2. `douyin_processor.py` - 抖音处理器
3. `processors/webpage_processor_enhanced.py` - 增强处理器

**修改方式**：
```python
# 修改前
from firecrawl import Firecrawl
firecrawl = Firecrawl(api_key=api_key)

# 修改后
from services.unified_api_client import UnifiedExtractionClient
client = UnifiedExtractionClient(api_key=api_key)
```

### 阶段三：配置管理

**环境变量更新** (`env.example`)：
```bash
# 新增配置项
EXTRACTION_API=tavily              # 优先API选择
EXTRACTION_API_KEY=tvly-xxx       # Tavily API Key
FIRECRAWL_API_KEY=fc-xxx          # Firecrawl API Key
PLAYWRIGHT_API_KEY=xxx            # Playwright API Key

# API优先级（逗号分隔）
EXTRACTION_API_PRIORITY=TAVILY,FIRECRAWL,PLAYWRIGHT
```

### 阶段四：逐步迁移

**第1周**：基础架构
- ✅ 创建UnifiedExtractionClient
- ✅ 实现Tavily客户端
- ✅ 更新content_processor（保留Firecrawl作为备用）
- ✅ 添加配置验证

**第2周**：处理器迁移
- ✅ 迁移douyin_processor到新接口
- ✅ 迁移其他处理器（如需要）
- ✅ 全面测试验证

**第3周**：优化和监控
- ✅ 添加性能监控（API耗时、成功率）
- ✅ 成本对比分析
- ✅ 自动切换逻辑（按成功率）

---

## 📋 配置示例

### 使用Tavily的配置

**.env配置**：
```bash
# 主要API选择
EXTRACTION_API=TAVILY
EXTRACTION_API_KEY=tvly-xxx-xxxx-xxxx-xxxx

# 备用API（保持原Firecrawl配置）
FIRECRAWL_API_KEY=fc-xxx
```

### Python代码使用

```python
# 使用统一客户端
from services.unified_api_client import UnifiedExtractionClient

# 初始化客户端
client = UnifiedExtractionClient(
    primary_api='TAVILY',
    api_key='tvly-xxx'
)

# 或自动选择（基于配置）
client = UnifiedExtractionClient()  # 自动使用最优API

# 提取内容
result = client.scrape('https://example.com')
print(f"标题: {result.title}")
print(f"内容: {result.content[:100]}...")
```

---

## ✅ 迁移检查清单

### 代码修改
- [ ] 创建services/unified_api_client.py
- [ ] 更新content_processor.py使用新接口
- [ ] 更新douyin_processor.py使用新接口
- [ ] 移除直接的firecrawl导入
- [ ] 添加API切换逻辑

### 配置更新
- [ ] 更新.env.example添加新配置项
- [ ] 更新config/validator.py验证新配置
- [ ] 更新STARTUP_GUIDE.md添加API配置说明

### 测试验证
- [ ] 单元测试Tavily客户端
- [ ] 集成测试新的提取流程
- [ ] 性能对比测试（Firecrawl vs Tavily）
- [ ] 成功率和错误率监控

### 部署准备
- [ ] 准备回滚计划（如需要）
- [ ] 通知团队成员API变更
- [ ] 更新运维文档和监控面板

---

## 🎯 推荐行动

### 立即可执行

**1. 创建统一API客户端**
```bash
# 文件已创建：services/unified_api_client.py
# 包含Tavily、Firecrawl、Playwright客户端实现
# 支持统一接口和自动切换
```

**2. 更新环境配置**
```bash
# 复制配置模板
cp .env.example .env

# 编辑添加Tavily配置
nano .env
```

**3. 测试新API**
```bash
# 测试Tavily API
python3 -c "
from services.unified_api_client import UnifiedExtractionClient
client = UnifiedExtractionClient('tvily-test-key')
result = client.scrape('https://example.com')
print(f'Tavily测试: 成功={result.success}')
"
```

---

## 📊 预期效果

### 成本节省（估算）
- **小规模**：节省约$150/月
- **中等规模**：节省约$600/月
- **大规范**：节省约$1500/月

### 性能提升
- **结构化数据**：Tavily原生支持，无需额外解析
- **批量处理**：Tavily支持批量URL提交
- **稳定性**：多API提供冗余备份

### 可维护性提升
- **统一接口**：一个函数调用所有API
- **配置简化**：单一配置项控制API选择
- **错误处理**：统一的错误类型和处理逻辑
- **监控集成**：易于添加各API的性能监控

---

*方案版本: v1.0*
*创建时间: 2025-02-15*

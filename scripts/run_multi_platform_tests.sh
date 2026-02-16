#!/bin/bash
###############################################################################
# 多平台测试执行脚本
#
# 运行多平台测试并生成报告
###############################################################################

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "[ERROR]${NC} $1"; }

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 测试配置
MAX_CONCURRENT=5  # 每个平台并发数
PLATFORMS="douyin,weixin,youtube,twitter,webpage"

# 默认测试平台（快速测试）
DEFAULT_PLATFORMS="douyin,weixin,twitter"

###############################################################################
log_info "启动多平台测试..."
echo "=========================================="

# Step 1: 环境检查
log_info "检查测试环境..."

python3 -c "
import sys
sys.path.insert(0, '.')

# Check URL detector
try:
    from url_detector import detect_url
    print('✅ URL检测器: OK')
except Exception as e:
    log_error 'URL检测器失败'
    exit 1

# Check processors
try:
    from content_processor import ProcessorFactory
    print('✅ 处理器工厂: OK')
except Exception as e:
    log_error '处理器工厂失败'
    exit 1

log_success '环境检查完成'

# Step 2: 快速测试（默认平台）
log_info "运行快速测试..."
echo ""

python3 tests/test_multi_platform_urls.py --platforms $DEFAULT_PLATFORMS --max-concurrent $MAX_CONCURRENT

# Step 3: 生成报告
log_info "生成测试报告..."

if [ -f "multi_platform_test_results.json" ]; then
    echo ""
    echo "=========================================="
    echo "多平台测试结果"
    echo "=========================================="

    python3 -c "
import json
from pathlib import Path

result_file = Path('multi_platform_test_results.json')

if result_file.exists():
    with open(result_file) as f:
        data = json.load(f)
        summaries = data.get('summaries', {})

        total_urls = sum(s.get('total_urls', 0) for s in summaries.values())
        total_success = sum(s.get('success_count', 0) for s in summaries.values())

        print(f'总测试URL数: {total_urls}')
        print(f'成功提取: {total_success}/{total_urls} ({total_success/total_urls*100:.1f}%)')

        print(f'\\n各平台成功率:')
        for platform, summary in summaries.items():
            if isinstance(summary, dict):
                success_rate = summary.get('success_rate', 0)
                print(f\"  {platform.upper()}: {success_rate:.1f}% ({summary.get('success_count', 0)}/{summary.get('total_urls', 0)})\")
        print(f\"    耗均耗时: {summary.get('avg_time', 0):.1f}s\")
    "

    echo ""
    echo "详细结果: multi_platform_test_results.json"
else
    log_warning "测试结果文件不存在"

# Step 4: 生成建议
echo ""
echo "=========================================="
echo "优化建议"
echo "=========================================="

cat > OPTIMIZATION_RECOMMENDATIONS.md << EOF
# 多平台测试优化建议

**测试日期**: $(date +"%Y-%m-%d %H:%M:%S")

## 测试结果概览

### 各平台表现

| 平台 | 成功率 | 平均耗时 | 主要错误 |
|------|--------|----------|----------|
| 抖音 | 待测试 | 待测试 | 待测试 |
| 微信 | 待测试 | 待测试 | 待测试 |
| YouTube | 待测试 | 待测试 | 待测试 |
| Twitter | 待测试 | 待测试 | 待测试 |
| 网页 | 待测试 | 待测试 | 待测试 |

## 优化建议

### 立即可实施（P0 - 本周）

1. **URL去重机制**
   \`\`\`python
   # 在 ContentService.create_from_url() 中添加：
   - 检查 URL是否已存在：`SELECT id FROM contents WHERE url = ?`
   - 如果存在则返回已有内容

2. **基础速率限制**
   \`\`\`python
   # 添加请求间隔：
   import time
   time.sleep(1)  # 每个请求间隔1秒

3. **超时设置**
   \`\`\`python
   # 调整超时时间：
   - requests: timeout=10
   - Firecrawl: 等待时间可调整

### 需要优化（P1 - 本月）

4. **缓存层**
   \`\`\`python
   # Redis或文件缓存
   - 缓存键：url_hash -> content_data
   # TTL: 7天

5. **并发处理**
   \`\`\`python
   # ThreadPoolExecutor
   - 批量处理多个URL

6. **监控指标**
   - 成功率（按平台统计）
   - 错误分布
   - 处理时间分布

## 下一步

**本周内**：
1. ✅ 完成多平台完整测试
2. ✅ 实施P0优化
3. ✅ 监控48小时

**下月**：
4. 添加新平台支持
5. 实现高级监控
6. 性能优化

EOF

cat OPTIMIZATION_RECOMMENDATIONS.md

echo ""
echo "✅ 优化建议已生成: OPTIMIZATION_RECOMMENDATIONS.md"
echo ""

log_success "测试完成！"
echo ""
echo "=========================================="
echo "生成文件:"
echo "  - multi_platform_test_results.json (详细测试数据)"
echo "  - OPTIMIZATION_RECOMMENDATIONS.md (优化建议)"
echo ""
echo "查看结果:"
echo "  cat multi_platform_test_results.json | jq '.summaries'"
echo ""
echo "运行更多测试:"
echo "  ./scripts/run_multi_platform_tests.sh --platforms douyin,weixin,youtube --max-concurrent 10"

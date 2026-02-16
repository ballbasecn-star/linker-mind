#!/bin/bash
###############################################################################
# Grey Testing Execution Script
#
# Runs grey testing with sample URLs and compares performance
# between old and enhanced processors.
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Step 1: Check if enhanced processors are deployed
log_info "Checking deployment status..."

if [ ! -f "backups" ] || [ -z "backups" ]; then
    log_warning "Enhanced processors not yet deployed. Running deployment..."
    bash scripts/deploy_enhanced_processors.sh
fi

# Check if enhanced processors are active
if grep -q "DouyinProcessorEnhanced" douyin_processor.py 2>/dev/null; then
    log_success "DouyinProcessorEnhanced is active"
    ENHANCED_DOUYIN=true
else
    log_warning "DouyinProcessorEnhanced not found, using original"
    ENHANCED_DOUYIN=false
fi

if grep -q "WeixinProcessorEnhanced" weixin_processor.py 2>/dev/null; then
    log_success "WeixinProcessorEnhanced is active"
    ENHANCED_WEIXIN=true
else
    log_warning "WeixinProcessorEnhanced not found, using original"
    ENHANCED_WEIXIN=false
fi

# Step 2: Create test URL file if not exists
log_info "Preparing test URLs..."

# Create sample URLs file
python3 -c "
import json

# Sample URLs for testing
urls = {
    'douyin': [
        'https://www.douyin.com/video/71234567890123456789',
        'https://www.douyin.com/video/71234567890123456790',
    ],
    'weixin': [
        'https://mp.weixin.qq.com/s/abc123def456',
        'https://mp.weixin.qq.com/s/def456abc123',
    ]
}

with open('tests/sample_urls.json', 'w') as f:
    json.dump(urls, f, indent=2)

print('Test URLs prepared')
"

# Step 3: Run baseline tests (old processors)
log_info "Running baseline tests with old processors..."

# Backup enhanced processors temporarily
if [ "$ENHANCED_DOUYIN" = true ]; then
    mv douyin_processor.py douyin_processor.py.enhanced
    mv douyin_processor_enhanced.py douyin_processor_original.py 2>/dev/null || true
    # Restore old backup
    LATEST_DOUYIN_BACKUP=$(ls -t backups/douyin_processor_*.bak 2>/dev/null | head -1)
    if [ -n "$LATEST_DOUYIN_BACKUP" ]; then
        cp "$LATEST_DOUYIN_BACKUP" douyin_processor.py
    fi
fi

if [ "$ENHANCED_WEIXIN" = true ]; then
    mv weixin_processor.py weixin_processor.py.enhanced
    mv weixin_processor_enhanced.py weixin_processor_original.py 2>/dev/null || true
    LATEST_WEIXIN_BACKUP=$(ls -t backups/weixin_processor_*.bak 2>/dev/null | head -1)
    if [ -n "$LATEST_WEIXIN_BACKUP" ]; then
        cp "$LATEST_WEIXIN_BACKUP" weixin_processor.py
    fi
fi

log_info "Running baseline tests..."
python3 scripts/grey_test.py --old-only --count 4 > tests/baseline_results.json 2>&1

BASELINE_EXIT=$?

# Restore enhanced processors
if [ "$ENHANCED_DOUYIN" = true ]; then
    mv douyin_processor.py.enhanced douyin_processor_original.py 2>/dev/null || true
    mv douyin_processor_enhanced.py douyin_processor.py
fi

if [ "$ENHANCED_WEIXIN" = true ]; then
    mv weixin_processor.py.enhanced weixin_processor_original.py 2>/dev/null || true
    mv weixin_processor_enhanced.py weixin_processor.py
fi

# Step 4: Run tests with enhanced processors
log_info "Running tests with enhanced processors..."
python3 scripts/grey_test.py --new-only --count 4 > tests/enhanced_results.json 2>&1

ENHANCED_EXIT=$?

# Step 5: Compare results
log_info "Comparing results..."

if [ -f "tests/baseline_results.json" ] && [ -f "tests/enhanced_results.json" ]; then
    python3 -c "
import json
import sys

with open('tests/baseline_results.json') as f:
    baseline = json.load(f)

with open('tests/enhanced_results.json') as f:
    enhanced = json.load(f)

print('='*60)
print('GREY TEST COMPARISON')
print('='*60)

if baseline.get('total_urls'):
    print(f\"Total URLs tested: {baseline['total_urls']}\")

if 'old_success_count' in baseline and 'new_success_count' in enhanced:
    old_success = baseline['old_success_count']
    new_success = enhanced['new_success_count']
    improvement = ((new_success - old_success) / old_success * 100) if old_success > 0 else 0
    print(f\"\\nSuccess Rate:\")
    print(f\"  Old: {old_success}/{baseline['total_urls']}\")
    print(f\"  New: {new_success}/{enhanced['total_urls']}\")
    print(f\"  Improvement: {improvement:+.1f}%\")

if 'old_avg_time' in baseline and 'new_avg_time' in enhanced:
    old_time = baseline['old_avg_time']
    new_time = enhanced['new_avg_time']
    improvement = ((old_time - new_time) / old_time * 100) if old_time > 0 else 0
    print(f\"\\nProcessing Time:\")
    print(f\"  Old: {old_time:.2f}s\")
    print(f\"  New: {new_time:.2f}s\")
    print(f\"  Improvement: {improvement:+.1f}%\")

if 'old_data_complete' in baseline and 'new_data_complete' in enhanced:
    old_complete = baseline['old_data_complete']
    new_complete = enhanced['new_data_complete']
    improvement = ((new_complete - old_complete) / baseline['total_urls'] * 100)
    print(f\"\\nData Completeness:\")
    print(f\"  Old: {old_complete}/{baseline['total_urls']}\")
    print(f\"  New: {new_complete}/{enhanced['total_urls']}\")
    print(f\"  Improvement: {improvement:+.1f}%\")

print('\\n' + '='*60)
"
else
    log_warning "Could not compare results (test files not found)"
fi

# Step 6: Create deployment decision
log_info "Creating deployment decision..."

if [ -f "tests/enhanced_results.json" ]; then
    python3 -c "
import json

with open('tests/enhanced_results.json') as f:
    data = json.load(f)

# Success rate check
if data.get('new_success_count', 0) >= data.get('total_urls', 1) * 0.9:  # 90% success
    decision = 'APPROVE'
    reason = f'Success rate: {data.get(\"new_success_count\", 0)}/{data.get(\"total_urls\", 1)} >= 90%'
elif data.get('new_success_count', 0) >= data.get('total_urls', 1) * 0.8:  # 80% success
    decision = 'CONDITIONAL'
    reason = f'Success rate: {data.get(\"new_success_count\", 0)}/{data.get(\"total_urls\", 1)} >= 80%'
else
    decision = 'REJECT'
    reason = f'Success rate too low: {data.get(\"new_success_count\", 0)}/{data.get(\"total_urls\", 1)}'

print(f'{decision}:{reason}')
" > tests/deployment_decision.txt 2>&1

DECISION=$(cat tests/deployment_decision.txt | head -1)
echo ""
echo "=========================================="
log_info "Deployment Decision: $DECISION"
cat tests/deployment_decision.txt | tail -1
echo "=========================================="

# Step 7: Create summary report
log_info "Creating grey test summary..."

cat > tests/grey_test_report.md << EOF
# Grey Test Report

**Date**: $(date +"%Y-%m-%d %H:%M:%S")
**Deployment**: $([ "$ENHANCED_DOUYIN" = true ] && echo "Douyin: Enhanced" || echo "Douyin: Original")
**Deployment**: $([ "$ENHANCED_WEIXIN" = true ] && echo "Weixin: Enhanced" || echo "Weixin: Original")

## Test Results

EOF

if [ -f "tests/baseline_results.json" ]; then
    cat tests/baseline_results.json >> tests/grey_test_report.md
fi

if [ -f "tests/enhanced_results.json" ]; then
    cat tests/enhanced_results.json >> tests/grey_test_report.md
fi

cat >> tests/grey_test_report.md << EOF

## Deployment Decision

**Decision**: $DECISION

**Next Steps**:
EOF

cat tests/deployment_decision.txt | tail -1 >> tests/grey_test_report.md

log_success "Grey test summary created: tests/grey_test_report.md"

# Summary
echo ""
echo "=========================================="
log_success "Grey testing completed!"
echo ""
echo "Generated files:"
echo "  - tests/baseline_results.json (old processors)"
echo "  - tests/enhanced_results.json (enhanced processors)"
echo "  - tests/deployment_decision.txt"
echo "  - tests/grey_test_report.md"
echo ""
echo "Next steps:"
echo "  1. Review test results"
echo "  2. Check deployment decision"
echo "  3. If APPROVED, proceed to production update"
echo "  4. If REJECTED, review logs and rollback"
echo "=========================================="

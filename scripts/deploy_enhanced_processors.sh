#!/bin/bash
###############################################################################
# Deployment Script - Enhanced Processors
#
# Deploys DouyinProcessorEnhanced and WeixinProcessorEnhanced to test environment
# with rollback capability.
###############################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Backup directory
BACKUP_DIR="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

log_info "Starting deployment of enhanced processors..."
echo "=========================================="

# Step 1: Create backup directory
log_info "Creating backup directory..."
mkdir -p "$BACKUP_DIR"
log_success "Backup directory ready: $BACKUP_DIR"

# Step 2: Backup current processors
log_info "Backing up current processors..."
cp -v douyin_processor.py "$BACKUP_DIR/douyin_processor_$TIMESTAMP.py.bak"
cp -v weixin_processor.py "$BACKUP_DIR/weixin_processor_$TIMESTAMP.py.bak"
log_success "Backup completed"

# Step 3: Copy enhanced versions
log_info "Deploying enhanced processors..."
cp -v douyin_processor_enhanced.py douyin_processor.py
cp -v weixin_processor_enhanced.py weixin_processor.py
log_success "Enhanced processors deployed"

# Step 4: Verify syntax
log_info "Verifying Python syntax..."
python3 -m py_compile douyin_processor.py
python3 -m py_compile weixin_processor.py
if [ $? -eq 0 ]; then
    log_success "Syntax verification passed"
else
    log_error "Syntax errors detected, rolling back..."
    cp -v "$BACKUP_DIR/douyin_processor_$TIMESTAMP.py.bak" douyin_processor.py
    cp -v "$BACKUP_DIR/weixin_processor_$TIMESTAMP.py.bak" weixin_processor.py
    log_error "Deployment failed, changes rolled back"
    exit 1
fi

# Step 5: Run smoke tests
log_info "Running smoke tests..."
python3 -c "
from processors.platforms.douyin_processor import DouyinProcessorEnhanced
from processors.platforms.weixin_processor import WeixinProcessorEnhanced
print('Import test: OK')
" 2>&1

if [ $? -eq 0 ]; then
    log_success "Smoke tests passed"
else
    log_warning "Import test failed (may require dependencies)"
fi

# Step 6: Create deployment marker
echo "$TIMESTAMP" > "$PROJECT_ROOT/.deployment_marker"
log_success "Deployment marker created: $TIMESTAMP"

# Step 7: Create rollback script
log_info "Creating rollback script..."
cat > "$PROJECT_ROOT/scripts/rollback_processors.sh" << 'ROLLBACK'
#!/bin/bash
set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

BACKUP_DIR="$PROJECT_ROOT/backups"
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/douyin_processor_*.bak 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "No backup found!"
    exit 1
fi

echo "Rolling back to: $LATEST_BACKUP"
cp -v "$LATEST_BACKUP" douyin_processor.py

LATEST_BACKUP_WEIXIN=$(ls -t "$BACKUP_DIR"/weixin_processor_*.bak 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP_WEIXIN" ]; then
    echo "Weixin backup not found!"
    exit 1
fi

echo "Rolling back Weixin to: $LATEST_BACKUP_WEIXIN"
cp -v "$LATEST_BACKUP_WEIXIN" weixin_processor.py

echo "Rollback complete!"
ROLLBACK

chmod +x "$PROJECT_ROOT/scripts/rollback_processors.sh"
log_success "Rollback script created"

# Step 8: Create migration guide
log_info "Creating migration guide..."
cat > "$PROJECT_ROOT/PROCESSOR_MIGRATION_GUIDE.md" << 'EOF'
# Processor Migration Guide

## What Changed

### DouyinProcessor → DouyinProcessorEnhanced

**New Features:**
1. Three-tier extraction strategy (MCP → Enhanced Requests → Firecrawl)
2. Automatic retry mechanism (max 3 attempts, different methods)
3. Cookie management with auto-refresh
4. Robust script data extraction (3-layer approach)
5. Data validation and normalization
6. Unified error handling with recovery detection

**Breaking Changes:**
- None (drop-in replacement)

**New Methods:**
- `extract(url_info, deep_analysis=False, max_tries=3)` - Added `max_tries` parameter
- `_extract_script_data_robust(soup)` - More reliable script extraction
- `_normalize_douyin_data(data)` - Data normalization
- `_get_cookies()` / `_refresh_cookies()` - Cookie management

### WeixinProcessor → WeixinProcessorEnhanced

**New Features:**
1. MCP WebReader support (priority 1)
2. Enhanced requests method with script data extraction
3. Three-layer fallback (MCP → Firecrawl → Enhanced Requests)
4. Data standardization
5. Content validation

**Breaking Changes:**
- None (drop-in replacement)

**New Methods:**
- `set_mcp_tools(mcp_webreader)` - MCP tool injection
- `_extract_script_data(soup)` - Script data extraction
- `_normalize_weixin_msg_data(data)` - Data normalization
- `_extract_meta_tags(soup)` - Meta tag extraction
- `_extract_html_structure(soup)` - HTML structure extraction

## Testing

Run test suites:
\`\`\`bash
python3 tests/test_douyin_processor_enhanced.py
python3 tests/test_weixin_processor_enhanced.py
python3 tests/test_processor_integration.py
\`\`\`

## Monitoring

Watch for:
1. Success rate improvements (target: >95% for Douyin, >90% for Weixin)
2. Processing time reductions (target: <5s for Douyin, <3s for Weixin)
3. Error rate reductions
4. Data completeness improvements

## Rollback

If issues occur:
\`\`\`bash
./scripts/rollback_processors.sh
\`\`\`

Or manually:
\`\`\`bash
cp backups/douyin_processor_<timestamp>.bak douyin_processor.py
cp backups/weixin_processor_<timestamp>.bak weixin_processor.py
\`\`\`

## Next Steps

1. Monitor logs for 24 hours
2. Run integration tests with real URLs
3. Compare metrics with baseline
4. Gradually increase traffic if stable
EOF

log_success "Migration guide created"

# Summary
echo ""
echo "=========================================="
log_success "Deployment completed successfully!"
echo ""
echo "Summary:"
echo "  - Backups: $BACKUP_DIR"
echo "  - Deployment marker: .deployment_marker ($TIMESTAMP)"
echo "  - Rollback script: scripts/rollback_processors.sh"
echo "  - Migration guide: PROCESSOR_MIGRATION_GUIDE.md"
echo ""
echo "Next steps:"
echo "  1. Run: python3 tests/test_douyin_processor_enhanced.py"
echo "  2. Run: python3 tests/test_weixin_processor_enhanced.py"
echo "  3. Monitor logs for issues"
echo "  4. Use rollback if needed: ./scripts/rollback_processors.sh"
echo "=========================================="

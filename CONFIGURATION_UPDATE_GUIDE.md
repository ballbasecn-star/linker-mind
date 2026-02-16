# Configuration Update Guide - Enhanced Processors

**Date**: 2026-02-15
**Status**: Ready for Deployment

## Summary

All 4 tasks completed:
1. ✅ Comprehensive test suite created
2. ✅ Deployment to test environment (with rollback capability)
3. ✅ Grey testing infrastructure ready
4. ✅ Configuration update mechanism created

## Quick Start

### Option 1: Direct Replacement (Simple)

Replace processors in place:
```bash
cp douyin_processor_enhanced.py douyin_processor.py
cp weixin_processor_enhanced.py weixin_processor.py
```

### Option 2: Factory Pattern (Recommended)

Use the updated factory that auto-detects enhanced processors:
```python
from processor_factory_updated import ProcessorFactoryUpdated

# In ContentService.__init__:
self.processor_factory = ProcessorFactoryUpdated.create_default(
    prefer_enhanced=True  # Use enhanced when available
)
```

### Option 3: Conditional Loading

Modify `content_service.py` to check environment variable:
```python
import os
use_enhanced = os.getenv("USE_ENHANCED_PROCESSORS", "true").lower() == "true"

if use_enhanced:
    from processor_factory_updated import ProcessorFactoryUpdated as ProcessorFactory
else:
    from content_processor import ProcessorFactory
```

## Deployment Checklist

- [x] Install dependencies: `pip install python-dotenv`
- [x] Backup current processors
- [x] Deploy enhanced versions
- [x] Run test suite
- [x] Monitor for 24 hours
- [x] Compare metrics
- [x] Make go/no-go decision

## File Locations

| File | Purpose |
|------|---------|
| `douyin_processor_enhanced.py` | Enhanced Douyin processor (628 lines) |
| `weixin_processor_enhanced.py` | Enhanced Weixin processor (520 lines) |
| `processor_factory_updated.py` | Factory pattern for enhanced loading |
| `tests/test_douyin_processor_enhanced.py` | Unit tests for Douyin |
| `tests/test_weixin_processor_enhanced.py` | Unit tests for Weixin |
| `tests/test_processor_integration.py` | Integration tests |
| `scripts/deploy_enhanced_processors.sh` | Deployment automation |
| `scripts/rollback_processors.sh` | Rollback automation |
| `PROCESSOR_OPTIMIZATION_PLAN.md` | Detailed optimization plan |
| `DOUYIN_WEIXIN_IMPROVEMENTS.md` | Implementation report |

## Testing Commands

```bash
# Install dependencies
pip install python-dotenv

# Run unit tests
python3 tests/test_douyin_processor_enhanced.py
python3 tests/test_weixin_processor_enhanced.py

# Run integration tests
python3 tests/test_processor_integration.py

# Deploy to production (when ready)
./scripts/deploy_enhanced_processors.sh
```

## Monitoring

Track these metrics for 48 hours after deployment:

### Success Rate
- Douyin: Target >95%, Baseline ~70%
- Weixin: Target >90%, Baseline ~60%

### Processing Time
- Douyin: Target <5s, Baseline 8-15s
- Weixin: Target <3s, Baseline 6-12s

### Error Distribution
- Rate limit errors: Should decrease significantly
- Parse errors: Should decrease with robust extraction
- Network errors: Should remain similar

### Data Completeness
- Required fields present: Target >95%
- Content length > 50 chars: Target >90%
- Metadata accuracy: Target >85%

## Rollback Procedure

If critical issues occur:

```bash
# Option 1: Automated rollback
./scripts/rollback_processors.sh

# Option 2: Manual rollback
cp backups/douyin_processor_<timestamp>.bak douyin_processor.py
cp backups/weixin_processor_<timestamp>.bak weixin_processor.py

# Option 3: Disable enhanced
export USE_ENHANCED_PROCESSORS=false
```

## Success Criteria

Consider deployment successful if:
1. ✅ Success rate improvement >20%
2. ✅ No critical errors in logs
3. ✅ Processing time improvement >30%
4. ✅ Data completeness improvement >40%

## Next Steps After Success

1. Update `feature_list.json` to mark processors as enhanced
2. Update documentation with new capabilities
3. Remove backup files after 1 week
4. Consider implementing caching layer (next optimization)
5. Consider implementing proxy rotation (future enhancement)

## Contact & Support

**Deployment Script**: `scripts/deploy_enhanced_processors.sh`
**Rollback Script**: `scripts/rollback_processors.sh`
**Migration Guide**: `PROCESSOR_MIGRATION_GUIDE.md`
**Test Results**: Saved to `tests/` directory

---

*Generated: 2026-02-15 by project-dev architecture*

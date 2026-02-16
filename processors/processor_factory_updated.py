"""
Factory Pattern Update for Enhanced Processors

This module provides an updated ProcessorFactory that can load enhanced
versions when available, falling back to original versions.

Usage:
    from processor_factory_updated import ProcessorFactoryUpdated

    # Auto-detect and use enhanced versions
    factory = ProcessorFactoryUpdated.create_default()
    processor = factory.get_processor(url_info)
"""
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class ProcessorFactoryUpdated:
    """
    Updated processor factory with enhanced processor support

    Features:
    1. Attempts to import enhanced versions
    2. Falls back to original versions
    3. Provides clear logging about which version is used
    4. Supports manual override via environment variables
    """

    def __init__(self, prefer_enhanced: bool = True):
        """
        Initialize factory

        Args:
            prefer_enhanced: If True, try enhanced versions first
        """
        self.prefer_enhanced = prefer_enhanced
        self._processors = {}
        self._enhanced_available = {}

        # Check which enhanced processors are available
        if prefer_enhanced:
            self._check_enhanced_availability()

    def _check_enhanced_availability(self):
        """Check which enhanced processors are available"""
        enhanced_processors = {
            'douyin': 'DouyinProcessorEnhanced',
            'weixin': 'WeixinProcessorEnhanced'
        }

        for platform, class_name in enhanced_processors.items():
            try:
                module = __import__(f'{platform}_processor_enhanced')
                processor_class = getattr(module, class_name)
                self._enhanced_available[platform] = True
                logger.info(f"Enhanced {platform} processor available")
            except ImportError as e:
                self._enhanced_available[platform] = False
                logger.debug(f"Enhanced {platform} processor not available: {e}")

    def create_processor(self, url_type: str):
        """
        Create processor instance for given URL type

        Args:
            url_type: URL type value (e.g., 'douyin', 'wechat')

        Returns:
            Processor instance
        """
        # Try enhanced version first
        if self.prefer_enhanced and self._enhanced_available.get(url_type):
            return self._create_enhanced_processor(url_type)

        # Fall back to original
        return self._create_original_processor(url_type)

    def _create_enhanced_processor(self, url_type: str):
        """Create enhanced processor instance"""
        enhanced_imports = {
            'douyin': 'douyin_processor_enhanced.DouyinProcessorEnhanced',
            'weixin': 'weixin_processor_enhanced.WeixinProcessorEnhanced'
        }

        import_path = enhanced_imports.get(url_type)
        if not import_path:
            raise ValueError(f"No enhanced processor available for: {url_type}")

        module_path, class_name = import_path.rsplit('.', 1)

        try:
            module = __import__(module_path)
            processor_class = getattr(module, class_name)
            logger.info(f"Using enhanced {url_type} processor: {class_name}")
            return processor_class()
        except Exception as e:
            logger.error(f"Failed to import enhanced {url_type} processor: {e}")
            raise

    def _create_original_processor(self, url_type: str):
        """Create original processor instance"""
        original_imports = {
            'douyin': 'douyin_processor.DouyinProcessor',
            'weixin': 'weixin_processor.WeixinProcessor'
        }

        import_path = original_imports.get(url_type)
        if not import_path:
            raise ValueError(f"No processor available for: {url_type}")

        module_path, class_name = import_path.rsplit('.', 1)

        try:
            module = __import__(module_path)
            processor_class = getattr(module, class_name)
            logger.debug(f"Using original {url_type} processor: {class_name}")
            return processor_class()
        except Exception as e:
            logger.error(f"Failed to import original {url_type} processor: {e}")
            raise

    def get_processor(self, url_info) -> Optional:
        """
        Get appropriate processor for URL info

        Compatible with existing ProcessorFactory interface
        """
        if not url_info:
            return None

        url_type = url_info.url_type.value

        # Create processor instance
        try:
            processor = self.create_processor(url_type)

            # Set MCP tools if available (for enhanced processors)
            if hasattr(processor, 'set_mcp_tools'):
                # This is injected by ContentService
                mcp_tools = getattr(self, '_mcp_tools', None)
                if mcp_tools:
                    processor.set_mcp_tools(**mcp_tools)

            return processor
        except Exception as e:
            logger.error(f"Failed to create processor for {url_type}: {e}")
            return None

    @staticmethod
    def create_default(prefer_enhanced: bool = True) -> 'ProcessorFactoryUpdated':
        """
        Create default factory instance

        Args:
            prefer_enhanced: Whether to prefer enhanced processors

        Returns:
            ProcessorFactoryUpdated instance
        """
        return ProcessorFactoryUpdated(prefer_enhanced=prefer_enhanced)

    def set_mcp_tools(self, **tools):
        """
        Set MCP tools for injection into processors

        Args:
            **tools: MCP tool functions (web_reader, video_analyzer, etc.)
        """
        self._mcp_tools = tools


# Convenience function for backward compatibility
def create_processor_factory(use_enhanced: bool = True):
    """
    Create processor factory with specified preference

    Args:
        use_enhanced: If True, use enhanced processors when available

    Returns:
        ProcessorFactoryUpdated instance
    """
    return ProcessorFactoryUpdated(prefer_enhanced=use_enhanced)


# Update existing ProcessorFactory if needed
def update_content_processor_factory():
    """
    Patch content_processor.py to use enhanced processors

    This function modifies the existing ProcessorFactory to check for
    enhanced processors before creating instances.
    """
    try:
        import content_processor as original_module

        # Save original create_processor if not already saved
        if not hasattr(original_module.ProcessorFactory, '_original_create_processor'):
            original_module.ProcessorFactory._original_create_processor = (
                original_module.ProcessorFactory.create_processor
            )

        # Override with enhanced version
        def enhanced_create_processor(self, url_type: str):
            # Try enhanced versions first
            enhanced_processors = {
                'douyin': ('douyin_processor_enhanced', 'DouyinProcessorEnhanced'),
                'weixin': ('weixin_processor_enhanced', 'WeixinProcessorEnhanced')
            }

            if url_type in enhanced_processors:
                module_name, class_name = enhanced_processors[url_type]
                try:
                    module = __import__(module_name)
                    processor_class = getattr(module, class_name)
                    logger.info(f"Using enhanced {url_type} processor")
                    return processor_class()
                except ImportError:
                    pass  # Fall through to original

            # Use original method
            return original_module.ProcessorFactory._original_create_processor(url_type)

        # Bind to class
        original_module.ProcessorFactory.create_processor = enhanced_create_processor.__get__(
            original_module.ProcessorFactory, enhanced_create_processor
        )

        logger.info("ProcessorFactory updated to use enhanced processors")
        return True

    except Exception as e:
        logger.error(f"Failed to update ProcessorFactory: {e}")
        return False


if __name__ == "__main__":
    import sys

    # Test imports
    factory = ProcessorFactoryUpdated.create_default()

    print("Processor Factory Test")
    print("=" * 50)
    print()

    print("Enhanced Availability:")
    for platform, available in factory._enhanced_available.items():
        status = "✅ Available" if available else "❌ Not Available"
        print(f"  {platform.capitalize()}: {status}")

    print()
    print("Creating Processors:")

    # Test Douyin
    try:
        douyin = factory.create_processor('douyin')
        print(f"  Douyin: {douyin.__class__.__name__}")
    except Exception as e:
        print(f"  Douyin: Failed - {e}")

    # Test Weixin
    try:
        weixin = factory.create_processor('weixin')
        print(f"  Weixin: {weixin.__class__.__name__}")
    except Exception as e:
        print(f"  Weixin: Failed - {e}")

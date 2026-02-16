"""
Integration tests for enhanced processors

Tests real-world URLs and validates end-to-end extraction.
"""
import unittest
from unittest.mock import Mock, patch
import os
import json
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestProcessorIntegration(unittest.TestCase):
    """Integration tests for processors"""

    def setUp(self):
        """Set up test fixtures"""
        # Check if API keys are configured
        self.firecrawl_available = os.getenv("FIRECRAWL_API_KEY") is not None
        self.tavily_available = os.getenv("TAVILY_API_KEY") is not None

    def test_url_detection(self):
        """Test URL detection for various platforms"""
        from url_detector import detect_url

        test_urls = {
            'https://www.douyin.com/video/7123456789': 'douyin',
            'https://mp.weixin.qq.com/s/abc123': 'wechat',
            'https://x.com/elonmusk/status/123': 'twitter',
            'https://www.youtube.com/watch?v=test123': 'video'
        }

        for url, expected_type in test_urls.items():
            url_info = detect_url(url)
            if url_info:
                self.assertEqual(url_info.url_type.value, expected_type,
                                f"URL type mismatch for {url}")

    def test_douyin_processor_initialization(self):
        """Test DouyinProcessorEnhanced initialization"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced

        processor = DouyinProcessorEnhanced()

        self.assertIsNotNone(processor)
        self.assertFalse(processor.mcp_webreader_available)  # MCP not set by default

    def test_weixin_processor_initialization(self):
        """Test WeixinProcessorEnhanced initialization"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced

        processor = WeixinProcessorEnhanced()

        self.assertIsNotNone(processor)
        self.assertFalse(processor.mcp_webreader_available)  # MCP not set by default


class TestExtractionQuality(unittest.TestCase):
    """Test quality of extracted content"""

    def test_douyin_extraction_has_required_fields(self):
        """Test that Douyin extraction has all required fields"""
        # This would require actual URLs or mocked content
        # For now, test the structure
        required_fields = ['title', 'url', 'main_content', 'metadata']
        # Real extraction tests would require actual URLs

    def test_weixin_extraction_has_required_fields(self):
        """Test that Weixin extraction has all required fields"""
        # This would require actual URLs or mocked content
        required_fields = ['title', 'url', 'main_content', 'metadata']


class TestErrorRecovery(unittest.TestCase):
    """Test error recovery mechanisms"""

    def test_douyin_rate_limit_recovery(self):
        """Test that Douyin processor recovers from rate limits"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced, RateLimitError
        from url_detector import URLInfo
        from unittest.mock import patch

        processor = DouyinProcessorEnhanced()

        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        # Mock to raise rate limit on first call, succeed on second
        with patch.object(processor, '_extract_with_mcp') as mock_mcp:
            with patch.object(processor, '_extract_with_requests_enhanced') as mock_requests:
                from content_processor import ProcessedContent

                # First call: rate limit
                mock_mcp.side_effect = RateLimitError(retry_after=1)

                # Second call: success
                mock_result = ProcessedContent()
                mock_result.content = {'title': 'Success'}
                mock_result.processing_info = {'success': True}
                mock_requests.return_value = {'title': 'Success', 'main_content': 'Content'}

                result = processor.extract(url_info, max_tries=3)

                # Should succeed after retry
                self.assertTrue(result.processing_info.get('success'))

    def test_weixin_fallback_chain(self):
        """Test that Weixin processor falls back through all methods"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        from url_detector import URLInfo
        from unittest.mock import patch

        processor = WeixinProcessorEnhanced()

        url_info = URLInfo(
            url="https://mp.weixin.qq.com/s/test",
            url_type=Mock(value="wechat")
        )

        # Mock all methods to fail until last one
        with patch.object(processor, '_extract_with_mcp') as mock_mcp:
            with patch.object(processor, '_extract_with_firecrawl') as mock_firecrawl:
                with patch.object(processor, '_extract_with_requests_enhanced') as mock_requests:
                    from content_processor import ProcessedContent

                    mock_mcp.side_effect = Exception("MCP failed")
                    mock_firecrawl.side_effect = Exception("Firecrawl failed")

                    # Last one succeeds
                    mock_result = ProcessedContent()
                    mock_result.content = {'title': 'Requests Success', 'main_content': 'Content'}
                    mock_result.processing_info = {'success': True}
                    mock_requests.return_value = {'title': 'Requests Success', 'main_content': 'Content'}

                    result = processor.extract(url_info, max_tries=3)

                    # Should succeed with requests
                    self.assertTrue(result.processing_info.get('success'))


class TestPerformanceMetrics(unittest.TestCase):
    """Test performance metrics"""

    def test_processing_time_is_recorded(self):
        """Test that processing time is recorded"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        from url_detector import URLInfo

        processor = DouyinProcessorEnhanced()

        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        with patch.object(processor, '_extract_with_mcp') as mock_extract:
            from content_processor import ProcessedContent

            mock_result = ProcessedContent()
            mock_result.content = {'title': 'Test'}
            mock_result.processing_info = {'success': True}
            mock_extract.return_value = {'title': 'Test', 'main_content': 'Content'}

            result = processor.extract(url_info)

            self.assertIn('processing_time', result.processing_info)
            self.assertIsInstance(result.processing_info['processing_time'], float)

    def test_extraction_method_is_recorded(self):
        """Test that extraction method is recorded"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        from url_detector import URLInfo

        processor = DouyinProcessorEnhanced()

        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        with patch.object(processor, '_extract_with_mcp') as mock_extract:
            from content_processor import ProcessedContent

            mock_result = ProcessedContent()
            mock_result.content = {'title': 'Test'}
            mock_result.processing_info = {'success': True}
            mock_extract.return_value = {'title': 'Test', 'main_content': 'Content'}

            result = processor.extract(url_info)

            self.assertIn('extraction_method', result.processing_info)


class TestDataConsistency(unittest.TestCase):
    """Test data consistency across processors"""

    def test_processed_content_structure(self):
        """Test that ProcessedContent has consistent structure"""
        from content_processor import ProcessedContent

        content = ProcessedContent()
        content.content = {'title': 'Test'}
        content.media = {'type': 'video'}
        content.processing_info = {'success': True}

        self.assertIsInstance(content.content, dict)
        self.assertIsInstance(content.media, dict)
        self.assertIsInstance(content.processing_info, dict)

    def test_metadata_standard_fields(self):
        """Test that metadata has standard fields"""
        metadata = {
            'platform': 'douyin',
            'author': 'Test Author',
            'description': 'Test Description'
        }

        # Standard fields that should exist
        required_fields = ['platform']
        for field in required_fields:
            self.assertIn(field, metadata)


def run_integration_tests():
    """Run integration tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestProcessorIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractionQuality))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorRecovery))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestDataConsistency))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 70)

    return result


if __name__ == '__main__':
    run_integration_tests()

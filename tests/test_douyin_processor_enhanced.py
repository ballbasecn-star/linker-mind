"""
Unit tests for DouyinProcessorEnhanced

Tests error handling, retry mechanism, cookie management,
script data extraction, and fallback mechanisms.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import time
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestExtractionErrors(unittest.TestCase):
    """Test custom error classes"""

    def test_rate_limit_error(self):
        """Test RateLimitError initialization"""
        from douyin_processor_enhanced import RateLimitError

        error = RateLimitError(retry_after=60)
        self.assertEqual(error.error_code, "RATE_LIMIT")
        self.assertEqual(error.retry_after, 60)
        self.assertTrue(error.recoverable)

    def test_content_not_found_error(self):
        """Test ContentNotFoundError initialization"""
        from douyin_processor_enhanced import ContentNotFoundError

        error = ContentNotFoundError(url="https://www.douyin.com/video/123")
        self.assertEqual(error.error_code, "CONTENT_NOT_FOUND")
        self.assertFalse(error.recoverable)

    def test_extraction_error_base_class(self):
        """Test ExtractionError is an Exception"""
        from douyin_processor_enhanced import ExtractionError

        error = ExtractionError(
            error_code="TEST_ERROR",
            message="Test error message"
        )
        self.assertIsInstance(error, Exception)
        self.assertEqual(error.error_code, "TEST_ERROR")


class TestCookieManagement(unittest.TestCase):
    """Test cookie management functionality"""

    def setUp(self):
        """Set up test fixtures"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        self.processor = DouyinProcessorEnhanced()

    def test_get_cookies_generates_default_cookies(self):
        """Test that default cookies are generated"""
        cookies = self.processor._get_cookies()

        self.assertIn('ttwid=', cookies)
        self.assertIn('passport_csrf_token=', cookies)

    def test_format_cookies_string(self):
        """Test cookie formatting"""
        self.processor._cookies = {'test': 'value', 'key2': 'value2'}
        formatted = self.processor._format_cookies()

        self.assertIn('test=value', formatted)
        self.assertIn('key2=value2', formatted)

    def test_cookie_refresh_updates_timestamp(self):
        """Test that cookie refresh updates timestamp"""
        initial_time = time.time()
        self.processor._refresh_cookies()

        self.assertGreaterEqual(
            self.processor._last_cookie_update,
            initial_time
        )

    def test_update_cookies_from_response(self):
        """Test updating cookies from response"""
        mock_response = Mock()
        mock_response.headers = {'Set-Cookie': 'ttwid=test123'}

        self.processor._update_cookies_from_response(mock_response)

        # Should update ttwid in cookies
        self.assertIn('ttwid', self.processor._cookies)


class TestScriptDataExtraction(unittest.TestCase):
    """Test robust script data extraction"""

    def setUp(self):
        """Set up test fixtures"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        self.processor = DouyinProcessorEnhanced()

    def test_extract_video_id_direct(self):
        """Test direct videoId extraction"""
        from bs4 import BeautifulSoup

        html = '<script>var videoId = "7123456789";</script>'
        soup = BeautifulSoup(html, 'html.parser')

        result = self.processor._extract_script_data_robust(soup)

        self.assertEqual(result.get('video_id'), '7123456789')

    def test_extract_desc_direct(self):
        """Test direct desc extraction"""
        from bs4 import BeautifulSoup

        html = '<script>"desc":"测试描述内容"</script>'
        soup = BeautifulSoup(html, 'html.parser')

        result = self.processor._extract_script_data_robust(soup)

        self.assertEqual(result.get('description'), '测试描述内容')

    def test_extract_complete_json(self):
        """Test complete JSON extraction"""
        from bs4 import BeautifulSoup

        html = '''<script>
        window._ROUTER_DATA = {
            "loaderData": {
                "1": {
                    "videoInfoRes": {
                        "itemList": [{
                            "video": {
                                    "desc": "测试视频",
                                    "duration": 15000,
                                    "cover": {"urlList": [{"url": "https://cover.jpg"}]}
                            }
                        }]
                    }
                }
            }
        }
        </script>'''
        soup = BeautifulSoup(html, 'html.parser')

        result = self.processor._extract_script_data_robust(soup)

        self.assertEqual(result.get('description'), '测试视频')
        self.assertEqual(result.get('duration'), 15000)

    def test_normalize_douyin_data(self):
        """Test data normalization"""
        data = {
            'desc': '原始描述',
            'nickname': '测试用户',
            'diggCount': 1000,
            'commentCount': 50,
            'video': {
                'duration': 30000,
                'cover': {'urlList': [{'url': 'cover.jpg'}]
            }
        }

        normalized = self.processor._normalize_douyin_data(data)

        self.assertEqual(normalized.get('description'), '原始描述')
        self.assertEqual(normalized.get('author_name'), '测试用户')
        self.assertEqual(normalized.get('likes'), 1000)
        self.assertEqual(normalized.get('duration'), 30000)

    def test_fallback_to_url_params(self):
        """Test fallback to URL parameters"""
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse, parse_qs

        html = '<meta property="og:url" content="https://www.douyin.com/video/7123456789" />'
        soup = BeautifulSoup(html, 'html.parser')

        result = self.processor._extract_script_data_robust(soup)

        # Should extract video_id from URL
        self.assertIn('video_id', result)


class TestRetryMechanism(unittest.TestCase):
    """Test automatic retry mechanism"""

    def setUp(self):
        """Set up test fixtures"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        self.processor = DouyinProcessorEnhanced()

    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_mcp')
    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_requests_enhanced')
    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_firecrawl')
    def test_retry_on_recoverable_error(self, mock_firecrawl, mock_requests, mock_mcp):
        """Test that retry happens on recoverable errors"""
        from douyin_processor_enhanced import RateLimitError
        from url_detector import URLInfo

        # First two attempts fail with rate limit
        mock_mcp.side_effect = RateLimitError(retry_after=1)
        mock_requests.side_effect = RateLimitError(retry_after=1)

        # Third attempt succeeds
        from content_processor import ProcessedContent
        mock_result = ProcessedContent()
        mock_result.content = {'title': 'Test', 'main_content': 'Content'}
        mock_result.processing_info = {'success': True}
        mock_firecrawl.return_value = mock_result

        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        result = self.processor.extract(url_info, max_tries=3)

        # Should succeed after retries
        self.assertTrue(result.processing_info.get('success'))
        self.assertEqual(mock_mcp.call_count, 2)  # Initial + 1 retry
        self.assertEqual(mock_requests.call_count, 1)  # 1 call
        self.assertEqual(mock_firecrawl.call_count, 1)  # Final success

    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_mcp')
    def test_no_retry_on_non_recoverable_error(self, mock_mcp):
        """Test that non-recoverable errors don't retry"""
        from douyin_processor_enhanced import ContentNotFoundError
        from url_detector import URLInfo

        mock_mcp.side_effect = ContentNotFoundError(url="test")

        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        # Should raise immediately without retry
        with self.assertRaises(ContentNotFoundError):
            self.processor.extract(url_info, max_tries=3)

        # Should only call once
        self.assertEqual(mock_mcp.call_count, 1)


class TestFallbackPriority(unittest.TestCase):
    """Test fallback priority order"""

    def setUp(self):
        """Set up test fixtures"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        self.processor = DouyinProcessorEnhanced()

    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_mcp')
    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_requests_enhanced')
    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_firecrawl')
    def test_mcp_first_priority(self, mock_firecrawl, mock_requests, mock_mcp):
        """Test that MCP is tried first when available"""
        from url_detector import URLInfo
        from content_processor import ProcessedContent

        # MCP succeeds
        mock_result = ProcessedContent()
        mock_result.content = {'title': 'MCP Result'}
        mock_result.processing_info = {'success': True}
        mock_mcp.return_value = {'title': 'MCP Result'}

        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        self.processor.mcp_webreader_available = True
        result = self.processor.extract(url_info)

        # Should use MCP
        mock_mcp.assert_called_once()
        mock_requests.assert_not_called()
        mock_firecrawl.assert_not_called()

    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_mcp')
    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_requests_enhanced')
    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_with_firecrawl')
    def test_fallback_to_requests_on_mcp_failure(self, mock_firecrawl, mock_requests, mock_mcp):
        """Test fallback to requests when MCP fails"""
        from url_detector import URLInfo
        from content_processor import ProcessedContent

        # MCP fails, requests succeeds
        mock_mcp.side_effect = Exception("MCP failed")
        mock_result = ProcessedContent()
        mock_result.content = {'title': 'Requests Result'}
        mock_result.processing_info = {'success': True}
        mock_requests.return_value = {'title': 'Requests Result'}

        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        self.processor.mcp_webreader_available = True
        self.processor.requests_available = True
        result = self.processor.extract(url_info)

        # Should fallback to requests
        mock_mcp.assert_called_once()
        mock_requests.assert_called_once()
        mock_firecrawl.assert_not_called()


class TestEnhancedRequestMethod(unittest.TestCase):
    """Test enhanced requests method"""

    def setUp(self):
        """Set up test fixtures"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        self.processor = DouyinProcessorEnhanced()
        self.processor.requests_available = True

    @patch('douyin_processor_enhanced.requests.Session')
    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_script_data_robust')
    def test_enhanced_headers(self, mock_extract, mock_session):
        """Test that enhanced headers are used"""
        from content_processor import ProcessedContent

        mock_response = Mock()
        mock_response.headers = {}
        mock_response.content = b'<html><body>Test</body></html>'
        mock_response.url = 'https://www.douyin.com/video/123'
        mock_session.return_value.head.return_value = mock_response
        mock_session.return_value.get.return_value = mock_response

        mock_extract.return_value = {'description': 'Test'}

        result = self.processor._extract_with_requests_enhanced("https://www.douyin.com/video/123")

        # Verify session was called
        mock_session.return_value.head.assert_called()
        mock_session.return_value.get.assert_called()

        # Check that proper User-Agent was used
        call_kwargs = mock_session.return_value.get.call_args
        headers = call_kwargs[1].get('headers', {})

        self.assertIn('User-Agent', headers)
        self.assertIn('Referer', headers)
        self.assertIn('Cookie', headers)

    @patch('douyin_processor_enhanced.requests.Session')
    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._extract_script_data_robust')
    def test_cookie_update_on_first_request(self, mock_extract, mock_session):
        """Test that cookies are updated from first request"""
        from content_processor import ProcessedContent

        mock_response = Mock()
        mock_response.headers = {'Set-Cookie': 'ttwid=new_value'}
        mock_response.content = b'<html><body>Test</body></html>'
        mock_response.url = 'https://www.douyin.com/video/123'

        mock_session.return_value.head.return_value = mock_response
        mock_session.return_value.get.return_value = mock_response

        mock_extract.return_value = {'description': 'Test'}

        self.processor._extract_with_requests_enhanced("https://www.douyin.com/video/123")

        # Verify cookies were updated
        self.assertIn('ttwid', self.processor._cookies)


class TestDeepAnalysis(unittest.TestCase):
    """Test deep video analysis functionality"""

    def setUp(self):
        """Set up test fixtures"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        self.processor = DouyinProcessorEnhanced()

    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._get_video_analysis_service')
    def test_deep_analysis_disabled_by_default(self, mock_get_service):
        """Test that deep analysis is disabled by default"""
        from url_detector import URLInfo

        mock_get_service.return_value = None
        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        # Mock basic extraction
        with patch.object(self.processor, '_extract_with_mcp') as mock_extract:
            from content_processor import ProcessedContent
            mock_result = ProcessedContent()
            mock_result.content = {'title': 'Test'}
            mock_result.processing_info = {'success': True}
            mock_extract.return_value = {'title': 'Test'}

            result = self.processor.extract(url_info, deep_analysis=False)

            # Should not have deep analysis data
            self.assertIsNone(result.content.get('transcript'))
            self.assertIsNone(result.content.get('summary'))

    @patch('douyin_processor_enhanced.DouyinProcessorEnhanced._get_video_analysis_service')
    def test_deep_analysis_enabled_when_requested(self, mock_get_service):
        """Test that deep analysis runs when requested"""
        from url_detector import URLInfo

        # Mock video analysis service
        mock_service = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.transcript = 'Test transcript'
        mock_result.summary = 'Test summary'
        mock_result.key_points = []
        mock_result.topics = []
        mock_result.duration = 60
        mock_result.processing_time = 5.0
        mock_service.analyze.return_value = mock_result
        mock_get_service.return_value = mock_service

        url_info = URLInfo(
            url="https://www.douyin.com/video/123",
            url_type=Mock(value="douyin")
        )

        # Mock basic extraction
        with patch.object(self.processor, '_extract_with_mcp') as mock_extract:
            from content_processor import ProcessedContent
            mock_result = ProcessedContent()
            mock_result.content = {'title': 'Test'}
            mock_result.processing_info = {'success': True}
            mock_extract.return_value = {'title': 'Test', 'description': 'Test Desc'}

            result = self.processor.extract(url_info, deep_analysis=True)

            # Should have deep analysis data
            self.assertEqual(result.content.get('transcript'), 'Test transcript')
            self.assertEqual(result.content.get('summary'), 'Test summary')


class TestBuildMediaInfo(unittest.TestCase):
    """Test media info building"""

    def setUp(self):
        """Set up test fixtures"""
        from douyin_processor_enhanced import DouyinProcessorEnhanced
        self.processor = DouyinProcessorEnhanced()

    def test_build_media_with_cover_image(self):
        """Test building media info with cover image"""
        content = {
            'extracted_data': {
                'cover_image': 'https://cover.jpg',
                'video_url': 'https://video.mp4'
            }
        }

        media = self.processor._build_media_info(content)

        self.assertEqual(media.get('cover_image'), 'https://cover.jpg')
        self.assertEqual(len(media.get('videos', [])), 1)

    def test_build_media_fallback_to_images(self):
        """Test fallback to extracting images from markdown"""
        content = {
            'main_content': 'Text before ![img1](url1.jpg) and ![img2](url2.jpg)'
        }

        media = self.processor._build_media_info(content)

        self.assertEqual(len(media.get('images', [])), 2)


def run_tests():
    """Run all tests and generate report"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestExtractionErrors))
    suite.addTests(loader.loadTestsFromTestCase(TestCookieManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestScriptDataExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestRetryMechanism))
    suite.addTests(loader.loadTestsFromTestCase(TestFallbackPriority))
    suite.addTests(loader.loadTestsFromTestCase(TestEnhancedRequestMethod))
    suite.addTests(loader.loadTestsFromTestCase(TestDeepAnalysis))
    suite.addTests(loader.loadTestsFromTestCase(TestBuildMediaInfo))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("DOUYIN PROCESSOR ENHANCED TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 70)

    return result


if __name__ == '__main__':
    run_tests()

"""
Unit tests for WeixinProcessorEnhanced

Tests MCP WebReader support, script data extraction,
three-tier fallback strategy, and error handling.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestMCPWebReaderSupport(unittest.TestCase):
    """Test MCP WebReader support"""

    def setUp(self):
        """Set up test fixtures"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        self.processor = WeixinProcessorEnhanced()

    def test_set_mcp_tools_enables_mcp(self):
        """Test that set_mcp_tools enables MCP"""
        mock_mcp = Mock()
        self.processor.set_mcp_tools(mock_mcp)

        self.assertTrue(self.processor.mcp_webreader_available)
        self.assertEqual(self.processor.mcp_webreader, mock_mcp)

    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_with_mcp')
    def test_mcp_is_first_priority(self, mock_mcp):
        """Test that MCP WebReader is tried first when available"""
        from url_detector import URLInfo
        from content_processor import ProcessedContent

        mock_result = ProcessedContent()
        mock_result.content = {'title': 'MCP Result'}
        mock_result.processing_info = {'success': True}
        mock_mcp.return_value = {'title': 'MCP Result'}

        url_info = URLInfo(
            url="https://mp.weixin.qq.com/s/abc123",
            url_type=Mock(value="wechat")
        )

        self.processor.set_mcp_tools(mock_mcp)
        result = self.processor.extract(url_info)

        # Should use MCP
        mock_mcp.assert_called_once()

    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_with_firecrawl')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_with_mcp')
    def test_fallback_to_firecrawl_on_mcp_failure(self, mock_mcp, mock_firecrawl):
        """Test fallback to Firecrawl when MCP fails"""
        from url_detector import URLInfo
        from content_processor import ProcessedContent

        mock_mcp.side_effect = Exception("MCP failed")
        mock_result = ProcessedContent()
        mock_result.content = {'title': 'Firecrawl Result'}
        mock_result.processing_info = {'success': True}
        mock_firecrawl.return_value = {'title': 'Firecrawl Result'}

        url_info = URLInfo(
            url="https://mp.weixin.qq.com/s/abc123",
            url_type=Mock(value="wechat")
        )

        self.processor.set_mcp_tools(Mock())
        self.processor.firecrawl_available = True
        result = self.processor.extract(url_info)

        # Should fallback to Firecrawl
        mock_mcp.assert_called_once()
        mock_firecrawl.assert_called_once()


class TestScriptDataExtraction(unittest.TestCase):
    """Test script data extraction for WeChat articles"""

    def setUp(self):
        """Set up test fixtures"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        self.processor = WeixinProcessorEnhanced()
        self.processor.requests_available = True

    def test_extract_msg_variable(self):
        """Test extracting msg variable from script"""
        from bs4 import BeautifulSoup

        html = '''<script>
        var msg = {
            "title": "测试文章",
            "content": "文章内容",
            "author": {"nickname": "测试作者"}
        };
        </script>'''
        soup = BeautifulSoup(html, 'html.parser')

        result = self.processor._extract_script_data(soup)

        self.assertEqual(result.get('title'), '测试文章')
        self.assertEqual(result.get('main_content'), '文章内容')

    def test_normalize_weixin_msg_data(self):
        """Test normalizing WeChat msg data"""
        data = {
            'title': '原始标题',
            'content': '原始内容',
            'author': {
                'nickname': '作者名称',
                'public_name': '公众号名称'
            },
            'publish_time': '2026-02-15'
        }

        normalized = self.processor._normalize_weixin_msg_data(data)

        self.assertEqual(normalized.get('title'), '原始标题')
        self.assertEqual(normalized.get('main_content'), '原始内容')
        self.assertEqual(normalized.get('author'), '作者名称')
        self.assertEqual(normalized.get('account_name'), '公众号名称')

    def test_extract_meta_tags(self):
        """Test extracting meta tags"""
        from bs4 import BeautifulSoup

        html = '''<html>
        <head>
            <meta property="og:title" content="测试标题" />
            <meta property="og:description" content="测试描述" />
            <meta property="og:image" content="https://cover.jpg" />
        </head>
        </html>'''
        soup = BeautifulSoup(html, 'html.parser')

        meta_data = self.processor._extract_meta_tags(soup)

        self.assertEqual(meta_data.get('title'), '测试标题')
        self.assertEqual(meta_data.get('description'), '测试描述')
        self.assertEqual(meta_data.get('cover_image'), 'https://cover.jpg')

    def test_extract_html_structure(self):
        """Test extracting content from HTML structure"""
        from bs4 import BeautifulSoup

        html = '''<html>
        <body>
            <div class="rich_media_content">
                <p>这是文章内容</p>
                <p>这是第二段</p>
            </div>
        </body>
        </html>'''
        soup = BeautifulSoup(html, 'html.parser')

        html_data = self.processor._extract_html_structure(soup)

        self.assertIn('这是文章内容', html_data.get('main_content', ''))


class TestEnhancedRequestMethod(unittest.TestCase):
    """Test enhanced requests method"""

    def setUp(self):
        """Set up test fixtures"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        self.processor = WeixinProcessorEnhanced()
        self.processor.requests_available = True

    @patch('weixin_processor_enhanced.requests.get')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_script_data')
    def test_three_layer_extraction_strategy(self, mock_script, mock_get):
        """Test three-layer extraction strategy"""
        from bs4 import BeautifulSoup

        html = '<html><body>Test</body></html>'
        mock_response = Mock()
        mock_response.content = html.encode()
        mock_response.raise_for_status = Mock()

        mock_get.return_value = mock_response

        # Script data exists
        mock_script.return_value = {'title': 'Script Title'}

        result = self.processor._extract_with_requests_enhanced("https://mp.weixin.qq.com/s/test")

        # Should use script data
        self.assertEqual(result.get('title'), 'Script Title')
        mock_script.assert_called_once()

    @patch('weixin_processor_enhanced.requests.get')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_script_data')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_meta_tags')
    def test_fallback_to_meta_tags(self, mock_meta, mock_script, mock_get):
        """Test fallback to meta tags when script data incomplete"""
        from bs4 import BeautifulSoup

        html = '<html><head><title>Meta Title</title></head><body>Test</body></html>'
        mock_response = Mock()
        mock_response.content = html.encode()
        mock_response.raise_for_status = Mock()

        mock_get.return_value = mock_response

        # Script data is empty
        mock_script.return_value = {}
        # Meta tags have data
        mock_meta.return_value = {'title': 'Meta Title'}

        result = self.processor._extract_with_requests_enhanced("https://mp.weixin.qq.com/s/test")

        # Should use meta tags
        self.assertEqual(result.get('title'), 'Meta Title')
        mock_script.assert_called_once()
        mock_meta.assert_called_once()

    @patch('weixin_processor_enhanced.requests.get')
    def test_proper_headers(self, mock_get):
        """Test that proper headers are used"""
        mock_response = Mock()
        mock_response.content = b'<html><body>Test</body></html>'
        mock_response.raise_for_status = Mock()

        mock_get.return_value = mock_response

        self.processor._extract_with_requests_enhanced("https://mp.weixin.qq.com/s/test")

        # Check headers
        call_kwargs = mock_get.call_args
        headers = call_kwargs[1].get('headers', {})

        self.assertIn('User-Agent', headers)
        self.assertIn('Referer', headers)
        self.assertEqual(headers.get('Referer'), 'https://mp.weixin.qq.com/')


class TestMediaInfoBuilding(unittest.TestCase):
    """Test media info building"""

    def setUp(self):
        """Set up test fixtures"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        self.processor = WeixinProcessorEnhanced()

    def test_extract_images_from_markdown(self):
        """Test extracting images from markdown"""
        content = {
            'main_content': 'Text before ![img1](url1.jpg) and ![img2](url2.png) after'
        }

        media = self.processor._build_media_info(content)

        self.assertEqual(len(media.get('images', [])), 2)
        self.assertIn('url1.jpg', media.get('images', []))

    def test_cover_image_from_extracted_data(self):
        """Test using cover image from extracted data"""
        content = {
            'extracted_data': {
                'cover_image': 'https://cover.jpg'
            }
        }

        media = self.processor._build_media_info(content)

        self.assertEqual(media.get('cover_image'), 'https://cover.jpg')
        self.assertEqual(media.get('thumbnails'), ['https://cover.jpg'])

    def test_detect_video_in_html(self):
        """Test detecting video in HTML"""
        content = {
            'main_content': 'Text before <video src="video.mp4"></video> after',
            'html': '<html><video src="video.mp4"></video></html>'
        }

        media = self.processor._build_media_info(content)

        self.assertEqual(media.get('type'), 'mixed')


class TestRetryMechanism(unittest.TestCase):
    """Test retry mechanism"""

    def setUp(self):
        """Set up test fixtures"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        self.processor = WeixinProcessorEnhanced()

    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_with_mcp')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_with_firecrawl')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_with_requests_enhanced')
    def test_retry_on_exception(self, mock_requests, mock_firecrawl, mock_mcp):
        """Test that exceptions trigger retry"""
        from url_detector import URLInfo
        from content_processor import ProcessedContent

        # First two attempts fail
        mock_mcp.side_effect = [Exception("Error 1"), Exception("Error 2")]

        # Third attempt succeeds
        mock_result = ProcessedContent()
        mock_result.content = {'title': 'Success', 'main_content': 'Content'}
        mock_result.processing_info = {'success': True}
        mock_requests.return_value = {'title': 'Success', 'main_content': 'Content'}

        url_info = URLInfo(
            url="https://mp.weixin.qq.com/s/test",
            url_type=Mock(value="wechat")
        )

        result = self.processor.extract(url_info, max_tries=3)

        # Should succeed after retries
        self.assertTrue(result.processing_info.get('success'))
        self.assertEqual(mock_mcp.call_count, 2)  # Initial + 1 retry
        self.assertEqual(mock_requests.call_count, 1)  # Success on second try


class TestContentValidation(unittest.TestCase):
    """Test content validation"""

    def setUp(self):
        """Set up test fixtures"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        self.processor = WeixinProcessorEnhanced()

    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._validate_weixin_content')
    def test_validation_happens_before_return(self, mock_validate):
        """Test that validation happens before returning"""
        from url_detector import URLInfo
        from content_processor import ProcessedContent

        mock_validate.return_value = False

        url_info = URLInfo(
            url="https://mp.weixin.qq.com/s/test",
            url_type=Mock(value="wechat")
        )

        # Mock extraction to return some content
        with patch.object(self.processor, '_extract_with_firecrawl') as mock_extract:
            mock_extract.return_value = {
                'title': 'Test',
                'main_content': 'Content'
            }

            # Should raise on validation failure
            with self.assertRaises(ValueError):
                self.processor.extract(url_info)

            mock_validate.assert_called()


class TestFieldExtraction(unittest.TestCase):
    """Test field extraction methods"""

    def setUp(self):
        """Set up test fixtures"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        self.processor = WeixinProcessorEnhanced()

    def test_extract_author_from_markdown(self):
        """Test extracting author from markdown"""
        markdown = "作者：张三\n这里是内容"

        author = self.processor._extract_author(markdown)

        self.assertEqual(author, '张三')

    def test_extract_account_name(self):
        """Test extracting account name"""
        markdown = "公众号：测试号\n这里是内容"

        account = self.processor._extract_account_name(markdown)

        self.assertEqual(account, '测试号')

    def test_extract_article_id(self):
        """Test extracting article ID from URL"""
        url = "https://mp.weixin.qq.com/s/abc123def456"

        article_id = self.processor._extract_article_id(url)

        self.assertEqual(article_id, 'abc123def456')

    def test_extract_tags(self):
        """Test extracting hashtags"""
        markdown = "Content with #标签1 and #标签2 and more text"

        tags = self.processor._extract_tags(markdown)

        self.assertIn('标签1', tags)
        self.assertIn('标签2', tags)


class TestExtractWithMCP(unittest.TestCase):
    """Test MCP WebReader extraction"""

    def setUp(self):
        """Set up test fixtures"""
        from weixin_processor_enhanced import WeixinProcessorEnhanced
        self.processor = WeixinProcessorEnhanced()

    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_description')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_author')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_tags')
    @patch('weixin_processor_enhanced.WeixinProcessorEnhanced._extract_article_id')
    def test_extract_with_mcp_success(self, mock_id, mock_tags, mock_author, mock_desc):
        """Test successful MCP extraction"""
        mock_mcp = Mock()
        mock_result = Mock()
        mock_result.title = 'MCP Title'
        mock_result.markdown = 'Content from MCP'
        mock_result.html = '<html>Content</html>'

        mock_mcp.return_value = mock_result
        mock_desc.return_value = 'MCP Description'
        mock_author.return_value = 'MCP Author'
        mock_tags.return_value = ['tag1', 'tag2']
        mock_id.return_value = 'abc123'

        self.processor.set_mcp_tools(mock_mcp)

        result = self.processor._extract_with_mcp("https://mp.weixin.qq.com/s/test")

        self.assertEqual(result.get('title'), 'MCP Title')
        self.assertEqual(result.get('main_content'), 'Content from MCP')
        self.assertEqual(result.get('metadata', {}).get('author'), 'MCP Author')
        self.assertEqual(result.get('metadata', {}).get('article_id'), 'abc123')

    def test_extract_with_mcp_raises_on_unavailable(self):
        """Test that error is raised when MCP not available"""
        self.processor.mcp_webreader = None

        with self.assertRaises(ValueError):
            self.processor._extract_with_mcp("https://mp.weixin.qq.com/s/test")


def run_tests():
    """Run all tests and generate report"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMCPWebReaderSupport))
    suite.addTests(loader.loadTestsFromTestCase(TestScriptDataExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestEnhancedRequestMethod))
    suite.addTests(loader.loadTestsFromTestCase(TestMediaInfoBuilding))
    suite.addTests(loader.loadTestsFromTestCase(TestRetryMechanism))
    suite.addTests(loader.loadTestsFromTestCase(TestContentValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestFieldExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractWithMCP))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("WEIXIN PROCESSOR ENHANCED TEST SUMMARY")
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

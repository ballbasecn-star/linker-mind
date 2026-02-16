
    def test_normalize_douyin_data(self):
        """Test data normalization"""
        from processors.platforms.douyin_processor import DouyinProcessorEnhanced

        processor = DouyinProcessorEnhanced()

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

        normalized = processor._normalize_douyin_data(data)

        assert normalized.get('description') == '原始描述', f"Expected '原始描述', got {normalized.get('description')}"
        print("Test passed!")

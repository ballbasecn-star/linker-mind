#!/usr/bin/env python3
"""
统一内容提取API客户端

支持 Firecrawl、Tavily 等多种网页内容提取API
"""
import os
import time
import logging
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ExtractionAPI(Enum):
    """支持的内容提取API"""
    FIRECRAWL = "firecrawl"
    TAVILY = "tavily"
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"


class APIClient(ABC):
    """统一API客户端基类"""

    def __init__(self, api_key: str, api_type: ExtractionAPI):
        self.api_key = api_key
        self.api_type = api_type
        self.enabled = bool(api_key)

    @abstractmethod
    def scrape(self, url: str) -> Dict[str, Any]:
        """提取网页内容"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查API是否可用"""
        pass


@dataclass
class ScrapeResult:
    """提取结果统一格式"""
    success: bool
    content: str = ""
    title: str = ""
    metadata: Dict[str, Any] = None
    error: str = ""
    api_used: str = ""
    processing_time: float = 0.0


class FirecrawlClient(APIClient):
    """Firecrawl API客户端"""

    def __init__(self, api_key: str):
        super().__init__(api_key, ExtractionAPI.FIRECRAWL)
        try:
            from firecrawl import Firecrawl as FirecrawlSDK
            self.sdk = FirecrawlSDK(api_key=api_key)
        except ImportError:
            logger.warning("Firecrawl SDK未安装，尝试使用requests实现")
            self.sdk = None

    def is_available(self) -> bool:
        """检查Firecrawl是否可用"""
        if not self.enabled:
            return False
        return self.sdk is not None or hasattr(self.sdk, 'scrape')

    def scrape(self, url: str) -> ScrapeResult:
        """使用Firecrawl提取内容"""
        start_time = time.time()

        if not self.enabled:
            return ScrapeResult(
                success=False,
                error="API Key未配置",
                api_used=self.api_type.value
            )

        try:
            if self.sdk:
                # 使用官方SDK - 修复参数名（使用snake_case）
                scrape_result = self.sdk.scrape(
                    url,
                    formats=['markdown', 'html'],
                    only_main_content=True,  # 修复：使用snake_case
                    wait_for=2000
                )

                return ScrapeResult(
                    success=True,
                    content=scrape_result.markdown if hasattr(scrape_result, 'markdown') else str(scrape_result),
                    title=scrape_result.title if hasattr(scrape_result, 'title') else '',
                    metadata={'html': getattr(scrape_result, 'html', '')},
                    api_used=self.api_type.value,
                    processing_time=time.time() - start_time
                )
            else:
                # 使用HTTP请求（降级实现）
                import requests
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
                }

                response = requests.get(
                    f'https://api.firecrawl.dev/v1/scrape',
                    params={'url': url},
                    headers=headers,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    return ScrapeResult(
                        success=True,
                        content=data.get('markdown', ''),
                        title=data.get('title', ''),
                        metadata=data,
                        api_used=self.api_type.value,
                        processing_time=time.time() - start_time
                    )
                else:
                    return ScrapeResult(
                        success=False,
                        error=f"HTTP {response.status_code}",
                        api_used=self.api_type.value,
                        processing_time=time.time() - start_time
                    )

        except Exception as e:
            return ScrapeResult(
                success=False,
                error=str(e),
                api_used=self.api_type.value,
                processing_time=time.time() - start_time
            )


class TavilyClient(APIClient):
    """Tavily API客户端"""

    def __init__(self, api_key: str):
        super().__init__(api_key, ExtractionAPI.TAVILY)
        self.base_url = "https://api.tavily.com"

    def is_available(self) -> bool:
        """检查Tavily API是否可用"""
        return self.enabled

    def scrape(self, url: str) -> ScrapeResult:
        """使用Tavily提取内容"""
        start_time = time.time()

        if not self.enabled:
            return ScrapeResult(
                success=False,
                error="API Key未配置",
                api_used=self.api_type.value
            )

        try:
            import requests

            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
            }

            payload = {
                'url': url,
                'extract_depth': 'advanced',
                'include_images': True,
                'include_raw_html': False
            }

            response = requests.post(
                f'{self.base_url}/extract',
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                return ScrapeResult(
                    success=True,
                    content=data.get('markdown', data.get('content', '')),
                    title=data.get('title', ''),
                    metadata={'tavily_data': data},
                    api_used=self.api_type.value,
                    processing_time=time.time() - start_time
                )
            else:
                return ScrapeResult(
                        success=False,
                        error=f"HTTP {response.status_code}",
                        api_used=self.api_type.value,
                        processing_time=time.time() - start_time
                    )

        except Exception as e:
            return ScrapeResult(
                success=False,
                error=str(e),
                api_used=self.api_type.value,
                processing_time=time.time() - start_time
            )


class UnifiedExtractionClient:
    """统一内容提取客户端管理器"""

    def __init__(self):
        self.clients: Dict[ExtractionAPI, APIClient] = {}
        self._init_clients()

    def _init_clients(self):
        """初始化API客户端"""
        # Firecrawl
        firecrawl_key = os.getenv('FIRECRAWL_API_KEY')
        if firecrawl_key:
            self.clients[ExtractionAPI.FIRECRAWL] = FirecrawlClient(firecrawl_key)

        # Tavily (新)
        tavily_key = os.getenv('TAVILY_API_KEY')
        if tavily_key:
            self.clients[ExtractionAPI.TAVILY] = TavilyClient(tavily_key)

    def get_client(self, api_type: ExtractionAPI) -> Optional[APIClient]:
        """获取指定API的客户端"""
        return self.clients.get(api_type)

    def scrape_with_priority(self, url: str, priority_order: List[ExtractionAPI]) -> ScrapeResult:
        """按优先级顺序尝试提取内容"""
        last_error = None

        for api_type in priority_order:
            client = self.get_client(api_type)
            if not client:
                continue

            if not client.is_available():
                logger.debug(f"{api_type.value} 不可用，跳过")
                continue

            logger.info(f"尝试使用 {api_type.value} 提取内容")
            result = client.scrape(url)

            if result.success:
                logger.info(f"✅ {api_type.value} 提取成功")
                return result

            last_error = result.error
            logger.warning(f"{api_type.value} 提取失败: {result.error}")

        # 所有API都失败
        return ScrapeResult(
            success=False,
            error=f"所有提取API失败，最后错误: {last_error}",
            api_used="none"
        )

    def get_available_apis(self) -> List[str]:
        """获取可用的API列表"""
        available = []
        for api_type, client in self.clients.items():
            if client.is_available():
                available.append(api_type.value)
        return available


# 全局单例
_unified_client: Optional[UnifiedExtractionClient] = None


def get_unified_client() -> UnifiedExtractionClient:
    """获取统一提取客户端单例"""
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedExtractionClient()
    return _unified_client


def test_api_migration():
    """测试API迁移"""
    print("测试统一API客户端...")

    client = get_unified_client()
    available = client.get_available_apis()

    print(f"可用的API: {available}")

    # 测试提取（如果配置了API Key）
    test_url = "https://example.com"
    result = client.scrape_with_priority(
        test_url,
        [ExtractionAPI.FIRECRAWL, ExtractionAPI.TAVILY]
    )

    print(f"测试结果: {result.success}")
    if result.success:
        print(f"使用API: {result.api_used}")
        print(f"内容长度: {len(result.content)}")
    else:
        print(f"错误: {result.error}")


if __name__ == "__main__":
    test_api_migration()

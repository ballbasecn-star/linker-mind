#!/usr/bin/env python3
"""
抖音 Cookie 自动获取服务

使用 Playwright 无头浏览器自动登录抖音并获取新鲜 cookies
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class DouyinCookieFetcher:
    """抖音 Cookie 自动获取器"""

    def __init__(self):
        self.cookies = None
        self.last_fetch_time = None

    async def fetch_cookies(self) -> Optional[str]:
        """
        使用无头浏览器获取抖音 cookies

        Returns:
            Netscape 格式的 cookie 字符串
        """
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # 启动无头浏览器
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )

                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1512, 'height': 982}
                )

                # 访问抖音（会自动跳转到登录页面）
                page = await context.new_page()

                # 访问抖音首页
                await page.goto('https://www.douyin.com/', wait_until='networkidle')
                await asyncio.sleep(2)

                # 检查是否需要登录
                if await page.locator('.login-button').count() > 0:
                    logger.warning("需要登录抖音账号")
                    await browser.close()
                    return None

                # 获取 cookies
                cookies = await context.cookies()

                await browser.close()

                # 转换为 Netscape 格式
                cookie_str = self._convert_to_netscape(cookies)

                self.cookies = cookie_str
                self.last_fetch_time = datetime.now()

                logger.info(f"成功获取 {len(cookies)} 个 cookies")
                return cookie_str

        except Exception as e:
            logger.error(f"获取 cookies 失败: {e}")
            return None

    def _convert_to_netscape(self, cookies) -> str:
        """将 cookies 转换为 Netscape 格式"""
        lines = ["# Netscape HTTP Cookie File"]
        lines.append("# https://curl.haxx.se/rfc/cookie_spec.html")
        lines.append("# This is a generated file! Do not edit.")
        lines.append("")

        for cookie in cookies:
            domain = cookie.get('domain', '')
            flag = 'TRUE' if cookie.get('hostOnly', False) is False else 'FALSE'
            path = cookie.get('path', '/')
            secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
            expiration = str(int(cookie.get('expires', 0)))
            name = cookie.get('name', '')
            value = cookie.get('value', '')

            lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}")

        return '\n'.join(lines)

    def get_cookies(self) -> Optional[str]:
        """获取缓存的 cookies"""
        # 如果 cookies 超过 10 分钟，重新获取
        if self.cookies and self.last_fetch_time:
            import time
            elapsed = (datetime.now() - self.last_fetch_time).total_seconds()
            if elapsed < 600:  # 10 分钟内
                return self.cookies

        # 异步获取（需要在事件循环中调用）
        return None


async def get_fokies()resh_co -> Optional[str]:
    """获取新鲜的抖音 cookies"""
    fetcher = DouyinCookieFetcher()
    return await fetcher.fetch_cookies()


if __name__ == "__main__":
    # 测试
    asyncio.run(get_fresh_cookies())

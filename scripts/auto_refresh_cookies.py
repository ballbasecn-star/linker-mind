#!/usr/bin/env python3
"""
自动刷新抖音Cookies脚本

定时运行以保持Cookies新鲜
"""
import os
import sys
import json
import logging
import subprocess
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置
DOUYIN_API = os.environ.get('DOUYIN_API', 'http://117.72.207.52:8080')
CONFIG_PATH = '/root/Douyin_TikTok_Download_API/crawlers/douyin/web/config.yaml'
CHECK_INTERVAL = 3600 * 6  # 每6小时检查一次


def check_api_working():
    """检查API是否正常工作"""
    try:
        test_url = "https://v.douyin.com/jkwHntr5qxw/"
        response = requests.get(
            f"{DOUYIN_API}/api/hybrid/video_data",
            params={"url": test_url, "minimal": "false"},
            timeout=30
        )
        data = response.json()
        if data.get("code") == 200 and data.get("data"):
            logger.info("API工作正常")
            return True
        else:
            logger.warning(f"API返回异常: {data}")
            return False
    except Exception as e:
        logger.error(f"API检查失败: {e}")
        return False


def get_fresh_cookies_from_browser():
    """使用Playwright从浏览器获取新鲜Cookies"""
    try:
        from playwright.async_api import async_playwright
        import asyncio

        async def fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()

                # 访问抖音
                await page.goto('https://www.douyin.com/', wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(5)

                # 获取cookies
                cookies = await context.cookies()

                # 转换为字符串
                cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
                await browser.close()
                return cookie_str

        return asyncio.run(fetch())
    except Exception as e:
        logger.error(f"获取Cookies失败: {e}")
        return None


def update_config_cookies(cookie_str):
    """更新配置文件中的Cookies"""
    try:
        # 读取当前配置
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换Cookie行
        lines = content.split('\n')
        new_lines = []
        in_cookie = False

        for line in lines:
            if 'Cookie:' in line and 'TokenManager' not in line:
                # 找到Cookie行，替换
                indent = len(line) - len(line.lstrip())
                spaces = ' ' * indent
                new_lines.append(f"{spaces}Cookie: {cookie_str}")
                in_cookie = True
            else:
                new_lines.append(line)

        # 写回配置
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))

        logger.info("Cookies配置已更新")
        return True

    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        return False


def restart_service():
    """重启API服务"""
    try:
        # 杀掉旧进程
        subprocess.run("pkill -f 'python3 start.py'", shell=True)
        import time
        time.sleep(2)

        # 启动新进程
        subprocess.Popen(
            "cd /root/Douyin_TikTok_Download_API && nohup python3 start.py > douyin_api.log 2>&1 &",
            shell=True
        )
        logger.info("服务已重启")
        return True
    except Exception as e:
        logger.error(f"重启服务失败: {e}")
        return False


def main():
    logger.info("=" * 50)
    logger.info(f"开始检查Cookies有效性 - {datetime.now()}")

    # 检查API是否正常工作
    if check_api_working():
        logger.info("API正常工作，无需刷新Cookies")
        return

    logger.warning("API异常，尝试刷新Cookies...")

    # 获取新鲜Cookies
    cookie_str = get_fresh_cookies_from_browser()
    if not cookie_str:
        logger.error("无法获取新鲜Cookies")
        return

    # 更新配置
    if update_config_cookies(cookie_str):
        # 重启服务
        restart_service()

        # 等待服务启动
        import time
        time.sleep(5)

        # 验证
        if check_api_working():
            logger.info("✅ Cookies刷新成功！")
        else:
            logger.error("⚠️ 刷新后API仍异常，可能需要手动处理")


if __name__ == "__main__":
    main()

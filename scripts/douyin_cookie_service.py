#!/usr/bin/env python3
"""
抖音 Cookie 服务

使用 Playwright 无头浏览器获取抖音 cookies，提供 API 给本地调用
"""
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="抖音 Cookie 服务", version="1.0.0")

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 登录Cookies配置路径
LOGIN_COOKIES_FILE = os.environ.get('LOGIN_COOKIES_FILE', '/root/douyin_login_cookies.json')

# User-Agent 常量
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# 签名生成器（延迟初始化）
_signature_generator = None


def get_signature_generator():
    """获取签名生成器"""
    global _signature_generator
    if _signature_generator is None:
        try:
            from douyin_signature import get_douyin_signature
            _signature_generator = get_douyin_signature()
            logger.info("签名生成器初始化成功")
        except Exception as e:
            logger.warning(f"签名生成器初始化失败: {e}")
            _signature_generator = None
    return _signature_generator


class DouyinCookieFetcher:
    """抖音 Cookie 获取器"""

    def __init__(self):
        self._cookies = None
        self._last_fetch_time = None
        self._lock = False  # 防止并发请求

    async def fetch_cookies(self, video_url: Optional[str] = None) -> dict:
        """
        获取抖音 cookies

        Args:
            video_url: 可选的抖音视频链接

        Returns:
            包含 cookies 和视频信息的字典
        """
        if self._lock:
            return {
                "success": False,
                "error": "正在获取中，请稍后再试"
            }

        self._lock = True
        result = {
            "success": False,
            "cookies": None,
            "video_info": None,
            "error": None,
            "timestamp": datetime.now().isoformat()
        }

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # 启动浏览器
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu'
                    ]
                )

                # 创建上下文
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1512, 'height': 982},
                    locale='zh-CN'
                )

                page = await context.new_page()

                # 如果提供了视频 URL，直接访问
                if video_url:
                    logger.info(f"访问视频: {video_url}")
                    try:
                        await page.goto(video_url, wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(5)  # 等待JavaScript执行

                        # 获取页面URL（可能已被重定向）
                        final_url = page.url
                        logger.info(f"最终URL: {final_url}")

                        # 从URL中提取视频ID
                        import re
                        video_id = None
                        match = re.search(r'/video/(\d+)', final_url)
                        if match:
                            video_id = match.group(1)

                        logger.info(f"提取到视频ID: {video_id}")

                        # 尝试提取视频信息
                        if video_id:
                            video_info = await self._extract_from_page(page, video_id)
                            if video_info:
                                result["video_info"] = video_info
                                logger.info(f"成功提取视频信息: {video_info.get('title', 'N/A')[:30]}")

                    except Exception as e:
                        logger.warning(f"访问视频失败: {e}")

                # 访问抖音首页获取 cookies
                await page.goto('https://www.douyin.com/', wait_until='domcontentloaded', timeout=60000)
                await asyncio.sleep(5)

                # 获取 cookies
                cookies = await context.cookies()

                # 转换为 Netscape 格式
                cookie_str = self._convert_to_netscape(cookies)

                result["cookies"] = cookie_str
                result["success"] = True

                # 保存缓存
                self._cookies = cookie_str
                self._last_fetch_time = datetime.now()

                logger.info(f"成功获取 {len(cookies)} 个 cookies")

                await browser.close()

        except Exception as e:
            logger.error(f"获取 cookies 失败: {e}")
            result["error"] = str(e)

        finally:
            self._lock = False

        return result

    async def _extract_from_page(self, page, video_id: str) -> Optional[dict]:
        """从页面HTML中直接提取视频信息"""
        try:
            import re
            import json
            import urllib.parse

            content = await page.content()

            # 方法1：尝试从 RENDER_DATA 中提取
            render_data_pattern = r'<script id="RENDER_DATA"[^>]*>([^<]+)</script>'
            match = re.search(render_data_pattern, content)
            if match:
                try:
                    render_json = urllib.parse.unquote(match.group(1))
                    data = json.loads(render_json)

                    # 尝试多种数据结构
                    if 'app' in data:
                        app_data = data.get('app', {})

                        # 尝试从视频详情页提取
                        if 'video' in app_data:
                            video_data = app_data.get('video', {})
                            if video_data.get('awemeDetail'):
                                detail = video_data.get('awemeDetail', {})
                                return self._parse_aweme_detail(detail, video_id)

                        # 尝试从其他结构提取
                        if 'aweme' in app_data:
                            aweme = app_data.get('aweme', {})
                            if aweme.get('detail'):
                                return self._parse_aweme_detail(aweme.get('detail'), video_id)

                    logger.info("RENDER_DATA 结构不包含视频详情")
                except Exception as e:
                    logger.warning(f"解析RENDER_DATA失败: {e}")

            # 方法2：尝试从 __INITIAL_STATE__ 中提取
            initial_state_pattern = r'window\.__INITIAL_STATE__\s*=\s*([^;]+);'
            match = re.search(initial_state_pattern, content)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if 'video' in data:
                        return self._parse_aweme_detail(data.get('video', {}), video_id)
                except Exception as e:
                    logger.warning(f"解析INITIAL_STATE失败: {e}")

            # 方法3：尝试从JSON-LD中提取
            json_ld_pattern = r'<script type="application/ld\+json">([^<]+)</script>'
            match = re.search(json_ld_pattern, content)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if '@graph' in data:
                        for item in data.get('@graph', []):
                            if item.get('@type') == 'VideoObject':
                                return {
                                    "title": item.get('name', ''),
                                    "description": item.get('description', ''),
                                    "author": item.get('author', {}).get('name', '') if isinstance(item.get('author'), dict) else item.get('author', ''),
                                    "video_id": video_id,
                                    "url": item.get('url', ''),
                                    "cover_url": item.get('thumbnailUrl', [''])[0] if item.get('thumbnailUrl') else '',
                                }
                except Exception as e:
                    logger.warning(f"解析JSON-LD失败: {e}")

        except Exception as e:
            logger.warning(f"页面提取视频信息失败: {e}")

        return None

    def _parse_aweme_detail(self, detail: dict, video_id: str) -> dict:
        """解析awemeDetail格式的视频数据"""
        try:
            # 提取视频封面
            cover_url = ''
            if detail.get('video'):
                cover_data = detail['video'].get('cover', {})
                if cover_data.get('url_list'):
                    cover_url = cover_data['url_list'][0]
                elif cover_data.get('uri'):
                    cover_url = f"https://p3.douyinpic.com/img/{cover_data['uri']}~tplv-obj.image"

            # 提取统计数据
            stats = detail.get('statistics', {})

            return {
                "title": detail.get('desc', ''),
                "description": detail.get('desc', ''),
                "author": detail.get('author', {}).get('nickname', ''),
                "author_id": detail.get('author', {}).get('unique_id', ''),
                "video_id": video_id,
                "url": f"https://www.douyin.com/video/{video_id}",
                "cover_url": cover_url,
                "duration": detail.get('video', {}).get('duration', 0),
                "play_count": stats.get('play_count', 0),
                "like_count": stats.get('digg_count', 0),
                "comment_count": stats.get('comment_count', 0),
                "share_count": stats.get('share_count', 0),
                "collect_count": stats.get('collect_count', 0),
            }
        except Exception as e:
            logger.warning(f"解析awemeDetail失败: {e}")
            return None

    async def _fetch_video_info_from_api(self, video_id: str, page) -> Optional[dict]:
        """从抖音页面提取视频详细信息（不依赖API签名）"""
        try:
            # 方法1：直接从页面提取视频信息
            video_info = await self._extract_from_page(page, video_id)
            if video_info:
                logger.info("从页面提取到视频信息")
                return video_info

            # 方法2：尝试使用游客cookies调用API（可能失败）
            logger.info("页面提取失败，尝试API...")
            cookies = await page.context.cookies()
            cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

            import httpx
            import uuid

            # 使用备用API端点
            webid = str(uuid.uuid4())
            verify_fp = f"verify_{uuid.uuid4().hex[:16]}"

            api_url = (
                f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?"
                f"item_ids={video_id}"
                f"&device_platform=webapp&aid=6383&channel=channel_pc_web"
                f"&pc_client_type=1&version_code=170400&version_name=17.4.0"
                f"&cookie_enabled=true&screen_width=1512&screen_height=982"
                f"&browser_language=zh-CN&browser_platform=MacIntel"
                f"&browser_name=Chrome&browser_version=120.0.0.0"
                f"&os_name=Macintosh&os_version=10_15_7"
                f"&webid={webid}&verifyFp={verify_fp}&fp={verify_fp}"
            )

            # 尝试添加签名
            sig_gen = get_signature_generator()
            if sig_gen:
                try:
                    a_bogus = sig_gen.get_a_bogus(api_url, USER_AGENT)
                    ms_token = sig_gen.get_ms_token()
                    api_url = f"{api_url}&a_bogus={a_bogus}&msToken={ms_token}"
                except Exception as e:
                    logger.warning(f"生成签名失败: {e}")

            headers = {
                'User-Agent': USER_AGENT,
                'Cookie': cookie_str,
                'Referer': 'https://www.douyin.com/',
                'Accept': 'application/json',
            }

            response = httpx.get(api_url, headers=headers, timeout=15)
            logger.info(f"API响应状态: {response.status_code}")

            if response.status_code == 200 and response.text:
                data = response.json()
                logger.info(f"API返回数据: {data}")

                if data.get('item_list') and len(data['item_list']) > 0:
                    item = data['item_list'][0]

                    # 提取视频封面
                    cover_url = ''
                    if item.get('video'):
                        cover_data = item['video'].get('cover', {})
                        if cover_data.get('url_list'):
                            cover_url = cover_data['url_list'][0]
                        elif cover_data.get('uri'):
                            cover_url = f"https://p3.douyinpic.com/img/{cover_data['uri']}~tplv-obj.image"

                    # 提取统计数据
                    stats = item.get('statistics', {})

                    return {
                        "title": item.get('desc', ''),
                        "description": item.get('desc', ''),
                        "author": item.get('author', {}).get('nickname', ''),
                        "author_id": item.get('author', {}).get('unique_id', ''),
                        "video_id": video_id,
                        "url": f"https://www.douyin.com/video/{video_id}",
                        "cover_url": cover_url,
                        "duration": item.get('video', {}).get('duration', 0),
                        # 统计数据
                        "play_count": stats.get('play_count', 0),
                        "like_count": stats.get('digg_count', 0),
                        "comment_count": stats.get('comment_count', 0),
                        "share_count": stats.get('share_count', 0),
                        "collect_count": stats.get('collect_count', 0),
                    }
                else:
                    logger.warning(f"API返回空数据: {data}")
        except Exception as e:
            logger.error(f"API调用失败: {e}")

        return None

    def _convert_to_netscape(self, cookies) -> str:
        """将 cookies 转换为 Netscape 格式"""
        lines = ["# Netscape HTTP Cookie File"]
        lines.append("# https://curl.haxx.se/rfc/cookie_spec.html")
        lines.append("# This is a generated file! Do not edit.")
        lines.append("")

        for cookie in cookies:
            domain = cookie.get('domain', '')
            # 移除域名前的点
            if domain.startswith('.'):
                domain = domain[1:]

            flag = 'TRUE' if cookie.get('domain', '').startswith('.') else 'FALSE'
            path = cookie.get('path', '/')
            secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'

            # 处理过期时间
            expires = cookie.get('expires')
            if expires:
                expiration = str(int(expires))
            else:
                expiration = '0'

            name = cookie.get('name', '')
            value = cookie.get('value', '')

            lines.append(f".{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}")

        return '\n'.join(lines)


# 全局实例
fetcher = DouyinCookieFetcher()


# ========== API 端点 ==========

@app.get("/")
async def root():
    return {"service": "抖音 Cookie 服务", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


class CookieRequest(BaseModel):
    video_url: Optional[str] = None


@app.post("/api/douyin/cookies")
async def get_cookies(request: CookieRequest = None):
    """
    获取抖音 cookies

    请求体:
    {
        "video_url": "可选的抖音视频链接"
    }

    响应:
    {
        "success": true/false,
        "cookies": "Netscape 格式的 cookies",
        "video_info": {...},
        "error": "错误信息",
        "timestamp": "时间戳"
    }
    """
    video_url = request.video_url if request else None
    result = await fetcher.fetch_cookies(video_url)
    return result


@app.get("/api/douyin/cookies")
async def get_cookies_simple(video_url: Optional[str] = None):
    """GET 方式获取 cookies"""
    result = await fetcher.fetch_cookies(video_url)
    return result


@app.get("/api/douyin/status")
async def get_status():
    """获取服务状态"""
    return {
        "has_cookies": fetcher._cookies is not None,
        "last_fetch": fetcher._last_fetch_time.isoformat() if fetcher._last_fetch_time else None,
        "is_busy": fetcher._lock
    }


class VideoDownloadRequest(BaseModel):
    video_url: str
    quality: Optional[str] = "720p"


@app.post("/api/douyin/download")
async def download_video(request: VideoDownloadRequest):
    """
    下载抖音视频

    请求体:
    {
        "video_url": "抖音视频链接",
        "quality": "视频质量 (720p/1080p)"
    }

    响应:
    {
        "success": true/false,
        "video_path": "下载后的文件路径",
        "video_url": "视频播放地址",
        "title": "视频标题",
        "cover_url": "封面图",
        "error": "错误信息"
    }
    """
    try:
        # 先获取cookies
        cookies_result = await fetcher.fetch_cookies(request.video_url)
        if not cookies_result.get("success"):
            return {"success": False, "error": "获取cookies失败"}

        cookies = cookies_result.get("cookies", "")
        video_info = cookies_result.get("video_info", {})

        # 解析cookies
        cookie_str = _parse_cookies_for_api(cookies)

        # 获取视频ID
        video_id = video_info.get("video_id")
        if not video_id:
            # 从URL中提取
            import re
            match = re.search(r'/video/(\d+)', request.video_url)
            if match:
                video_id = match.group(1)

        if not video_id:
            return {"success": False, "error": "无法获取视频ID"}

        # 调用API获取视频信息 - 添加完整签名参数
        import uuid
        webid = str(uuid.uuid4())
        verify_fp = f"verify_{uuid.uuid4().hex[:16]}"

        api_url = (
            f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?"
            f"item_ids={video_id}"
            f"&device_platform=webapp"
            f"&aid=6383"
            f"&channel=channel_pc_web"
            f"&pc_client_type=1"
            f"&version_code=170400"
            f"&version_name=17.4.0"
            f"&cookie_enabled=true"
            f"&screen_width=1512"
            f"&screen_height=982"
            f"&browser_language=zh-CN"
            f"&browser_platform=MacIntel"
            f"&browser_name=Chrome"
            f"&browser_version=120.0.0.0"
            f"&os_name=Macintosh"
            f"&os_version=10_15_7"
            f"&webid={webid}"
            f"&verifyFp={verify_fp}"
            f"&fp={verify_fp}"
        )

        # 生成签名
        sig_gen = get_signature_generator()
        if sig_gen:
            try:
                a_bogus = sig_gen.get_a_bogus(api_url, USER_AGENT)
                ms_token = sig_gen.get_ms_token()
                api_url = f"{api_url}&a_bogus={a_bogus}&msToken={ms_token}"
                logger.info(f"添加签名后的URL: {api_url[:100]}...")
            except Exception as e:
                logger.warning(f"生成签名失败: {e}")

        headers = {
            'User-Agent': USER_AGENT,
            'Cookie': cookie_str,
            'Referer': 'https://www.douyin.com/',
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers, timeout=30)
            logger.info(f"API响应状态: {response.status_code}")

            if response.status_code != 200:
                return {"success": False, "error": f"API请求失败: {response.status_code}"}

            # 检查响应内容
            if not response.text:
                return {"success": False, "error": "API返回空响应", "debug": {"status_code": response.status_code, "headers": dict(response.headers)}}

            # 记录原始响应用于调试
            logger.info(f"API原始响应长度: {len(response.text)}")

            try:
                data = response.json()
            except Exception as e:
                logger.error(f"JSON解析失败: {e}, 响应内容: {response.text[:500]}")
                return {"success": False, "error": f"JSON解析失败: {e}"}

            if not data.get("item_list"):
                logger.warning(f"API返回无item_list: {data}")
                return {"success": False, "error": "无法获取视频信息"}

            item = data["item_list"][0]
            title = item.get("desc", "无标题")
            video_data = item.get("video", {})

            # 优先使用play_addr中的url_list
            video_play_url = None
            play_addr = video_data.get("play_addr", {})
            if play_addr.get("url_list"):
                video_play_url = play_addr["url_list"][0]
                logger.info(f"使用URL list: {video_play_url[:50]}...")

            # 如果没有url_list，尝试使用video_id
            if not video_play_url:
                video_uri = play_addr.get("uri")
                if video_uri:
                    quality = request.quality or "720p"
                    video_play_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_uri}&ratio={quality}&line=0"
                    logger.info(f"使用video_id: {video_play_url[:50]}...")

            if not video_play_url:
                return {"success": False, "error": "无法获取视频地址"}

            # 下载视频
            video_dir = "/tmp/douyin_videos"
            os.makedirs(video_dir, exist_ok=True)

            # 清理文件名
            import re as re_module
            clean_title = re_module.sub(r'[\/\\\:\*\?\"\<\>\|\.]', '_', title)[:50]
            filename = f"{clean_title}_{video_id}.mp4"
            filepath = os.path.join(video_dir, filename)

            # 下载视频文件
            video_headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'https://www.douyin.com/',
            }

            async with httpx.AsyncClient() as video_client:
                video_response = await video_client.get(video_play_url, headers=video_headers, timeout=120)
                if video_response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(video_response.content)

                    # 获取封面
                    cover_url = ""
                    cover_data = video_data.get("cover", {})
                    if cover_data.get("url_list"):
                        cover_url = cover_data["url_list"][0]

                    return {
                        "success": True,
                        "video_path": filepath,
                        "video_url": video_play_url,
                        "title": title,
                        "cover_url": cover_url,
                        "video_id": video_id,
                        "file_size": os.path.getsize(filepath)
                    }
                else:
                    return {"success": False, "error": f"视频下载失败: {video_response.status_code}"}

    except Exception as e:
        logger.error(f"视频下载失败: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/douyin/download")
async def download_video_get(video_url: str, quality: Optional[str] = "720p"):
    """GET方式下载视频"""
    return await download_video(VideoDownloadRequest(video_url=video_url, quality=quality))


class VideoAnalyzeRequest(BaseModel):
    video_url: str
    enable_transcription: bool = True
    enable_screenshots: bool = True


@app.post("/api/douyin/analyze")
async def analyze_video(request: VideoAnalyzeRequest):
    """
    深度分析抖音视频

    请求体:
    {
        "video_url": "抖音视频链接",
        "enable_transcription": true,  // 启用语音转文字
        "enable_screenshots": true     // 启用截图
    }

    响应:
    {
        "success": true/false,
        "video_path": "视频文件路径",
        "transcript": "转录文本",
        "screenshots": ["截图路径列表"],
        "analysis": {...},
        "error": "错误信息"
    }
    """
    try:
        # 先下载视频
        download_result = await download_video(
            VideoDownloadRequest(video_url=request.video_url, quality="720p")
        )

        if not download_result.get("success"):
            return {"success": False, "error": f"视频下载失败: {download_result.get('error')}"}

        video_path = download_result.get("video_path")
        title = download_result.get("title", "")

        result = {
            "success": True,
            "video_path": video_path,
            "title": title,
            "transcript": None,
            "screenshots": [],
            "analysis": {}
        }

        # 截图
        if request.enable_screenshots:
            try:
                import subprocess
                screenshot_dir = "/tmp/douyin_screenshots"
                os.makedirs(screenshot_dir, exist_ok=True)

                # 使用ffmpeg截图（每10秒截取一帧）
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                screenshot_pattern = os.path.join(screenshot_dir, f"{base_name}_%03d.jpg")

                # 获取视频时长
                cmd = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", video_path
                ]
                duration = float(subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip())

                # 每10秒截取一帧，最多10张
                num_screenshots = min(10, int(duration // 10) + 1)

                if num_screenshots > 0:
                    cmd = [
                        "ffmpeg", "-i", video_path,
                        "-vf", f"fps=1/10",
                        "-frames:v", str(num_screenshots),
                        "-q:v", "2",
                        screenshot_pattern
                    ]
                    subprocess.run(cmd, capture_output=True, timeout=60)

                    # 收集截图文件
                    screenshots = []
                    for f in os.listdir(screenshot_dir):
                        if f.startswith(base_name) and f.endswith('.jpg'):
                            screenshots.append(os.path.join(screenshot_dir, f))

                    result["screenshots"] = screenshots
                    logger.info(f"截图完成: {len(screenshots)} 张")

            except Exception as e:
                logger.warning(f"截图失败: {e}")
                result["screenshots_error"] = str(e)

        # 语音转文字
        if request.enable_transcription:
            try:
                import subprocess

                # 提取音频
                audio_path = video_path.replace(".mp4", ".mp3")
                cmd = [
                    "ffmpeg", "-i", video_path,
                    "-vn", "-acodec", "libmp3lame",
                    "-q:a", "2",
                    audio_path
                ]
                subprocess.run(cmd, capture_output=True, timeout=120)

                if os.path.exists(audio_path):
                    # 尝试使用whisper进行转录（如果安装了whisper）
                    try:
                        import whisper
                        model = whisper.load_model("base")
                        result_whisper = model.transcribe(audio_path)
                        result["transcript"] = result_whisper.get("text", "")
                        logger.info("Whisper转录完成")
                    except ImportError:
                        result["transcript"] = "[Whisper未安装，无法转录]"
                        result["transcript_error"] = "whisper模块未安装"
                    except Exception as e:
                        result["transcript"] = f"[转录失败: {e}]"
                        result["transcript_error"] = str(e)

                    # 清理音频文件
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                else:
                    result["transcript_error"] = "音频提取失败"

            except Exception as e:
                logger.warning(f"语音转文字失败: {e}")
                result["transcript_error"] = str(e)

        return result

    except Exception as e:
        logger.error(f"视频分析失败: {e}")
        return {"success": False, "error": str(e)}


def _parse_cookies_for_api(cookies_str: str) -> str:
    """将Netscape格式cookies转换为API请求格式"""
    if not cookies_str:
        return ""

    if cookies_str.strip().startswith('# Netscape'):
        cookies_list = []
        for line in cookies_str.strip().split('\n'):
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) >= 7:
                name = parts[5].strip()
                value = parts[6].strip()
                if name and value:
                    cookies_list.append(f"{name}={value}")
        return '; '.join(cookies_list)

    return cookies_str


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

#!/usr/bin/env python3
"""
抖音远程提取服务客户端

调用服务器上的抖音服务获取视频信息
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)

# Cookies缓存配置
CACHE_DIR = os.environ.get('CACHE_DIR', './cache')
COOKIES_CACHE_FILE = os.path.join(CACHE_DIR, 'douyin_cookies_cache.json')
COOKIES_CACHE_HOURS = int(os.environ.get('DOUYIN_COOKIES_CACHE_HOURS', '6'))  # 默认6小时有效

# 服务器地址配置 (Douyin_TikTok_Download_API)
DOUYIN_SERVICE_URL = os.environ.get(
    "DOUYIN_SERVICE_URL",
    "http://117.72.207.52:8080"
)


class DouyinRemoteClient:
    """远程抖音服务客户端"""

    def __init__(self, service_url: str = None):
        self.service_url = service_url or DOUYIN_SERVICE_URL
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    def get_cached_cookies(self) -> Optional[Dict[str, Any]]:
        """获取缓存的cookies"""
        if not os.path.exists(COOKIES_CACHE_FILE):
            logger.info("Cookies缓存不存在")
            return None

        try:
            with open(COOKIES_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)

            # 检查是否过期
            cached_time = datetime.fromisoformat(cache.get('timestamp', '2000-01-01'))
            if datetime.now() - cached_time > timedelta(hours=COOKIES_CACHE_HOURS):
                logger.info(f"Cookies缓存已过期（超过{COOKIES_CACHE_HOURS}小时）")
                return None

            logger.info(f"使用缓存的Cookies（缓存时间: {cache.get('timestamp')}）")
            return {
                "cookies": cache.get('cookies'),
                "video_info": cache.get('video_info', {}),
                "cached": True
            }
        except Exception as e:
            logger.warning(f"读取Cookies缓存失败: {e}")
            return None

    def save_cookies_cache(self, cookies: str, video_info: Dict = None):
        """保存cookies到缓存"""
        try:
            cache = {
                'cookies': cookies,
                'video_info': video_info or {},
                'timestamp': datetime.now().isoformat()
            }
            with open(COOKIES_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            logger.info("Cookies已保存到缓存")
        except Exception as e:
            logger.warning(f"保存Cookies缓存失败: {e}")

    def clear_cookies_cache(self):
        """清除cookies缓存"""
        try:
            if os.path.exists(COOKIES_CACHE_FILE):
                os.remove(COOKIES_CACHE_FILE)
                logger.info("Cookies缓存已清除")
        except Exception as e:
            logger.warning(f"清除Cookies缓存失败: {e}")

    def get_video_info(self, video_url: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取抖音视频信息

        Args:
            video_url: 抖音视频链接
            use_cache: 是否使用缓存（默认True）

        Returns:
            包含视频信息的字典，失败返回 None
        """
        # 尝试使用缓存
        if use_cache:
            cached = self.get_cached_cookies()
            if cached:
                logger.info("使用缓存的cookies，不调用远程服务")
                return {
                    "success": True,
                    "video_info": cached.get('video_info', {}),
                    "cookies": cached.get('cookies'),
                    "url": video_url,
                    "cached": True
                }

        # 调用远程服务
        try:
            response = requests.get(
                f"{self.service_url}/api/douyin/cookies",
                params={"video_url": video_url},
                timeout=180  # 3分钟超时
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    video_info = data.get("video_info", {})
                    cookies = data.get("cookies", "")

                    # 保存到缓存
                    self.save_cookies_cache(cookies, video_info)

                    logger.info("成功从远程服务获取视频信息")
                    return {
                        "success": True,
                        "video_info": video_info,
                        "cookies": cookies,
                        "url": video_url,
                        "cached": False
                    }
                else:
                    logger.warning(f"获取失败: {data.get('error')}")
            else:
                logger.warning(f"API 返回错误: {response.status_code}")

        except requests.exceptions.Timeout:
            logger.error("请求远程服务超时")
        except requests.exceptions.ConnectionError:
            logger.error(f"无法连接到远程服务: {self.service_url}")
        except Exception as e:
            logger.error(f"获取视频信息异常: {e}")

        return None

    # ==================== 新架构方法 ====================

    def get_cookies(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        从服务器获取登录Cookies（新架构）

        Args:
            force_refresh: 强制刷新缓存

        Returns:
            包含cookies的字典
        """
        if not force_refresh:
            cached = self.get_cached_cookies()
            if cached:
                return {
                    "success": True,
                    "cookies": cached.get('cookies'),
                    "cached": True
                }

        # 调用远程服务获取Cookies
        try:
            # 使用 Douyin_TikTok_Download_API 的视频数据API
            # 这个API会返回视频信息，同时也刷新了cookies
            test_url = "https://v.douyin.com/jkwHntr5qxw/"
            response = requests.get(
                f"{self.service_url}/api/hybrid/video_data",
                params={"url": test_url, "minimal": "false"},
                timeout=180
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and data.get("data"):
                    # 从响应中提取cookies（如果有）
                    # Douyin_TikTok_Download_API 会在请求时自动使用配置的cookies
                    # 我们只需确认API可用即可
                    logger.info("API连接成功，Cookies有效")
                    return {
                        "success": True,
                        "cookies": "from_server",  # Cookies在服务器端
                        "cached": False,
                        "api_available": True
                    }
                else:
                    logger.warning(f"API返回异常: {data}")
                    return {
                        "success": False,
                        "error": data.get("message", "Unknown error"),
                        "api_available": False
                    }
        except Exception as e:
            logger.error(f"获取Cookies失败: {e}")
            return {"success": False, "error": str(e)}

    def get_video_info(self, video_url: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取抖音视频信息（新架构 - 调用服务器API）

        Args:
            video_url: 抖音视频链接
            use_cache: 是否使用缓存

        Returns:
            包含视频信息的字典
        """
        # 先获取/确认Cookies有效
        cookies_result = self.get_cookies()
        if not cookies_result or not cookies_result.get("success"):
            return {
                "success": False,
                "error": "Cookies不可用"
            }

        # 调用服务器API获取视频信息
        try:
            response = requests.get(
                f"{self.service_url}/api/hybrid/video_data",
                params={"url": video_url, "minimal": "false"},
                timeout=180
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("code") == 200 and data.get("data"):
                    video_data = data["data"]

                    # 解析视频信息
                    video_info = self._parse_video_data(video_data)

                    logger.info(f"成功获取视频信息: {video_info.get('title', 'N/A')[:30]}...")
                    return {
                        "success": True,
                        "video_info": video_info,
                        "url": video_url,
                        "cached": False
                    }
                else:
                    logger.warning(f"获取视频信息失败: {data.get('message')}")

        except Exception as e:
            logger.error(f"获取视频信息异常: {e}")

        return None

    def _parse_video_data(self, data: Dict) -> Dict:
        """解析服务器返回的视频数据"""
        video_info = {}

        try:
            # 基础信息 - 注意：id可能在不同位置
            stats = data.get("statistics", {}) or {}
            video_info["video_id"] = data.get("id") or stats.get("aweme_id", "")
            video_info["title"] = data.get("desc", "") or data.get("title", "")  # desc是标题
            video_info["description"] = data.get("desc", "")  # 描述和标题相同
            video_info["url"] = f"https://www.douyin.com/video/{video_info['video_id']}"

            # 作者信息
            author = data.get("author", {}) or {}
            video_info["author"] = author.get("nickname", "")
            video_info["author_id"] = author.get("unique_id", "") or author.get("short_id", "")
            video_info["author_avatar"] = None
            avatar = author.get("avatar_thumb", {})
            if avatar and isinstance(avatar, dict):
                url_list = avatar.get("url_list", [])
                if url_list:
                    video_info["author_avatar"] = url_list[0]

            # 统计数据 - 有些字段可能为0或None
            video_info["play_count"] = stats.get("play_count", 0) or stats.get("play", 0) or 0
            video_info["like_count"] = stats.get("digg_count", 0) or stats.get("like", 0) or 0
            video_info["comment_count"] = stats.get("comment_count", 0) or 0
            video_info["share_count"] = stats.get("share_count", 0) or 0
            video_info["collect_count"] = stats.get("collect_count", 0) or 0

            # 封面 - 尝试多个位置
            cover = data.get("cover", {})
            if not cover:
                cover = data.get("video", {}).get("cover", {})
            if cover and isinstance(cover, dict):
                url_list = cover.get("url_list", [])
                if url_list:
                    video_info["cover_url"] = url_list[0]
                else:
                    # 可能是uri格式
                    uri = cover.get("uri", "")
                    if uri:
                        video_info["cover_url"] = f"https://p3.douyinpic.com/img/{uri}~tplv-obj.image"
            else:
                video_info["cover_url"] = None

            # 视频 duration
            video_info["duration"] = data.get("duration", 0) or data.get("video", {}).get("duration", 0) or 0

            # 发布时间
            video_info["create_time"] = data.get("create_time", 0)

        except Exception as e:
            logger.error(f"解析视频数据失败: {e}")

        return video_info

    def get_download_url(self, video_url: str, with_watermark: bool = False) -> Optional[Dict[str, Any]]:
        """
        获取视频下载链接（新架构）

        注意：这个API直接返回视频流，不是JSON响应。
        我们通过检查Content-Type来判断是否成功。

        Args:
            video_url: 抖音视频链接
            with_watermark: 是否带水印

        Returns:
            包含下载链接的字典（成功时video_url为空，表示直接返回流）
        """
        # 先获取/确认Cookies有效
        cookies_result = self.get_cookies()
        if not cookies_result or not cookies_result.get("success"):
            return {
                "success": False,
                "error": "Cookies不可用"
            }

        try:
            response = requests.get(
                f"{self.service_url}/api/download",
                params={
                    "url": video_url,
                    "with_watermark": "true" if with_watermark else "false"
                },
                timeout=180,
                stream=True  # 流式接收
            )

            # 检查响应是否是视频（不是错误JSON）
            content_type = response.headers.get('Content-Type', '')

            if response.status_code == 200:
                # 如果是视频流，直接返回成功
                if 'video' in content_type or 'application/octet-stream' in content_type:
                    # 获取Content-Length
                    content_length = response.headers.get('Content-Length', 0)

                    logger.info(f"获取到视频流，长度: {content_length}")
                    return {
                        "success": True,
                        "video_url": "",  # 流直接在这里
                        "stream": response.content,  # 视频内容
                        "content_length": int(content_length) if content_length else 0,
                        "with_watermark": with_watermark
                    }
                else:
                    # 尝试解析JSON错误
                    try:
                        data = response.json()
                        logger.warning(f"获取下载链接失败: {data}")
                        return {"success": False, "error": data.get("message", "Unknown error")}
                    except:
                        logger.warning(f"未知响应类型: {content_type}")
                        return {"success": False, "error": f"Unknown response type: {content_type}"}

        except Exception as e:
            logger.error(f"获取下载链接异常: {e}")

        return None

    def download_video(self, video_url: str, output_path: str = None, with_watermark: bool = False) -> Optional[str]:
        """
        下载视频到本地（新架构）

        Args:
            video_url: 抖音视频链接
            output_path: 保存路径，默认临时文件
            with_watermark: 是否带水印

        Returns:
            下载后的文件路径
        """
        import tempfile

        # 获取下载结果
        download_result = self.get_download_url(video_url, with_watermark)
        if not download_result or not download_result.get("success"):
            logger.error("无法获取下载链接")
            return None

        # 确定保存路径
        if not output_path:
            output_path = os.path.join(tempfile.gettempdir(), f"douyin_{int(datetime.now().timestamp())}.mp4")

        try:
            # 方式1：直接返回了视频流
            if download_result.get("stream"):
                video_content = download_result["stream"]
                with open(output_path, 'wb') as f:
                    f.write(video_content)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    logger.info(f"视频下载成功(流): {output_path}")
                    return output_path

            # 方式2：返回了URL，需要再下载
            video_url_direct = download_result.get("video_url")
            if video_url_direct:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Referer': 'https://www.douyin.com/'
                }

                response = requests.get(video_url_direct, headers=headers, stream=True, timeout=300)

                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        logger.info(f"视频下载成功(URL): {output_path}")
                        return output_path

        except Exception as e:
            logger.error(f"视频下载失败: {e}")

        return None

    # ==================== 兼容旧版本 ====================

    def get_cookies_only(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        仅获取cookies（不获取视频信息）

        Args:
            force_refresh: 强制刷新缓存

        Returns:
            包含cookies的字典
        """
        if not force_refresh:
            cached = self.get_cached_cookies()
            if cached:
                return {
                    "success": True,
                    "cookies": cached.get('cookies'),
                    "cached": True
                }

        # 调用远程服务
        try:
            response = requests.get(
                f"{self.service_url}/api/douyin/cookies",
                timeout=180
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    cookies = data.get("cookies", "")
                    self.save_cookies_cache(cookies)
                    return {
                        "success": True,
                        "cookies": cookies,
                        "cached": False
                    }
        except Exception as e:
            logger.error(f"获取cookies失败: {e}")

        return None

    def _parse_cookies_for_api(self, cookies_str: str) -> str:
        """
        将Netscape格式的cookies转换为简单的key=value格式

        Args:
            cookies_str: Netscape格式的cookies字符串

        Returns:
            简单的cookie字符串 "key1=value1; key2=value2"
        """
        if not cookies_str:
            return ""

        # 检查是否是Netscape格式
        if cookies_str.strip().startswith('# Netscape'):
            cookies_list = []
            for line in cookies_str.strip().split('\n'):
                # 跳过注释行和空行
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                # Netscape格式: domain, flag, path, secure, expiration, name, value
                if len(parts) >= 7:
                    name = parts[5].strip()
                    value = parts[6].strip()
                    # 跳过空名称
                    if name and value:
                        cookies_list.append(f"{name}={value}")

            # 转换为字符串
            return '; '.join(cookies_list)

        # 已经是简单格式
        return cookies_str

    def fetch_video_info_from_api(self, video_id: str, cookies: str = None) -> Optional[Dict[str, Any]]:
        """
        使用cookies直接调用抖音API获取视频详细信息

        Args:
            video_id: 视频ID
            cookies: cookies字符串，如果不提供则使用缓存的cookies

        Returns:
            视频详细信息字典
        """
        if not cookies:
            cached = self.get_cached_cookies()
            if cached:
                cookies = cached.get('cookies')
            else:
                logger.warning("没有可用的cookies")
                return None

        # 转换cookies格式
        cookie_str = self._parse_cookies_for_api(cookies)
        if not cookie_str:
            logger.warning("Cookies解析失败")
            return None

        try:
            import httpx

            # 抖音视频信息API
            api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cookie': cookie_str,
                'Referer': 'https://www.douyin.com/',
                'Origin': 'https://www.douyin.com',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
            }

            response = httpx.get(api_url, headers=headers, timeout=15)
            logger.info(f"API响应状态: {response.status_code}")

            if response.status_code == 200 and response.text:
                data = response.json()

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

                    video_info = {
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

                    logger.info(f"成功从API获取视频信息: {video_info.get('title', 'N/A')[:30]}...")
                    return video_info
                else:
                    logger.warning(f"API返回空数据: {data}")

        except Exception as e:
            logger.error(f"调用抖音API失败: {e}")

        return None

    def get_status(self) -> Dict[str, Any]:
        """获取远程服务状态"""
        status = {"remote_service": "unknown", "cache": {}}

        # 获取远程服务状态
        try:
            response = requests.get(
                f"{self.service_url}/api/douyin/status",
                timeout=10
            )
            if response.status_code == 200:
                status["remote_service"] = response.json()
        except Exception as e:
            status["remote_service"] = {"error": str(e)}

        # 获取缓存状态
        cached = self.get_cached_cookies()
        if cached:
            status["cache"] = {
                "exists": True,
                "cached": True,
                "video_info": cached.get('video_info', {})
            }
        else:
            status["cache"] = {"exists": False}

        return status

    def download_video_remote(self, video_url: str, quality: str = "720p") -> Optional[Dict[str, Any]]:
        """
        调用远程API下载视频

        Args:
            video_url: 抖音视频链接
            quality: 视频质量

        Returns:
            下载结果字典
        """
        try:
            response = requests.get(
                f"{self.service_url}/api/douyin/download",
                params={"video_url": video_url, "quality": quality},
                timeout=300  # 5分钟超时
            )

            if response.status_code == 200:
                data = response.json()
                return data
            else:
                logger.warning(f"远程下载失败: {response.status_code}")

        except Exception as e:
            logger.error(f"远程视频下载异常: {e}")

        return None

    def analyze_video_remote(
        self,
        video_url: str,
        enable_transcription: bool = True,
        enable_screenshots: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        调用远程API深度分析视频

        Args:
            video_url: 抖音视频链接
            enable_transcription: 启用语音转文字
            enable_screenshots: 启用截图

        Returns:
            分析结果字典
        """
        try:
            response = requests.post(
                f"{self.service_url}/api/douyin/analyze",
                json={
                    "video_url": video_url,
                    "enable_transcription": enable_transcription,
                    "enable_screenshots": enable_screenshots
                },
                timeout=600  # 10分钟超时
            )

            if response.status_code == 200:
                data = response.json()
                return data
            else:
                logger.warning(f"远程分析失败: {response.status_code}")

        except Exception as e:
            logger.error(f"远程视频分析异常: {e}")

        return None


# 全局客户端
_remote_client = None


def get_douyin_remote_client() -> DouyinRemoteClient:
    """获取远程抖音客户端单例"""
    global _remote_client
    if _remote_client is None:
        _remote_client = DouyinRemoteClient()
    return _remote_client


# 兼容旧版本别名
def get_remote_cookie_client() -> DouyinRemoteClient:
    """获取远程抖音客户端（兼容旧版本）"""
    return get_douyin_remote_client()


if __name__ == "__main__":
    # 测试
    client = DouyinRemoteClient()

    print("获取服务状态...")
    status = client.get_status()
    print(f"状态: {status}")

    print("\n获取视频信息...")
    result = client.get_video_info("https://v.douyin.com/jkwHntr5qxw/")
    if result:
        print(f"成功: {result.get('success')}")
        print(f"视频信息: {result.get('video_info')}")
    else:
        print("获取失败")

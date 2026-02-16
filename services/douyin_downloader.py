#!/usr/bin/env python3
# coding=utf-8
"""
抖音视频下载器 - 支持 Cookie 认证

基于 ikool-cn/python-video-downloader-douyin 项目
"""
import requests
import re
import os
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class DouYinDownloader:
    """抖音视频下载器"""

    def __init__(self, cookies: Optional[str] = None):
        # 默认 headers
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.douyin.com/',
        }

        # 设置 cookies
        self.cookie_string = cookies
        if cookies:
            # 解析 cookies 并格式化为请求头
            cookies_dict = self._parse_cookies(cookies)
            cookie_header = '; '.join([f'{k}={v}' for k, v in cookies_dict.items()])
            self.headers['cookie'] = cookie_header

        self.share_txt = None
        self.share_link = None
        self.redirect_url = None
        self.item_id = None
        self.title = None
        self.video_id = None
        self.video_url = None
        self.cover_url = None

    def _parse_cookies(self, cookies_str: str) -> Dict[str, str]:
        """
        解析 cookie 字符串为字典

        支持两种格式：
        1. 简单格式: key1=value1; key2=value2
        2. Netscape 格式: # Netscape HTTP Cookie File...
        """
        cookies_dict = {}

        # 检查是否是 Netscape 格式
        if cookies_str.strip().startswith('# Netscape'):
            # 解析 Netscape 格式的 cookie 文件
            for line in cookies_str.strip().split('\n'):
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    # 格式: domain, flag, path, secure, expiration, name, value
                    name = parts[5]
                    value = parts[6]
                    cookies_dict[name] = value
        else:
            # 解析简单格式
            for item in cookies_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies_dict[key.strip()] = value.strip()

        return cookies_dict

    def parse(self, share_txt):
        """
        解析分享链接

        Args:
            share_txt: 包含抖音链接的文本（如：xxx https://v.douyin.com/xxx 复制此链接...）

        Returns:
            self
        """
        self.share_txt = share_txt
        try:
            self._parse_share_link()
            self._get_redirect_url()
            self._get_item_id()
            self._get_video_info()
            logger.info(f"解析成功: {self.title}")
            return self
        except Exception as e:
            logger.error(f"解析失败: {e}")
            raise

    def get_video_url(self):
        """获取无水印视频链接"""
        return self.video_url

    def get_title(self):
        """获取视频标题"""
        return self.title

    def get_cover_url(self):
        """获取视频封面图链接"""
        return self.cover_url

    def _parse_share_link(self):
        """从分享文本中提取抖音链接"""
        match = re.findall(r'(https://v\.douyin\.com/[\w-]+)', self.share_txt)
        if match:
            # 确保获取完整链接（去除末尾的 /）
            link = match[0].rstrip('/')
            logger.info(f"提取到分享链接: {link}")
            self.share_link = link
            return self
        raise Exception("无法从文本中提取抖音链接")

    def _get_redirect_url(self):
        """获取重定向后的真实URL"""
        resp = requests.get(self.share_link, headers=self.headers, allow_redirects=True, timeout=10)
        if resp and resp.status_code == 200:
            logger.info(f"重定向URL: {resp.url}")
            self.redirect_url = resp.url
            return self
        raise Exception("获取重定向URL失败")

    def _get_item_id(self):
        """从URL中提取视频ID"""
        # 匹配 video/xxxxx
        match = re.search(r'/video/(\d+)', self.redirect_url)
        if match:
            self.item_id = match.group(1)
            logger.info(f"视频ID: {self.item_id}")
            return self
        raise Exception("无法提取视频ID")

    def _get_video_info(self):
        """获取视频信息（标题、URL、封面）"""
        # 尝试新版 API
        url = f'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={self.item_id}'

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get('item_list'):
                    item = data['item_list'][0]
                    self.title = item.get('desc', '无标题')
                    video_info = item.get('video', {})

                    # 获取视频 URI
                    self.video_id = video_info.get('play_addr', {}).get('uri')
                    if self.video_id:
                        # 构建无水印视频 URL
                        self.video_url = f'https://aweme.snssdk.com/aweme/v1/play/?video_id={self.video_id}&ratio=720p&line=0'

                    # 获取封面图
                    cover = video_info.get('cover', {})
                    if isinstance(cover, dict):
                        url_list = cover.get('url_list', [])
                        if url_list:
                            self.cover_url = url_list[0].get('url', '')
                    elif isinstance(cover, str):
                        self.cover_url = cover

                    logger.info(f"标题: {self.title}, 视频URL: {'已获取' if self.video_url else '未获取'}, 封面: {'已获取' if self.cover_url else '未获取'}")
                    return self
        except Exception as e:
            logger.warning(f"API 请求失败: {e}")

        raise Exception("无法获取视频信息")

    def download_video(self, path):
        """
        下载视频到指定目录

        Args:
            path: 保存目录路径
        """
        if not self.video_url:
            raise Exception("没有可下载的视频URL")

        resp = requests.get(url=self.video_url, headers=self.headers)
        if resp and resp.status_code == 200:
            save_path = os.path.join(os.getcwd(), path)
            if not os.path.exists(save_path):
                os.makedirs(save_path)

            # 清理文件名中的非法字符
            remove_chars = r"[\/\\\:\*\?\"\<\>\|]"
            new_title = re.sub(remove_chars, "_", self.title or "video")
            filename = f'{new_title}.mp4'

            full_path = os.path.join(save_path, filename)
            with open(full_path, 'wb') as f:
                f.write(resp.content)
            logger.info(f"视频已保存: {full_path}")
            return full_path

        raise Exception("视频下载失败")


def get_douyin_info(url_or_text: str, cookies: Optional[str] = None) -> Dict:
    """
    便捷函数：获取抖音视频信息

    Args:
        url_or_text: 抖音链接或包含链接的文本
        cookies: 可选的 Cookie 字符串

    Returns:
        dict: 包含 title, video_url, cover_url, success, error
    """
    try:
        downloader = DouYinDownloader(cookies=cookies)
        downloader.parse(url_or_text)
        return {
            'success': True,
            'title': downloader.get_title(),
            'video_url': downloader.get_video_url(),
            'cover_url': downloader.get_cover_url(),
            'item_id': downloader.item_id
        }
    except Exception as e:
        logger.error(f"获取抖音信息失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    # 测试（需要配置 cookies）
    import sys
    sys.path.insert(0, '/Users/qiuhaizhang/project/linker/linker-mind')

    from services.settings_service import get_settings_service

    settings = get_settings_service()
    cookies = settings.get_douyin_cookies_string()

    test_text = "7.97 d@N.JI 03/21 BGV:/ 拒绝盲目跟风，聊聊我个人的 AI 工作台 # PPT动画 # AI工作流 # 动画视频 # 人工智能 # AI提效  https://v.douyin.com/myYQ-hYayoY/ 复制此链接，打开Dou音搜索，直接观看视频！"

    result = get_douyin_info(test_text, cookies)
    print(result)

#!/usr/bin/env python3
"""
抖音签名生成模块

使用 py_mini_racer 调用 JS 代码生成 x_bogus 和 a_bogus 签名
"""
import os
import urllib.parse
import logging
import random
import time
import json
import re
import requests

logger = logging.getLogger(__name__)

# 尝试导入 py_mini_racer
try:
    from py_mini_racer import MiniRacer
    MINIRACER_AVAILABLE = True
except ImportError:
    logger.warning("py_mini_racer 未安装，将使用模拟签名")
    MINIRACER_AVAILABLE = False

# JS文件路径
JS_DIR = os.environ.get('JS_DIR', '/root/douyin_sig')
X_BOGUS_JS_PATH = os.path.join(JS_DIR, 'x_bogus.js')
A_BOGUS_JS_PATH = os.path.join(JS_DIR, 'a_bogus.js')


class DouyinSignature:
    """抖音签名生成器"""

    def __init__(self):
        self._x_bogus_ctx = None
        self._a_bogus_ctx = None
        self._init_js_context()

    def _init_js_context(self):
        """初始化JS上下文"""
        if not MINIRACER_AVAILABLE:
            logger.warning("py_mini_racer 不可用")
            return

        try:
            # 加载 x_bogus.js
            if os.path.exists(X_BOGUS_JS_PATH):
                with open(X_BOGUS_JS_PATH, 'r', encoding='utf-8') as f:
                    x_bogus_js_code = f.read()
                self._x_bogus_ctx = MiniRacer()
                self._x_bogus_ctx.eval(x_bogus_js_code)
                logger.info("x_bogus JS 加载成功")
            else:
                logger.warning(f"x_bogus JS 文件不存在: {X_BOGUS_JS_PATH}")

            # 加载 a_bogus.js
            if os.path.exists(A_BOGUS_JS_PATH):
                with open(A_BOGUS_JS_PATH, 'r', encoding='utf-8') as f:
                    a_bogus_js_code = f.read()
                self._a_bogus_ctx = MiniRacer()
                self._a_bogus_ctx.eval(a_bogus_js_code)
                logger.info("a_bogus JS 加载成功")
            else:
                logger.warning(f"a_bogus JS 文件不存在: {A_BOGUS_JS_PATH}")

        except Exception as e:
            logger.error(f"初始化JS上下文失败: {e}")

    def get_x_bogus(self, url: str, user_agent: str = None) -> str:
        """
        生成 x_bogus 签名

        Args:
            url: 请求URL（包含查询参数）
            user_agent: User-Agent 字符串

        Returns:
            x_bogus 签名字符串
        """
        if not self._x_bogus_ctx:
            logger.warning("x_bogus 上下文未初始化，返回模拟签名")
            return self._mock_signature()

        try:
            # 提取查询参数
            query = urllib.parse.urlparse(url).query or ""

            if not user_agent:
                user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

            # 调用JS函数生成签名
            x_bogus = self._x_bogus_ctx.call('sign', query, user_agent)
            logger.info(f"生成 x_bogus: {x_bogus[:20]}...")
            return x_bogus

        except Exception as e:
            logger.error(f"生成 x_bogus 失败: {e}")
            return self._mock_signature()

    def get_a_bogus(self, url: str, user_agent: str = None) -> str:
        """
        生成 a_bogus 签名

        Args:
            url: 请求URL（包含查询参数）
            user_agent: User-Agent 字符串

        Returns:
            a_bogus 签名字符串
        """
        if not self._a_bogus_ctx:
            logger.warning("a_bogus 上下文未初始化，返回模拟签名")
            return self._mock_signature()

        try:
            # 提取查询参数
            query = urllib.parse.urlparse(url).query or ""

            if not user_agent:
                user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

            # 调用JS函数生成签名
            a_bogus = self._a_bogus_ctx.call('generate_a_bogus', query, user_agent)
            logger.info(f"生成 a_bogus: {a_bogus[:20]}...")
            return a_bogus

        except Exception as e:
            logger.error(f"生成 a_bogus 失败: {e}")
            return self._mock_signature()

    def _mock_signature(self) -> str:
        """返回模拟签名（当JS不可用时）"""
        # 生成一个随机字符串
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        return ''.join(random.choice(chars) for _ in range(50))

    @staticmethod
    def get_ms_token(randomlength: int = 107) -> str:
        """
        生成 msToken

        Args:
            randomlength: 随机字符串长度

        Returns:
            msToken 字符串
        """
        random_str = ''
        base_str = 'ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789='
        length = len(base_str) - 1
        for _ in range(randomlength):
            random_str += base_str[random.randint(0, length)]
        return random_str

    @staticmethod
    def get_ttwid_webid(req_url: str = "https://www.douyin.com/") -> tuple:
        """
        获取 ttwid 和 webid

        Args:
            req_url: 请求的URL

        Returns:
            (ttwid, webid) 元组
        """
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(req_url, headers=headers, verify=False, timeout=10)
                cookies_dict = response.cookies.get_dict()
                ttwid_str = cookies_dict.get('ttwid', '')

                # 从页面中提取 webid
                render_data_text = re.compile(
                    r'<script id="RENDER_DATA"[^>]*>([^<]+)</script>'
                ).findall(response.text)

                webid = None
                if render_data_text:
                    try:
                        render_data_text = render_data_text[0]
                        render_data_text = urllib.parse.unquote(render_data_text)
                        render_data_json = json.loads(render_data_text, strict=False)
                        webid = render_data_json.get('app', {}).get('odin', {}).get('user_unique_id')
                    except Exception as e:
                        logger.warning(f"解析RENDER_DATA失败: {e}")

                if ttwid_str:
                    logger.info(f"获取 ttwid 成功: {ttwid_str[:30]}...")
                    return ttwid_str, webid or ""

            except Exception as e:
                logger.warning(f"获取 ttwid 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                time.sleep(1)

        return "", ""


# 全局实例
_signature = None


def get_douyin_signature() -> DouyinSignature:
    """获取签名生成器单例"""
    global _signature
    if _signature is None:
        _signature = DouyinSignature()
    return _signature


if __name__ == "__main__":
    # 测试
    sig = DouyinSignature()

    # 测试签名生成
    test_url = "https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=1234567890"
    print(f"测试URL: {test_url}")

    x_bogus = sig.get_x_bogus(test_url)
    print(f"x_bogus: {x_bogus}")

    a_bogus = sig.get_a_bogus(test_url)
    print(f"a_bogus: {a_bogus}")

    ms_token = sig.get_ms_token()
    print(f"msToken: {ms_token[:30]}...")

    ttwid, webid = sig.get_ttwid_webid()
    print(f"ttwid: {ttwid[:30] if ttwid else 'None'}...")
    print(f"webid: {webid}")

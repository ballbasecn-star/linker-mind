#!/usr/bin/env python3
"""
设置服务 - 管理 Cookies 和其他配置

存储位置: data/settings.json
"""
import json
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# 设置文件路径
SETTINGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
SETTINGS_FILE = os.path.join(SETTINGS_DIR, 'settings.json')

# 确保目录存在
os.makedirs(SETTINGS_DIR, exist_ok=True)


class SettingsService:
    """设置服务 - 管理应用配置"""

    def __init__(self):
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载设置失败: {e}")
                return {}
        return {}

    def _save_settings(self):
        """保存设置"""
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            logger.info("设置已保存")
        except Exception as e:
            logger.error(f"保存设置失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取设置值"""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any):
        """设置值"""
        self._settings[key] = value
        self._save_settings()

    def delete(self, key: str):
        """删除设置"""
        if key in self._settings:
            del self._settings[key]
            self._save_settings()

    def get_all(self) -> Dict[str, Any]:
        """获取所有设置"""
        return self._settings.copy()

    # ========== Cookies 管理 ==========

    def get_douyin_cookies(self) -> Optional[Dict[str, str]]:
        """获取抖音 Cookies"""
        cookies = self._settings.get('douyin_cookies')
        if cookies:
            # 返回但不显示完整内容（安全）
            return {
                'has_cookies': True,
                'updated_at': cookies.get('updated_at'),
                'description': cookies.get('description', '')
            }
        return None

    def set_douyin_cookies(self, cookie_string: str, description: str = '') -> bool:
        """
        设置抖音 Cookies

        Args:
            cookie_string: 浏览器导出的 cookie 字符串
            description: 描述

        Returns:
            是否成功
        """
        if not cookie_string:
            return False

        # 验证 cookie 格式
        if 'sessionid' not in cookie_string and 'ttwid' not in cookie_string:
            logger.warning("Cookie 字符串可能无效")

        self._settings['douyin_cookies'] = {
            'cookie_string': cookie_string,
            'description': description,
            'updated_at': datetime.now().isoformat()
        }
        self._save_settings()
        logger.info("抖音 Cookies 已更新")
        return True

    def delete_douyin_cookies(self):
        """删除抖音 Cookies"""
        if 'douyin_cookies' in self._settings:
            del self._settings['douyin_cookies']
            self._save_settings()
            logger.info("抖音 Cookies 已删除")

    def get_douyin_cookies_string(self) -> Optional[str]:
        """获取原始 Cookie 字符串（内部使用）"""
        cookies = self._settings.get('douyin_cookies')
        return cookies.get('cookie_string') if cookies else None


# 全局单例
_settings_service: Optional[SettingsService] = None


def get_settings_service() -> SettingsService:
    """获取设置服务单例"""
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService()
    return _settings_service

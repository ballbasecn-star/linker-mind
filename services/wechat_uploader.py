"""
WeChat Material Upload Service

Handles uploading images to WeChat official account material library.
This enables generated images to be permanently available in WeChat articles.

Note: This requires a registered WeChat Official Account (公众号) with
AppID and AppSecret configured.
"""
import os
import time
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class WeChatUploader:
    """微信公众号素材上传服务"""

    def __init__(self, app_id: str = None, app_secret: str = None):
        """
        Initialize WeChat uploader

        Args:
            app_id: WeChat Official Account AppID (defaults to env var)
            app_secret: WeChat Official Account AppSecret (defaults to env var)
        """
        self.app_id = app_id or os.environ.get('WECHAT_APP_ID')
        self.app_secret = app_secret or os.environ.get('WECHAT_APP_SECRET')
        self.access_token = None
        self.token_expires_at = 0

        if not self.app_id or not self.app_secret:
            logger.warning("WeChat APP_ID or APP_SECRET not configured")

    def get_access_token(self) -> Optional[str]:
        """
        获取Access Token

        Returns:
            Access token string or None if failed
        """
        import requests

        # Check if current token is still valid
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        if not self.app_id or not self.app_secret:
            logger.error("WeChat APP_ID or APP_SECRET not configured")
            return None

        try:
            url = f"https://api.weixin.qq.com/cgi-bin/token"
            params = {
                'grant_type': 'client_credential',
                'appid': self.app_id,
                'secret': self.app_secret
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if 'access_token' in data:
                self.access_token = data['access_token']
                # Token typically expires in 7200 seconds, use 7000 as safety margin
                self.token_expires_at = time.time() + data.get('expires_in', 7200) - 200
                logger.info("Successfully obtained WeChat access token")
                return self.access_token
            else:
                logger.error(f"Failed to get access token: {data}")
                return None

        except Exception as e:
            logger.error(f"Error getting WeChat access token: {e}")
            return None

    def upload_image(self, image_path: str) -> Optional[str]:
        """
        上传图片到微信素材库

        Args:
            image_path: Path to local image file

        Returns:
            Permanent URL of uploaded image or None if failed
        """
        import requests

        access_token = self.get_access_token()
        if not access_token:
            return None

        try:
            url = f"https://api.weixin.qq.com/cgi-bin/material/add_material"
            params = {
                'access_token': access_token,
                'type': 'image'
            }

            # Check if file exists
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return None

            # Prepare files
            with open(image_path, 'rb') as f:
                files = {'media': (os.path.basename(image_path), f, 'image/jpeg')}
                response = requests.post(url, params=params, files=files, timeout=30)

            data = response.json()

            if 'url' in data:
                logger.info(f"Successfully uploaded image to WeChat: {data['url']}")
                return data['url']
            else:
                logger.error(f"Failed to upload image: {data}")
                return None

        except Exception as e:
            logger.error(f"Error uploading image to WeChat: {e}")
            return None

    def upload_image_from_url(self, image_url: str, project_id: str = "default") -> Optional[str]:
        """
        Download image from URL and upload to WeChat

        Args:
            image_url: URL of the image to upload
            project_id: Project ID for naming

        Returns:
            Permanent URL of uploaded image or None if failed
        """
        import requests
        import uuid
        import tempfile

        try:
            # Download image
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to download image: {response.status_code}")
                return None

            # Determine content type
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            ext = 'jpg'
            if 'png' in content_type:
                ext = 'png'
            elif 'gif' in content_type:
                ext = 'gif'
            elif 'webp' in content_type:
                ext = 'webp'

            # Save to temporary file
            temp_filename = f"{project_id}_{uuid.uuid4().hex[:8]}.{ext}"
            temp_path = os.path.join(tempfile.gettempdir(), temp_filename)

            with open(temp_path, 'wb') as f:
                f.write(response.content)

            # Upload to WeChat
            result_url = self.upload_image(temp_path)

            # Clean up temp file
            try:
                os.remove(temp_path)
            except:
                pass

            return result_url

        except Exception as e:
            logger.error(f"Error uploading image from URL: {e}")
            return None

    def upload_images_batch(self, image_urls: list, project_id: str = "default") -> Dict[str, Any]:
        """
        Batch upload multiple images to WeChat

        Args:
            image_urls: List of image URLs to upload
            project_id: Project ID for naming

        Returns:
            Dictionary with upload results
        """
        results = {
            'total': len(image_urls),
            'success': 0,
            'failed': 0,
            'images': []
        }

        for i, url in enumerate(image_urls):
            logger.info(f"Uploading image {i+1}/{len(image_urls)}: {url}")

            wechat_url = self.upload_image_from_url(url, project_id)

            if wechat_url:
                results['success'] += 1
                results['images'].append({
                    'original_url': url,
                    'wechat_url': wechat_url,
                    'status': 'success'
                })
            else:
                results['failed'] += 1
                results['images'].append({
                    'original_url': url,
                    'wechat_url': None,
                    'status': 'failed'
                })

            # Add delay to avoid rate limiting
            if i < len(image_urls) - 1:
                time.sleep(1)

        logger.info(f"Batch upload complete: {results['success']} success, {results['failed']} failed")
        return results


def get_wechat_uploader() -> WeChatUploader:
    """Get WeChatUploader instance with configured credentials"""
    return WeChatUploader()

import time
import pyperclip
import re
import os
import sys
import requests
from playwright.sync_api import sync_playwright

# --- 配置 ---
DOWNLOAD_PATH = os.path.join(os.getcwd(), "抖音下载库")


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def extract_douyin_url(text):
    pattern = r'(https?://(?:v\.douyin\.com|www\.douyin\.com|www\.iesdouyin\.com)/[a-zA-Z0-9/]+)'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None


def download_with_playwright(url):
    print(f"\n⚡ 正在启动浏览器引擎解析: {url}")

    try:
        with sync_playwright() as p:
            # 启动无头浏览器 (headless=True 表示后台运行，看不到窗口)
            # 如果一直失败，可以改成 headless=False 看看发生了什么
            browser = p.chromium.launch(headless=True)

            # 伪装成手机，这样抖音会返回结构更简单的页面，更容易下载
            context = browser.new_context(
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
            )
            page = context.new_page()

            # 访问链接
            page.goto(url)

            # 等待视频标签加载出来 (最多等10秒)
            try:
                # 手机版网页通常会有 video 标签
                video_element = page.wait_for_selector('video', timeout=10000)
                video_src = video_element.get_attribute('src')

                # 获取标题用于文件名
                # 尝试获取描述文字
                try:
                    desc = page.locator('.desc').first.inner_text()
                    # 截取前20个字作为文件名，去除非法字符
                    title = re.sub(r'[\\/*?:"<>|]', '', desc)[:20].strip()
                except:
                    title = f"抖音视频_{int(time.time())}"

                if not title:
                    title = f"抖音视频_{int(time.time())}"

                print(f"🎬 解析成功，准备下载: {title}")
                print(f"🔗 真实地址: {video_src[:50]}...")

                # 使用 requests 下载这个真实地址
                if video_src:
                    r = requests.get(video_src, stream=True)
                    file_path = os.path.join(DOWNLOAD_PATH, f"{title}.mp4")

                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)
                    print(f"✅ 下载完成！已存入: {file_path}")
                else:
                    print("❌ 未找到视频源地址")

            except Exception as e:
                print(f"❌ 解析页面超时或失败: {e}")
                # 截图调试（如果需要）
                # page.screenshot(path="debug_error.png")

            finally:
                browser.close()

    except Exception as e:
        print(f"❌ 浏览器引擎出错: {e}")


def main():
    ensure_dir(DOWNLOAD_PATH)
    print("=" * 40)
    print(f"🚀 抖音终极下载器 (Playwright内核版)")
    print(f"📂 存储目录: {DOWNLOAD_PATH}")
    print("👀 正在监听剪贴板... (此方案无需Cookies，更稳定)")
    print("=" * 40)

    last_url = ""

    while True:
        try:
            clipboard_content = pyperclip.paste()
            current_url = extract_douyin_url(clipboard_content)

            if current_url and current_url != last_url:
                last_url = current_url
                download_with_playwright(current_url)
                print("\n👀 继续监听中...")

            time.sleep(1.5)

        except KeyboardInterrupt:
            print("\n🛑 程序已退出")
            sys.exit(0)
        except Exception:
            time.sleep(1.5)


if __name__ == "__main__":
    main()
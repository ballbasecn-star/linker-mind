# 抖音和微信处理器深度分析与优化方案

## 一、当前代码分析

### 1.1 抖音处理器 (DouyinProcessor) - 726行

#### 当前架构
```
提取流程：URL → 展开短链接 → MCP WebReader → requests → Firecrawl
                                ↓              ↓           ↓
                              元数据提取    script解析   API获取
                                              ↓
                                    JSON数据解析(6种方法)
```

#### 关键问题

**问题1: script标签JSON解析极其脆弱** (519-685行)
```python
# 当前代码：douyin_processor.py:519-685
# 6种不同的提取方法，说明页面结构频繁变化
for script in soup.find_all('script'):
    if script.string and 'window.__ROUTER_DATA__' in script.string:
        # 需要精确匹配变量名
        # 需要精确匹配JSON嵌套结构
        # 一处失败则全部失败
```

**影响**：
- 6种方法说明抖音页面结构至少变化过6次
- 每次变化都需要手动适配
- 正则表达式匹配JSON极其不可靠

**问题2: 正则表达式统计数据提取不可靠** (465-501行)
```python
# 当前代码：douyin_processor.py:465-501
patterns = {
    'likes': r'(\d+(?:\.\d+)?[kKwW万]?)\s*(?:点赞|likes?|like)',
    'comments': r'(\d+(?:\.\d+)?[kKwW万]?)\s*(?:评论|comments?)',
    ...
}
```

**影响**：
- 依赖页面显示文本格式
- 页面改版会导致正则失效
- 无法准确提取精确数据

**问题3: requests方法缺少反爬措施** (333-340行)
```python
# 当前代码：douyin_processor.py:333-340
headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) ...',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
# 缺少的关键headers:
# - Referer
# - Cookie
# - X-TT- (抖音的token验证)
```

**问题4: 错误处理不充分**
```python
# 当前代码：douyin_processor.py:84-100
if self.mcp_webreader_available:
    try:
        content = self._extract_with_mcp(expanded_url)
        result.processing_info["extraction_method"] = "mcp_webreader"
    except Exception as e:
        result.processing_info["mcp_error"] = str(e)
# 没有区分错误类型
# 没有重试逻辑
# 没有降级提示
```

### 1.2 微信处理器 (WeixinProcessor) - 315行

#### 当前架构
```
提取流程：URL → Firecrawl → requests
                    ↓          ↓
              API获取    BeautifulSoup解析
                         ↓
                    元标签提取(og:title, og:description等)
                         ↓
                    class名提取(rich_media_content, js_content等)
```

#### 关键问题

**问题1: 提取方法过于单一** (82-125行)
```python
# 当前代码：weixin_processor.py:56-61
if self.firecrawl_available:
    content = self._extract_with_firecrawl(url_info.url)
elif self.requests_available:
    content = self._extract_with_requests(url_info.url)
else:
    raise ValueError("Both Firecrawl and requests unavailable...")
```

**影响**：
- 没有MCP WebReader选项
- 降级策略只有一层
- 如果Firecrawl失败且requests被限制，无法获取内容

**问题2: 依赖固定的CSS类名** (152-158行)
```python
# 当前代码：weixin_processor.py:152-158
article_body = soup.find('div', class_='rich_media_content') or soup.find('div', id='js_content')
main_content = article_body.get_text('\n', strip=True) if article_body else ''

account_name_elem = soup.find('a', class_='account_name') or soup.find('span', class_='rich_meta_title')
```

**影响**：
- 微信可能随时更改这些类名
- 没有备用方案
- 一次性验证后很少维护

**问题3: 缺少script数据提取**
- 微信文章也经常在script标签中存储数据
- 当前代码完全没有提取script数据
- 完全依赖meta标签和HTML结构

**问题4: 没有内容验证**
```python
# 当前代码：weixin_processor.py:152-154
article_body = soup.find('div', class_='rich_media_content') or soup.find('div', id='js_content')
main_content = article_body.get_text('\n', strip=True) if article_body else ''
```

**影响**：
- 如果找不到元素，返回空字符串
- 没有警告或错误提示
- 用户不知道提取失败

---

## 二、优化方案

### 2.1 抖音处理器优化方案

#### 优化1: 增强script数据解析

**当前实现的问题**：
- 依赖6种不同的JSON解析方法
- 正则表达式匹配JSON边界不可靠
- 没有处理JSON解析后的数据验证

**改进方案**：
```python
def _extract_script_data_enhanced(self, soup) -> Dict[str, Any]:
    """增强的script数据提取"""
    result = {}

    # 方法1: 优先查找最可靠的数据源
    # 1.1 查找含有视频ID的script标签
    for script in soup.find_all('script'):
        if script.string:
            # 直接查找videoId模式
            video_match = re.search(r'"videoId":"(\d+)"', script.string)
            if video_match:
                result['video_id'] = video_match.group(1)

    # 1.2 查找desc模式
    for script in soup.find_all('script'):
        if script.string:
            desc_match = re.search(r'"desc":"([^"]+)"', script.string)
            if desc_match:
                result['desc'] = desc_match.group(1)

    # 方法2: 如果找到了基本数据，尝试完整解析
    if 'video_id' in result or 'desc' in result:
        # 继续尝试提取完整JSON
        for script in soup.find_all('script'):
            if script.string and ('videoInfo' in script.string or 'videoData' in script.string):
                try:
                    # 更健壮的JSON提取
                    json_start = script.string.find('{')
                    json_end = script.string.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = script.string[json_start:json_end]
                        data = json.loads(json_str)

                        # 验证数据结构
                        if isinstance(data, dict):
                            return self._validate_and_normalize_douyin_data(data)
                except Exception as e:
                    # 失败不影响已提取的基本数据
                    pass

    # 方法3: 最后的降级 - 使用URL本身
    if 'video_id' not in result:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(str(soup.find('meta', property='og:url')['content']))
        query = parse_qs(parsed.query)
        if 'video_id' in query:
            result['video_id'] = query['video_id'][0]
        elif 'vid' in query:
            result['video_id'] = query['vid'][0]

    return result

def _validate_and_normalize_douyin_data(self, data: Dict) -> Dict[str, Any]:
    """验证并标准化抖音数据"""
    normalized = {}

    # 标准化字段名
    field_mappings = {
        'desc': 'description',
        'aweme_id': 'video_id',
        'nickname': 'author_name',
        'uid': 'author_id',
        'digCount': 'likes',
        'commentCount': 'comments',
        'shareCount': 'shares',
    }

    for old_field, new_field in field_mappings.items():
        if old_field in data:
            normalized[new_field] = data[old_field]

    # 提取嵌套的video数据
    if 'video' in data and isinstance(data['video'], dict):
        video = data['video']
        if 'duration' in video:
            normalized['duration'] = video['duration']
        if 'cover' in video:
            if isinstance(video['cover'], dict):
                normalized['cover_url'] = video['cover'].get('url_list', [{}])[0].get('url', '')
            else:
                normalized['cover_url'] = video['cover']

    # 提取统计信息
    if 'statistics' in data and isinstance(data['statistics'], dict):
        stats = data['statistics']
        for field in ['digCount', 'commentCount', 'shareCount', 'playCount']:
            if field in stats:
                normalized[field.replace('Count', '').lower()] = stats[field]

    return normalized
```

#### 优化2: 增强requests方法

```python
def _extract_with_requests_enhanced(self, url: str) -> Dict[str, Any]:
    """增强的requests方法"""
    if not self.requests_available:
        raise ValueError("requests not available")

    headers = {
        # 模拟移动端抖音
        'User-Agent': 'com.ss.android.ugc.aweme/280102 (Linux; U; Android 12; zh_CN; V2205212; Build/280102; Device; samsung SM-S908E; cpp; 16)',
        'Accept': 'application/json',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        # 关键：添加Referer
        'Referer': 'https://www.douyin.com/',
        # 尝试获取Cookie
        'Cookie': self._get_cookies(),
    }

    session = requests.Session()

    # 第一次请求获取Cookie
    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # 更新Cookie
        if 'Set-Cookie' in response.headers:
            session.cookies.update(response.cookies)
    except Exception:
        pass

    # 第二次请求获取内容
    response = session.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    soup = self.bs4(response.content, 'html.parser')

    # 使用增强的解析方法
    script_data = self._extract_script_data_enhanced(soup)

    # 如果script数据不充分，使用HTML解析
    if not script_data.get('desc') or not script_data.get('video_id'):
        html_data = self._extract_from_html_enhanced(soup)
        script_data.update(html_data)

    return {
        "title": script_data.get('description', '')[:100] or "抖音视频",
        "url": url,
        "main_content": script_data.get('description', ''),
        "metadata": {
            "platform": "douyin",
            "author": script_data.get('author_name', ''),
            "author_id": script_data.get('author_id', ''),
            "description": script_data.get('description', ''),
            "likes": script_data.get('likes', 0),
            "comments": script_data.get('comments', 0),
            "shares": script_data.get('shares', 0),
            "video_id": script_data.get('video_id', ''),
            "duration": script_data.get('duration', 0),
            "play_count": script_data.get('play_count', 0),
            "publish_date": "",
            "tags": [],
        },
        "extracted_data": {
            "source": "_requests_enhanced",
            "script_data": script_data,
        }
    }

def _get_cookies(self) -> str:
    """获取或生成Cookie"""
    # 尝试从缓存读取
    # 如果没有，生成基础Cookie
    cookies = [
        "ttwid=1%7C2r%7Cw%7Cj%7Cq%7Cp%7Cz%7Cr%7Cs%7Ct%7Cu%7Cv%7Cw%7Cx%7Cy%7Cz",
        "passport_csrf_token=placeholder",
        "passport_csrf_default=placeholder",
    ]
    return "; ".join(cookies)
```

#### 优化3: 添加错误分类和重试逻辑

```python
class DouyinExtractionError(Exception):
    """抖音提取错误基类"""
    def __init__(self, error_code: str, message: str, recoverable: bool = False):
        self.error_code = error_code
        self.recoverable = recoverable
        super().__init__(message)

class RateLimitError(DouyinExtractionError):
    """速率限制错误（可恢复）"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            error_code="RATE_LIMIT",
            message=f"Rate limited, retry after {retry_after}s",
            recoverable=True
        )
        self.retry_after = retry_after

class ContentNotFoundError(DouyinExtractionError):
    """内容未找到错误（可能不可恢复）"""
    def __init__(self, url: str):
        super().__init__(
            error_code="CONTENT_NOT_FOUND",
            message=f"Content not found for URL: {url}",
            recoverable=False
        )

def extract_with_retry(self, url_info: URLInfo, max_retries: int = 3) -> ProcessedContent:
    """带重试的提取方法"""
    last_error = None

    for attempt in range(max_retries):
        try:
            # 每次尝试使用不同的方法
            if attempt == 0:
                # 第一次：优先使用MCP
                if self.mcp_webreader_available:
                    return self._extract_with_mcp(url_info.url)
            elif attempt == 1:
                # 第二次：使用增强的requests
                return self._extract_with_requests_enhanced(url_info.url)
            else:
                # 第三次：使用Firecrawl
                return self._extract_with_firecrawl(url_info.url)
        except RateLimitError as e:
            if attempt < max_retries - 1:
                time.sleep(e.retry_after)
                last_error = e
                continue
            raise
        except DouyinExtractionError as e:
            if not e.recoverable:
                raise
            last_error = e
            continue
        except Exception as e:
            last_error = e
            continue

    # 所有重试都失败
    raise DouyinExtractionError(
        error_code="EXTRACTION_FAILED",
        message=f"Failed after {max_retries} attempts: {last_error}",
        recoverable=False
    )
```

#### 优化4: 添加数据完整性验证

```python
def _validate_extracted_data(self, data: Dict[str, Any], url: str) -> bool:
    """验证提取的数据是否完整"""
    required_fields = ['title', 'url']
    important_fields = ['description', 'video_id', 'author']

    # 检查必需字段
    for field in required_fields:
        if not data.get(field):
            logger.warning(f"Missing required field: {field} for {url}")
            return False

    # 检查重要字段（至少有一个）
    has_important = any(data.get(field) for field in important_fields)
    if not has_important:
        logger.warning(f"No important fields found for {url}")
        return False

    # 验证数据质量
    if data.get('description') and len(data['description']) < 10:
        logger.warning(f"Description too short for {url}: {data.get('description')}")
        return False

    return True
```

### 2.2 微信处理器优化方案

#### 优化1: 添加MCP WebReader支持

```python
def __init__(self):
    super().__init__()
    # 原有代码...

    # 新增：MCP WebReader支持
    self.mcp_webreader_available = False
    self.mcp_webreader = None

def set_mcp_tools(self, mcp_webreader):
    """设置MCP工具"""
    self.mcp_webreader = mcp_webreader
    self.mcp_webreader_available = mcp_webreader is not None

def extract(self, url_info: URLInfo) -> ProcessedContent:
    """提取微信内容"""
    self._start_timer()
    result = self._create_base_content(url_info)

    try:
        content = None

        # 优先级1: MCP WebReader（新增）
        if self.mcp_webreader_available:
            try:
                content = self._extract_with_mcp(url_info.url)
                result.processing_info["extraction_method"] = "mcp_webreader"
            except Exception as e:
                result.processing_info["mcp_error"] = str(e)

        # 优先级2: Firecrawl
        if not content and self.firecrawl_available:
            try:
                content = self._extract_with_firecrawl(url_info.url)
                result.processing_info["extraction_method"] = "firecrawl"
            except Exception as e:
                result.processing_info["firecrawl_error"] = str(e)

        # 优先级3: requests + BeautifulSoup
        if not content and self.requests_available:
            content = self._extract_with_requests_enhanced(url_info.url)
            result.processing_info["extraction_method"] = "requests"

        # 验证提取结果
        if not content or not content.get('main_content'):
            raise ValueError("Failed to extract content from all methods")

        # 更新结果
        result.content.update(content)
        result.media = self._build_media_info(content)

        result.processing_info.update({
            "processing_time": self._end_timer(),
            "success": True,
            "errors": []
        })

    except Exception as e:
        result.processing_info.update({
            "processing_time": self._end_timer(),
            "success": False,
            "errors": [str(e)]
        })
        raise

    return result

def _extract_with_mcp(self, url: str) -> Dict[str, Any]:
    """使用MCP WebReader提取"""
    if not self.mcp_webreader:
        raise ValueError("MCP WebReader not available")

    mcp_result = self.mcp_webreader(
        url=url,
        return_format="markdown",
        timeout=30,
        retain_images=True
    )

    markdown = getattr(mcp_result, 'markdown', '') or str(mcp_result)
    html = getattr(mcp_result, 'html', '') if hasattr(mcp_result, 'html') else ''

    return {
        "title": self._extract_title_from_markdown(markdown),
        "url": url,
        "main_content": markdown,
        "html": html,
        "metadata": {
            "platform": "wechat",
            "author": self._extract_author(markdown, html),
            "description": self._extract_description(markdown),
            "article_id": self._extract_article_id(url),
            "tags": self._extract_tags(markdown),
        }
    }
```

#### 优化2: 增强requests方法

```python
def _extract_with_requests_enhanced(self, url: str) -> Dict[str, Any]:
    """增强的requests提取方法"""
    if not self.requests_available:
        raise ValueError("requests not available")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://mp.weixin.qq.com/',
    }

    response = self.requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    soup = self.bs4(response.content, 'html.parser')

    # 多层提取策略
    content = {}

    # 优先级1: 提取script数据（新增）
    script_data = self._extract_script_data(soup)
    if script_data:
        content.update(script_data)

    # 优先级2: 提取meta标签
    meta_data = self._extract_meta_tags(soup)
    content.update(meta_data)

    # 优先级3: 提取HTML结构
    if not content.get('main_content'):
        html_data = self._extract_html_structure(soup)
        content.update(html_data)

    # 验证提取结果
    if not content.get('title') or not content.get('main_content'):
        raise ValueError(f"Failed to extract essential content from {url}")

    return {
        "title": content.get('title', '微信文章'),
        "url": url,
        "main_content": content.get('main_content', ''),
        "html": str(soup),
        "metadata": {
            "platform": "wechat",
            "author": content.get('author', ''),
            "account_name": content.get('account_name', ''),
            "publish_date": content.get('publish_date', ''),
            "article_id": content.get('article_id', ''),
            "tags": content.get('tags', []),
        },
        "extracted_data": {
            "source": "requests_enhanced"
        }
    }

def _extract_script_data(self, soup) -> Dict[str, Any]:
    """提取微信文章的script数据"""
    for script in soup.find_all('script'):
        if script.string:
            # 查找msg数据
            msg_match = re.search(r'var msg = ({.+?});', script.string)
            if msg_match:
                try:
                    msg_data = json.loads(msg_match.group(1))
                    if isinstance(msg_data, dict):
                        return self._normalize_weixin_msg_data(msg_data)
                except Exception:
                    pass

            # 查找其他常见格式
            for pattern in [
                r'window\.msg\s*=\s*({.+?});',
                r'ct\s*=\s*({.+?});',
            ]:
                match = re.search(pattern, script.string)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        if isinstance(data, dict):
                            return self._normalize_weixin_msg_data(data)
                    except Exception:
                        pass

    return {}

def _normalize_weixin_msg_data(self, data: Dict) -> Dict:
    """标准化微信msg数据"""
    normalized = {}

    if 'title' in data:
        normalized['title'] = data['title']

    if 'content' in data:
        normalized['main_content'] = data['content']

    if 'author' in data and isinstance(data['author'], dict):
        author = data['author']
        normalized['author'] = author.get('name', '')
        normalized['account_name'] = author.get('public_name', '')

    if 'publish_time' in data:
        normalized['publish_date'] = data['publish_time']

    # 提取封面图
    if 'cover' in data:
        normalized['cover_image'] = data['cover']
    elif 'cdn_url' in data:
        normalized['cover_image'] = data['cdn_url']

    return normalized

def _extract_meta_tags(self, soup) -> Dict:
    """提取meta标签"""
    meta_data = {}

    # 标题
    for meta_name in ['og:title', 'twitter:title']:
        meta = soup.find('meta', property=meta_name)
        if meta and meta.get('content'):
            meta_data['title'] = meta.get('content')
            break

    # 描述
    for meta_name in ['og:description', 'twitter:description', 'description']:
        meta = soup.find('meta', property=meta_name) or soup.find('meta', attrs={'name': meta_name})
        if meta and meta.get('content'):
            meta_data['description'] = meta.get('content')
            break

    # 作者
    for meta_name in ['og:article:author', 'article:author', 'author']:
        meta = soup.find('meta', property=meta_name) or soup.find('meta', attrs={'name': meta_name})
        if meta and meta.get('content'):
            meta_data['author'] = meta.get('content')
            break

    # 公众号
    for meta_name in ['og:article:author', 'weixin:account_nickname']:
        meta = soup.find('meta', property=meta_name) or soup.find('meta', attrs={'name': meta_name})
        if meta and meta.get('content'):
            meta_data['account_name'] = meta.get('content')
            break

    # 发布时间
    for meta_name in ['og:article:published_time', 'article:published_time', 'publish_time']:
        meta = soup.find('meta', property=meta_name) or soup.find('meta', attrs={'name': meta_name})
        if meta and meta.get('content'):
            meta_data['publish_date'] = meta.get('content')
            break

    # 封面图
    for meta_name in ['og:image', 'twitter:image']:
        meta = soup.find('meta', property=meta_name)
        if meta and meta.get('content'):
            meta_data['cover_image'] = meta.get('content')
            break

    return meta_data

def _extract_html_structure(self, soup) -> Dict:
    """提取HTML结构"""
    html_data = {}

    # 多个可能的class名
    content_classes = [
        'rich_media_content',
        'rich_media_area',
        'wx_rich_media_content',
        'js_content',
    ]

    for class_name in content_classes:
        elem = soup.find('div', class_=class_name)
        if elem:
            html_data['main_content'] = elem.get_text('\n', strip=True)
            break

    # 尝试id选择器
    if not html_data.get('main_content'):
        for elem_id in ['js_content', 'content', 'article-content']:
            elem = soup.find('div', id=elem_id)
            if elem:
                html_data['main_content'] = elem.get_text('\n', strip=True)
                break

    # 账号名
    account_classes = ['account_name', 'rich_meta_title', 'wx_account_nickname']
    for class_name in account_classes:
        elem = soup.find('a', class_=class_name) or soup.find('span', class_=class_name)
        if elem:
            html_data['account_name'] = elem.get_text(strip=True)
            break

    return html_data
```

#### 优化3: 添加内容验证

```python
def _validate_weixin_content(self, content: Dict) -> bool:
    """验证微信内容"""
    # 检查必需字段
    if not content.get('url'):
        return False

    # 检查内容质量
    main_content = content.get('main_content', '')
    if len(main_content) < 50:
        logger.warning(f"WeChat content too short: {len(main_content)} chars")
        return False

    # 检查标题
    title = content.get('title', '')
    if len(title) < 5:
        logger.warning(f"WeChat title too short: {title}")
        return False

    # 检查是否包含微信特有的内容
    if 'mp.weixin.qq.com' not in content.get('url', ''):
        logger.warning(f"Invalid WeChat URL: {content.get('url')}")
        return False

    return True
```

---

## 三、测试建议

### 3.1 抖音处理器测试

```python
def test_douyin_extraction():
    """测试抖音提取"""
    test_urls = [
        "https://www.douyin.com/video/123456789",
        "https://v.douyin.com/123456789",
    ]

    processor = DouyinProcessor()

    for url in test_urls:
        print(f"\nTesting: {url}")

        try:
            from url_detector import detect_url
            url_info = detect_url(url)

            if processor.can_process(url_info):
                content = processor.extract(url_info)

                # 验证提取结果
                assert content.content.get('title'), "Title required"
                assert content.content.get('metadata', {}).get('video_id'), "Video ID required"

                print(f"✅ Success: {content.content.get('title')}")
                print(f"   Video ID: {content.content.get('metadata', {}).get('video_id')}")
            else:
                print(f"❌ Cannot process this URL type")
        except Exception as e:
            print(f"❌ Failed: {e}")
```

### 3.2 微信处理器测试

```python
def test_weixin_extraction():
    """测试微信提取"""
    test_urls = [
        "https://mp.weixin.qq.com/s/xxx",
        "https://mp.weixin.qq.com/s?__biz=xxx",
    ]

    processor = WeixinProcessor()

    for url in test_urls:
        print(f"\nTesting: {url}")

        try:
            from url_detector import detect_url
            url_info = detect_url(url)

            if processor.can_process(url_info):
                content = processor.extract(url_info)

                # 验证提取结果
                assert content.content.get('title'), "Title required"
                assert len(content.content.get('main_content', '')) > 50, "Content too short"

                print(f"✅ Success: {content.content.get('title')}")
                print(f"   Author: {content.content.get('metadata', {}).get('author')}")
            else:
                print(f"❌ Cannot process this URL type")
        except Exception as e:
            print(f"❌ Failed: {e}")
```

---

## 四、实施优先级

### P0（立即实施）
1. ✅ 为抖音处理器添加数据完整性验证
2. ✅ 为微信处理器添加MCP WebReader支持
3. ✅ 统一错误处理格式

### P1（本周完成）
4. ✅ 增强抖音的requests方法（Cookie、Referer）
5. ✅ 增强微信的requests方法（多层降级）
6. ✅ 添加重试逻辑

### P2（下周完成）
7. ✅ 优化script数据提取算法
8. ✅ 添加测试套件
9. ✅ 性能优化（缓存、并发）

---

## 五、关键指标

### 抖音处理器
- **成功率目标**: > 95%
- **平均提取时间**: < 5秒
- **数据完整度**: title + desc + video_id + stats
- **降级成功率**: MCP > requests > Firecrawl

### 微信处理器
- **成功率目标**: > 90%
- **平均提取时间**: < 3秒
- **数据完整度**: title + content + author + account_name
- **降级成功率**: MCP > Firecrawl > requests

---

*文档生成日期: 2026-02-15*

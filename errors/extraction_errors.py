#!/usr/bin/env python3
"""
统一的错误处理模块

为内容提取系统提供一致的错误类型和处理
"""
import os
import sys
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"           # 低：可重试的错误
    MEDIUM = "medium"      # 中：影响功能但不致命
    HIGH = "high"         # 高：致命错误
    CRITICAL = "critical"  # 严重：系统级错误


class ErrorCategory(Enum):
    """错误类别"""
    NETWORK = "network"           # 网络相关错误
    DETECTION = "detection"       # URL检测错误
    EXTRACTION = "extraction"     # 内容提取错误
    VALIDATION = "validation"      # 数据验证错误
    CONFIGURATION = "config"      # 配置错误
    AUTHENTICATION = "auth"       # 认证相关错误
    RATE_LIMIT = "rate_limit"      # 速率限制错误
    UNKNOWN = "unknown"           # 未知错误


@dataclass
class ExtractionError:
    """
    统一的提取错误类

    所有处理器应使用此类返回错误，确保一致性
    """
    code: str                    # 错误代码
    message: str                  # 错误消息
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    category: ErrorCategory = ErrorCategory.UNKNOWN
    recoverable: bool = False         # 是否可恢复（可重试）
    details: Optional[Dict[str, Any]] = None  # 额外详情
    suggestion: Optional[str] = None     # 建议的解决方案

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'message': self.message,
            'severity': self.severity.value,
            'category': self.category.value,
            'recoverable': self.recoverable,
            'details': self.details or {},
            'suggestion': self.suggestion
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def raise_exception(self):
        """抛出异常"""
        raise ContentExtractionException(self)


class ContentExtractionException(Exception):
    """内容提取异常"""

    def __init__(self, error: ExtractionError):
        self.error = error
        super().__init__(str(error))


# 预定义错误类型
class Errors:
    """常用错误类型的工厂类"""

    # 网络错误
    @staticmethod
    def network_error(message: str, recoverable: bool = True) -> ExtractionError:
        return ExtractionError(
            code="NETWORK_ERROR",
            message=message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            recoverable=recoverable,
            suggestion="检查网络连接或重试"
        )

    @staticmethod
    def timeout_error(url: str, timeout: int) -> ExtractionError:
        return ExtractionError(
            code="TIMEOUT_ERROR",
            message=f"请求超时 ({timeout}s): {url}",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.NETWORK,
            recoverable=True,
            details={'url': url, 'timeout': timeout},
            suggestion="增加超时时间或检查目标服务器"
        )

    @staticmethod
    def connection_error(url: str, original_error: str = "") -> ExtractionError:
        return ExtractionError(
            code="CONNECTION_ERROR",
            message=f"无法连接到服务器: {url}",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            recoverable=True,
            details={'url': url, 'original_error': original_error},
            suggestion="检查URL是否可访问或网络连接"
        )

    # URL检测错误
    @staticmethod
    def detection_failed(url: str, reason: str = "") -> ExtractionError:
        return ExtractionError(
            code="DETECTION_FAILED",
            message=f"无法检测URL类型: {url}",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DETECTION,
            recoverable=False,
            details={'url': url, 'reason': reason},
            suggestion="检查URL格式或联系管理员添加此平台支持"
        )

    @staticmethod
    def unsupported_platform(platform: str) -> ExtractionError:
        return ExtractionError(
            code="UNSUPPORTED_PLATFORM",
            message=f"不支持的平台: {platform}",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DETECTION,
            recoverable=False,
            details={'platform': platform},
            suggestion="联系管理员添加此平台的处理器"
        )

    # 内容提取错误
    @staticmethod
    def extraction_failed(url: str, reason: str = "") -> ExtractionError:
        return ExtractionError(
            code="EXTRACTION_FAILED",
            message=f"内容提取失败: {url}",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.EXTRACTION,
            recoverable=True,
            details={'url': url, 'reason': reason},
            suggestion="尝试使用不同的提取方法或稍后重试"
        )

    @staticmethod
    def no_content_found(url: str) -> ExtractionError:
        return ExtractionError(
            code="NO_CONTENT_FOUND",
            message=f"未找到主要内容: {url}",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.EXTRACTION,
            recoverable=False,
            details={'url': url},
            suggestion="页面可能已删除或需要登录访问"
        )

    @staticmethod
    def invalid_content_format(format_type: str, expected: str, got: str) -> ExtractionError:
        return ExtractionError(
            code="INVALID_FORMAT",
            message=f"无效的内容格式: 期望 {expected}, 得到 {got}",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.VALIDATION,
            recoverable=False,
            details={'format_type': format_type, 'expected': expected, 'got': got},
            suggestion="检查内容解析逻辑或页面结构是否变化"
        )

    # 认证和授权错误
    @staticmethod
    def authentication_failed(platform: str, reason: str = "") -> ExtractionError:
        return ExtractionError(
            code="AUTH_FAILED",
            message=f"认证失败 ({platform}): {reason}",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.AUTHENTICATION,
            recoverable=False,
            details={'platform': platform, 'reason': reason},
            suggestion="更新API密钥或检查认证配置"
        )

    @staticmethod
    def rate_limit_exceeded(platform: str, limit: int = 0) -> ExtractionError:
        return ExtractionError(
            code="RATE_LIMIT_EXCEEDED",
            message=f"超过速率限制 ({platform})",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.RATE_LIMIT,
            recoverable=True,
            details={'platform': platform, 'limit': limit},
            suggestion="等待一段时间后重试或升级API配额"
        )

    # 配置错误
    @staticmethod
    def missing_config(key: str) -> ExtractionError:
        return ExtractionError(
            code="MISSING_CONFIG",
            message=f"缺少必需的配置: {key}",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.CONFIGURATION,
            recoverable=False,
            details={'key': key},
            suggestion="在.env文件中设置此配置项"
        )

    @staticmethod
    def invalid_config(key: str, value: str, reason: str) -> ExtractionError:
        return ExtractionError(
            code="INVALID_CONFIG",
            message=f"配置无效 ({key}): {value}",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.CONFIGURATION,
            recoverable=False,
            details={'key': key, 'value': value, 'reason': reason},
            suggestion="检查配置值格式和有效性"
        )

    # API错误
    @staticmethod
    def api_error(service: str, status_code: int, message: str = "") -> ExtractionError:
        return ExtractionError(
            code="API_ERROR",
            message=f"API错误 ({service}): HTTP {status_code}",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            recoverable=status_code < 500,  # 5xx错误可能不可恢复
            details={'service': service, 'status_code': status_code, 'message': message},
            suggestion=f"检查API状态码 {status_code} 的含义"
        )


def convert_exception_to_error(exception: Exception, url: str = "") -> ExtractionError:
    """
    将Python异常转换为统一的ExtractionError

    Args:
        exception: Python异常对象
        url: 相关的URL

    Returns:
        ExtractionError对象
    """
    error_type = type(exception).__name__

    # 网络相关异常
    if 'ConnectionError' in error_type or 'Connect' in error_type:
        return Errors.connection_error(url, str(exception))

    if 'Timeout' in error_type:
        return Errors.timeout_error(url, 30)

    # HTTP异常
    if 'HTTPError' in error_type or 'HTTP' in error_type:
        status_code = getattr(exception, 'status', 0)
        return Errors.api_error('HTTP', status_code, str(exception))

    # JSON解析异常
    if 'JSONDecodeError' in error_type:
        return Errors.extraction_failed(url, 'JSON解析失败')

    # 通用异常
    return ExtractionError(
        code=error_type,
        message=str(exception),
        severity=ErrorSeverity.MEDIUM,
        category=ErrorCategory.UNKNOWN,
        recoverable=True,
        details={'exception_type': error_type, 'url': url}
    )


def validate_result(result: Any, url: str) -> bool:
    """
    验证提取结果的有效性

    Args:
        result: 提取结果对象
        url: 原始URL

    Returns:
        True if valid, raises ExtractionError if invalid
    """
    # 检查必需字段
    if not hasattr(result, 'processing_info'):
        raise Errors.invalid_content_format('result', 'has processing_info', 'missing')

    if not hasattr(result, 'content'):
        raise Errors.invalid_content_format('result', 'has content', 'missing')

    # 检查内容有效性
    content = result.content
    if not content.get('title') and not content.get('main_content'):
        raise Errors.no_content_found(url)

    return True


def main():
    """测试错误处理"""
    import argparse

    parser = argparse.ArgumentParser(description="错误处理测试")
    parser.add_argument("--test", choices=['exception', 'validation'], help="测试类型")

    args = parser.parse_args()

    print("统一错误处理测试")
    print("="*60)

    if args.test == 'exception':
        # 测试异常转换
        print("\n测试异常转换:")

        exceptions = [
            ConnectionError("无法连接到服务器"),
            TimeoutError("请求超时"),
            ValueError("无效的JSON"),
            Exception("未知错误")
        ]

        for exc in exceptions:
            error = convert_exception_to_error(exc, "https://example.com")
            print(f"✅ {type(exc).__name__:} -> {error.code}")
            print(f"   消息: {error.message}")
            print(f"   可恢复: {error.recoverable}")
            print(f"   建议: {error.suggestion}")
            print()

    elif args.test == 'validation':
        # 测试结果验证
        print("\n测试结果验证:")

        # 创建测试结果
        from content_processor import ProcessedContent, URLInfo

        valid_result = ProcessedContent(
            id="test",
            timestamp="2024-01-01",
            raw_input="https://example.com",
            source_type="webpage",
            platform="test",
            content={
                'title': '测试标题',
                'main_content': '测试内容',
                'metadata': {}
            },
            processing_info={'success': True}
        )

        try:
            validate_result(valid_result, "https://example.com")
            print("✅ 有效结果验证通过")
        except ExtractionError as e:
            print(f"❌ 验证失败: {e}")

        # 测试无效结果
        invalid_result = ProcessedContent(
            id="test",
            timestamp="2024-01-01",
            raw_input="https://example.com",
            source_type="webpage",
            platform="test",
            content={},  # 空内容
            processing_info={'success': True}
        )

        try:
            validate_result(invalid_result, "https://example.com")
            print("✅ 不应该到达这里")
        except ExtractionError as e:
            print(f"✅ 正确捕获无效结果: {e.code}")

    print("="*60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

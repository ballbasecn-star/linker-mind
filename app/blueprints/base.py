"""
Base Blueprint Class

提供统一的错误处理、响应格式和工具方法
"""
from functools import wraps
from typing import Callable, Any, Optional
import logging

from flask import Blueprint, jsonify
from database.db_interface import get_connection

logger = logging.getLogger(__name__)


class BlueprintBase:
    """
    所有 Blueprint 的基类

    提供:
    - 统一的错误处理
    - 统一的响应格式
    - 通用的工具方法
    """

    def __init__(self, name: str, import_name: str, **kwargs):
        """
        初始化 Blueprint

        Args:
            name: Blueprint 名称
            import_name: 导入名称（通常是 __name__）
            **kwargs: 传递给 Blueprint 的其他参数
        """
        self.blueprint = Blueprint(name, import_name, **kwargs)
        self.db = get_connection()

    def route(self, rule: str, **options):
        """
        路由装饰器，带自动错误处理

        使用方式:
            @bp.route('/api/items', methods=['GET'])
            def list_items():
                return self.success(items)
        """
        def decorator(f: Callable) -> Callable:
            @self.blueprint.route(rule, **options)
            @wraps(f)
            def wrapped(*args, **kwargs):
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in {f.__name__}: {e}", exc_info=True)
                    return self.error(str(e)), 500
            return wrapped
        return decorator

    def success(self, data: Any = None, meta: Optional[dict] = None, status_code: int = 200):
        """
        成功响应

        Args:
            data: 返回的数据
            meta: 元数据（如分页信息）
            status_code: HTTP 状态码

        Returns:
            JSON 响应
        """
        response = {
            'success': True,
            'data': data
        }
        if meta:
            response['meta'] = meta
        return jsonify(response), status_code

    def error(self, message: str, code: str = 'ERROR', status_code: int = 500):
        """
        错误响应

        Args:
            message: 错误消息
            code: 错误代码
            status_code: HTTP 状态码

        Returns:
            JSON 响应
        """
        return jsonify({
            'success': False,
            'error': message,
            'code': code
        }), status_code

    def validation_error(self, errors: dict):
        """验证错误 (400)"""
        return self.error('Validation failed', 'VALIDATION_ERROR', 400)

    def not_found(self, message: str = 'Resource not found'):
        """未找到 (404)"""
        return self.error(message, 'NOT_FOUND', 404)

    def bad_request(self, message: str = 'Bad request'):
        """错误请求 (400)"""
        return self.error(message, 'BAD_REQUEST', 400)

    def unauthorized(self, message: str = 'Unauthorized'):
        """未授权 (401)"""
        return self.error(message, 'UNAUTHORIZED', 401)

    def forbidden(self, message: str = 'Forbidden'):
        """禁止访问 (403)"""
        return self.error(message, 'FORBIDDEN', 403)

    def conflict(self, message: str = 'Resource conflict'):
        """冲突 (409)"""
        return self.error(message, 'CONFLICT', 409)

    def get_pagination_params(self, default_page: int = 1, default_page_size: int = 20,
                             max_page_size: int = 100) -> tuple:
        """
        获取分页参数

        Args:
            default_page: 默认页码
            default_page_size: 默认每页大小
            max_page_size: 最大每页大小

        Returns:
            (page, page_size) 元组
        """
        from flask import request

        try:
            page = max(1, int(request.args.get('page', default_page)))
            page_size = min(
                max(1, int(request.args.get('page_size', default_page_size))),
                max_page_size
            )
        except (ValueError, TypeError):
            page = default_page
            page_size = default_page_size

        return page, page_size

    def calculate_pagination_meta(self, total: int, page: int, page_size: int) -> dict:
        """
        计算分页元数据

        Args:
            total: 总记录数
            page: 当前页
            page_size: 每页大小

        Returns:
            分页元数据字典
        """
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }

    def get_json_data(self, required_fields: Optional[list] = None) -> Optional[dict]:
        """
        获取 JSON 请求数据并验证

        Args:
            required_fields: 必需字段列表

        Returns:
            数据字典，如果验证失败返回 None
        """
        from flask import request

        data = request.get_json()

        if not data:
            self.bad_request('Request body is required')
            return None

        if required_fields:
            missing = [field for field in required_fields if field not in data]
            if missing:
                self.validation_error({
                    'missing_fields': missing,
                    'message': f'Missing required fields: {", ".join(missing)}'
                })
                return None

        return data

    def get_query_param(self, key: str, default: Any = None, type_func: Optional[Callable] = None) -> Any:
        """
        获取查询参数并可选地转换类型

        Args:
            key: 参数名
            default: 默认值
            type_func: 类型转换函数

        Returns:
            参数值
        """
        from flask import request

        value = request.args.get(key, default)

        if value is not None and type_func:
            try:
                return type_func(value)
            except (ValueError, TypeError):
                logger.warning(f"Invalid {key} value: {value}")
                return default

        return value


def create_blueprint_base(name: str, import_name: str, url_prefix: Optional[str] = None):
    """
    工厂函数：创建带有 URL 前缀的 BlueprintBase

    Args:
        name: Blueprint 名称
        import_name: 导入名称
        url_prefix: URL 前缀

    Returns:
        BlueprintBase 实例
    """
    kwargs = {}
    if url_prefix:
        kwargs['url_prefix'] = url_prefix

    return BlueprintBase(name, import_name, **kwargs)


# 导出以便使用
__all__ = ['BlueprintBase', 'create_blueprint_base']

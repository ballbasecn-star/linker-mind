#!/usr/bin/env python3
"""
配置验证模块

验证应用启动时所需的配置是否完整
"""
import os
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


@dataclass
class ConfigRequirement:
    """配置要求"""
    key: str
    description: str
    required: bool = True
    default_value: Optional[str] = None
    validator: Optional[callable] = None


class ConfigValidator:
    """配置验证器"""

    # 必需配置项
    REQUIRED_CONFIGS = {
        'FIRECRAWL_API_KEY': ConfigRequirement(
            key='FIRECRAWL_API_KEY',
            description='Firecrawl API密钥（用于通用网页内容提取）',
            required=True,
            validator=lambda x: len(x) > 10 if x else False
        ),
        'DEEPSEEK_API_KEY': ConfigRequirement(
            key='DEEPSEEK_API_KEY',
            description='DeepSeek AI分析密钥（用于内容智能分析）',
            required=False  # AI功能可选
        ),
        'DATABASE_URL': ConfigRequirement(
            key='DATABASE_URL',
            description='数据库连接字符串',
            required=True,
            # 支持多种格式：postgresql://, jdbc:postgresql://, sqlite:///
            validator=lambda x: x and (
                x.startswith('postgresql://') or
                x.startswith('jdbc:postgresql://') or
                x.startswith('sqlite:///') or
                x.startswith('jdbc:sqlite:///')
            )
        )
    }

    # 可选配置项
    OPTIONAL_CONFIGS = {
        'FIRECRAWL_TIMEOUT': ConfigRequirement(
            key='FIRECRAWL_TIMEOUT',
            description='Firecrawl请求超时时间（秒）',
            required=False,
            default_value='30'
        ),
        'MAX_RETRIES': ConfigRequirement(
            key='MAX_RETRIES',
            description='最大重试次数',
            required=False,
            default_value='3'
        ),
        'LOG_LEVEL': ConfigRequirement(
            key='LOG_LEVEL',
            description='日志级别',
            required=False,
            default_value='INFO'
        )
    }

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.config_values = {}

    def validate_all(self, raise_on_error: bool = True) -> bool:
        """验证所有配置"""
        print("\n" + "="*60)
        print("配置验证")
        print("="*60)

        is_valid = True

        # 验证必需配置
        print("\n[必需配置]")
        for key, requirement in self.REQUIRED_CONFIGS.items():
            value = os.getenv(requirement.key)
            self.config_values[key] = value

            if requirement.required and not value:
                error_msg = f"❌ {requirement.key}: 未设置"
                self.errors.append(error_msg)
                print(error_msg)
                is_valid = False
            elif value and requirement.validator and not requirement.validator(value):
                error_msg = f"❌ {requirement.key}: 格式无效"
                self.errors.append(error_msg)
                print(error_msg)
                is_valid = False
            else:
                print(f"✅ {requirement.key}: {'已设置' if value else '使用默认值'}")

        # 验证可选配置
        print("\n[可选配置]")
        for key, requirement in self.OPTIONAL_CONFIGS.items():
            value = os.getenv(requirement.key) or requirement.default_value
            self.config_values[key] = value

            if value and requirement.validator and not requirement.validator(value):
                warning_msg = f"⚠️  {requirement.key}: 格式可能无效"
                self.warnings.append(warning_msg)
                print(warning_msg)
            else:
                print(f"✅ {requirement.key}: {value or '默认'}")

        # 打印结果
        print("\n" + "="*60)
        if is_valid:
            print("✅ 配置验证通过")
        else:
            print("❌ 配置验证失败")
        print("="*60 + "\n")

        if not is_valid and raise_on_error:
            self._raise_config_error()

        return is_valid

    def _raise_config_error(self):
        """抛出配置错误"""
        error_msg = "配置验证失败，请检查以下配置项:\n\n"
        for error in self.errors:
            error_msg += f"  • {error}\n"

        if self.warnings:
            error_msg += "\n警告:\n"
            for warning in self.warnings:
                error_msg += f"  • {warning}\n"

        error_msg += "\n请在 .env 文件中设置这些配置项。"
        raise EnvironmentError(error_msg)

    def get_config_summary(self) -> Dict:
        """获取配置摘要"""
        return {
            'total_required': len(self.REQUIRED_CONFIGS),
            'total_optional': len(self.OPTIONAL_CONFIGS),
            'errors': self.errors,
            'warnings': self.warnings,
            'config_values': self.config_values
        }


def validate_startup_config(raise_on_error: bool = True) -> bool:
    """应用启动时验证配置"""
    validator = ConfigValidator()
    return validator.validate_all(raise_on_error)


def main():
    """测试配置验证"""
    import argparse

    parser = argparse.ArgumentParser(description="配置验证工具")
    parser.add_argument("--no-raise", action="store_true", help="不抛出异常")
    args = parser.parse_args()

    try:
        is_valid = validate_startup_config(raise_on_error=not args.no_raise)

        # 输出JSON格式结果
        import json
        from pathlib import Path

        validator = ConfigValidator()
        validator.validate_all(raise_on_error=False)

        summary = validator.get_config_summary()
        output_path = Path('config_validation_result.json')

        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\n验证结果已保存到: {output_path}")

        return 0 if is_valid else 1

    except EnvironmentError as e:
        print(f"\n错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

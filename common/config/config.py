import logging
import os
import ssl
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

# 创建模块级日志记录器
logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """配置相关异常"""
    pass


# =============================================================================
# Pydantic 配置模型定义
# =============================================================================

class AppConfig(BaseModel):
    """应用基础配置"""

    app_name: str = Field(..., description="应用名称")
    app_version: str = Field(..., description="应用版本号")
    env: str = Field(..., description="运行环境（dev/prod/test等）")

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


class WorkflowConfig(BaseModel):
    """工作流配置（包含各种 API 密钥）"""

    anthropic_api_key: str = Field(..., description="Anthropic API 密钥")
    openai_api_key: str = Field(..., description="OpenAI API 密钥")
    exa_api_key: str = Field(..., description="Exa API 密钥")
    twitterapi_api_key: str = Field(..., description="Twitter API 密钥")


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = Field(..., description="日志级别")
    datefmt: str = Field(..., description="日志日期格式")
    format: str = Field(..., description="日志格式")
    colors: str = Field(..., description="日志颜色配置（JSON 格式）")


# =============================================================================
# 配置管理器
# =============================================================================

class ConfigManager:
    """
    配置管理器 - 单例模式

    负责：
    1. 加载环境变量和配置文件
    2. 创建和缓存各种配置对象
    3. 提供类型安全的配置访问接口
    """

    _instance: Optional['ConfigManager'] = None
    _initialized: bool = False

    def __new__(cls) -> 'ConfigManager':
        """确保单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化配置管理器"""
        if not self._initialized:
            self._load_environment()
            self._initialized = True

    def _load_environment(self) -> None:
        """
        加载环境变量

        加载顺序：
        1. .env 通用配置
        2. .env.{env} 环境特定配置
        3. 系统环境变量（最高优先级）
        """
        logger.info("开始加载配置...")

        # 备份系统环境变量
        system_env_backup = dict(os.environ)

        # 获取项目根目录（修改为从项目根目录读取）
        project_root = Path(__file__).resolve().parent.parent.parent

        # 1. 加载通用配置 (.env)
        env_path = project_root / '.env'
        if env_path.exists():
            logger.info(f"加载通用配置: {env_path}")
            load_dotenv(dotenv_path=str(env_path), override=False)
        else:
            logger.warning(f"通用配置文件不存在: {env_path}")

        # 2. 获取当前环境
        env = os.environ.get('ENV')
        if env is None:
            raise ConfigError("缺少必需的环境变量: ENV")
        logger.info(f"当前环境: {env}")

        # 3. 加载环境特定配置
        env_specific_path = project_root / f'.env.{env}'
        if env_specific_path.exists():
            logger.info(f"加载环境特定配置: {env_specific_path}")
            load_dotenv(dotenv_path=str(env_specific_path), override=True)
        else:
            logger.warning(f"环境特定配置文件不存在: {env_specific_path}")

        # 4. 恢复系统环境变量（确保最高优先级）
        os.environ.clear()
        os.environ.update(system_env_backup)
        if env_path.exists():
            load_dotenv(dotenv_path=str(env_path), override=False)
        if (project_root / f'.env.{env}').exists():
            load_dotenv(dotenv_path=str(
                project_root / f'.env.{env}'), override=True)
        os.environ.update(system_env_backup)

        logger.info("配置加载完成")

    @staticmethod
    def _get_env(key: str, default: Optional[str] = None) -> str:
        """
        获取环境变量值

        Args:
            key: 环境变量名
            default: 默认值（如果为 None 则表示必需）

        Returns:
            环境变量值

        Raises:
            ConfigError: 当必需的环境变量缺失时
        """
        value = os.environ.get(key, default)
        if value is None or (not default and value.strip() == ""):
            raise ConfigError(f"缺少必需的环境变量: {key}")
        return value

    @staticmethod
    def _get_env_int(key: str, default: Optional[int] = None) -> int:
        """获取整数类型的环境变量"""
        value = ConfigManager._get_env(
            key, str(default) if default is not None else None)
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ConfigError(f"环境变量 {key} 不是有效的整数: {value}")

    @staticmethod
    def _get_env_bool(key: str, default: Optional[bool] = None) -> bool:
        """获取布尔类型的环境变量"""
        value = ConfigManager._get_env(
            key, str(default).lower() if default is not None else None)
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ConfigError(f"环境变量 {key} 不是有效的布尔值 (true/false): {value}")

    @lru_cache(maxsize=None)
    def get_app_config(self) -> AppConfig:
        """获取应用基础配置"""
        try:
            return AppConfig(
                app_name=self._get_env('APP_NAME'),
                app_version=self._get_env('APP_VERSION'),
                env=self._get_env('ENV')
            )
        except ValidationError as e:
            raise ConfigError(f"应用配置验证失败: {e}")

    @lru_cache(maxsize=None)
    def get_workflow_config(self) -> WorkflowConfig:
        """获取工作流配置"""
        try:
            return WorkflowConfig(
                anthropic_api_key=self._get_env('ANTHROPIC_API_KEY'),
                openai_api_key=self._get_env('OPENAI_API_KEY'),
                exa_api_key=self._get_env('EXA_API_KEY'),
                twitterapi_api_key=self._get_env('TWITTERAPI_API_KEY')
            )
        except ValidationError as e:
            raise ConfigError(f"工作流配置验证失败: {e}")

    @lru_cache(maxsize=None)
    def get_logging_config(self) -> LoggingConfig:
        """获取日志配置"""
        try:
            return LoggingConfig(
                level=self._get_env('LOGGING_LEVEL'),
                datefmt=self._get_env('LOGGING_DATEFMT'),
                format=self._get_env('LOGGING_FORMAT'),
                colors=self._get_env('LOGGING_COLORS')
            )
        except ValidationError as e:
            raise ConfigError(f"日志配置验证失败: {e}")

    def get_health_status(self) -> Dict[str, Any]:
        """
        获取配置健康状态

        Returns:
            包含各个配置项加载状态的字典
        """
        health_status = {
            "initialized": self._initialized,
            "configs": {}
        }

        # 检查各个配置的健康状态
        config_methods = {
            "app_config": self.get_app_config,
            "workflow_config": self.get_workflow_config,
            "logging_config": self.get_logging_config
        }

        for name, method in config_methods.items():
            try:
                method()
                health_status["configs"][name] = {"status": "ok"}
            except ConfigError as e:
                health_status["configs"][name] = {
                    "status": "error",
                    "message": str(e)
                }

        # 计算整体健康状态
        all_ok = all(cfg["status"] ==
                     "ok" for cfg in health_status["configs"].values())
        health_status["overall_status"] = "healthy" if all_ok else "unhealthy"

        return health_status

    def print_config(self) -> None:
        """打印当前配置信息（隐藏敏感信息）"""
        print("\n" + "=" * 50)
        print("配置信息")
        print("=" * 50)

        try:
            app_config = self.get_app_config()
            print(f"环境: {app_config.env}")
            print(f"应用名称: {app_config.app_name}")
            print(f"应用版本: {app_config.app_version}")
        except ConfigError:
            print("无法加载应用配置")

        print("=" * 50)

        # 打印环境变量（隐藏敏感信息）
        sensitive_keywords = ["PASSWORD",
                              "SECRET", "KEY", "TOKEN", "CREDENTIAL"]
        for key in sorted(os.environ.keys()):
            if key.isupper():
                value = os.environ[key]
                is_sensitive = any(
                    keyword in key for keyword in sensitive_keywords)
                if is_sensitive and value:
                    print(f"{key}: {value[:4]}***")
                else:
                    print(f"{key}: {value}")

        print("=" * 50 + "\n")


# =============================================================================
# 全局配置实例
# =============================================================================

# 创建全局配置管理器实例
config_manager = ConfigManager()

# 导出便捷访问函数


def get_app_config() -> AppConfig:
    """获取应用配置"""
    return config_manager.get_app_config()


def get_workflow_config() -> WorkflowConfig:
    """获取工作流配置"""
    return config_manager.get_workflow_config()


def get_logging_config() -> LoggingConfig:
    """获取日志配置"""
    return config_manager.get_logging_config()


# 导出公共接口
__all__ = [
    # 异常类
    'ConfigError',

    # 配置管理器
    'ConfigManager',
    'config_manager',

    # Pydantic 模型
    'AppConfig',
    'WorkflowConfig',
    'LoggingConfig',

    # 便捷函数
    'get_app_config',
    'get_workflow_config',
    'get_logging_config',
]

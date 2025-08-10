import logging
import os
import ssl
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

# Create module-level logger
logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration related exception"""
    pass


# =============================================================================
# Pydantic Configuration Model Definitions
# =============================================================================

class AppConfig(BaseModel):
    """Application base configuration"""

    app_name: str = Field(..., description="Application name")
    app_version: str = Field(..., description="Application version")
    env: str = Field(..., description="Runtime environment (dev/prod/test etc.)")

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }


class WorkflowConfig(BaseModel):
    """Workflow configuration containing API keys"""

    openai_api_key: str = Field(..., description="OpenAI API key")


class LoggingConfig(BaseModel):
    """Logging configuration"""

    level: str = Field(..., description="Log level")
    datefmt: str = Field(..., description="Log date format")
    format: str = Field(..., description="Log format")
    colors: str = Field(..., description="Log color configuration (JSON format)")


# =============================================================================
# Configuration Manager
# =============================================================================

class ConfigManager:
    """
    Configuration Manager - Singleton Pattern

    Responsibilities:
    1. Load environment variables and configuration files
    2. Create and cache various configuration objects
    3. Provide type-safe configuration access interface
    """

    _instance: Optional['ConfigManager'] = None
    _initialized: bool = False

    def __new__(cls) -> 'ConfigManager':
        """Ensure singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize configuration manager"""
        if not self._initialized:
            self._load_environment()
            self._initialized = True

    def _load_environment(self) -> None:
        """
        Load environment variables

        Loading order:
        1. .env general configuration
        2. .env.{env} environment-specific configuration
        3. System environment variables (highest priority)
        """
        logger.info("Starting to load configuration...")

        # Backup system environment variables
        system_env_backup = dict(os.environ)

        # Get project root directory (modified to read from project root)
        project_root = Path(__file__).resolve().parent.parent.parent

        # 1. Load general configuration (.env)
        env_path = project_root / '.env'
        if env_path.exists():
            logger.info(f"Loading general configuration: {env_path}")
            load_dotenv(dotenv_path=str(env_path), override=False)
        else:
            logger.warning(f"General configuration file does not exist: {env_path}")

        # 2. Get current environment
        env = os.environ.get('ENV')
        if env is None:
            raise ConfigError("Missing required environment variable: ENV")
        logger.info(f"Current environment: {env}")

        # 3. Load environment-specific configuration
        env_specific_path = project_root / f'.env.{env}'
        if env_specific_path.exists():
            logger.info(f"Loading environment-specific configuration: {env_specific_path}")
            load_dotenv(dotenv_path=str(env_specific_path), override=True)
        else:
            logger.warning(f"Environment-specific configuration file does not exist: {env_specific_path}")

        # 4. Restore system environment variables (ensure highest priority)
        os.environ.clear()
        os.environ.update(system_env_backup)
        if env_path.exists():
            load_dotenv(dotenv_path=str(env_path), override=False)
        if (project_root / f'.env.{env}').exists():
            load_dotenv(dotenv_path=str(
                project_root / f'.env.{env}'), override=True)
        os.environ.update(system_env_backup)

        logger.info("Configuration loading completed")

    @staticmethod
    def _get_env(key: str, default: Optional[str] = None) -> str:
        """
        Get environment variable value

        Args:
            key: Environment variable name
            default: Default value (None means required)

        Returns:
            Environment variable value

        Raises:
            ConfigError: When required environment variable is missing
        """
        value = os.environ.get(key, default)
        if value is None or (not default and value.strip() == ""):
            raise ConfigError(f"Missing required environment variable: {key}")
        return value

    @staticmethod
    def _get_env_int(key: str, default: Optional[int] = None) -> int:
        """Get integer type environment variable"""
        value = ConfigManager._get_env(
            key, str(default) if default is not None else None)
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ConfigError(f"Environment variable {key} is not a valid integer: {value}")

    @staticmethod
    def _get_env_bool(key: str, default: Optional[bool] = None) -> bool:
        """Get boolean type environment variable"""
        value = ConfigManager._get_env(
            key, str(default).lower() if default is not None else None)
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ConfigError(f"Environment variable {key} is not a valid boolean (true/false): {value}")

    @lru_cache(maxsize=None)
    def get_app_config(self) -> AppConfig:
        """Get application base configuration"""
        try:
            return AppConfig(
                app_name=self._get_env('APP_NAME'),
                app_version=self._get_env('APP_VERSION'),
                env=self._get_env('ENV')
            )
        except ValidationError as e:
            raise ConfigError(f"Application configuration validation failed: {e}")

    @lru_cache(maxsize=None)
    def get_workflow_config(self) -> WorkflowConfig:
        """Get workflow configuration"""
        try:
            return WorkflowConfig(
                openai_api_key=self._get_env('OPENAI_API_KEY')
            )
        except ValidationError as e:
            raise ConfigError(f"Workflow configuration validation failed: {e}")

    @lru_cache(maxsize=None)
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration"""
        try:
            return LoggingConfig(
                level=self._get_env('LOGGING_LEVEL'),
                datefmt=self._get_env('LOGGING_DATEFMT'),
                format=self._get_env('LOGGING_FORMAT'),
                colors=self._get_env('LOGGING_COLORS')
            )
        except ValidationError as e:
            raise ConfigError(f"Logging configuration validation failed: {e}")

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get configuration health status

        Returns:
            Dictionary containing the loading status of each configuration item
        """
        health_status = {
            "initialized": self._initialized,
            "configs": {}
        }

        # Check health status of each configuration
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

        # Calculate overall health status
        all_ok = all(cfg["status"] ==
                     "ok" for cfg in health_status["configs"].values())
        health_status["overall_status"] = "healthy" if all_ok else "unhealthy"

        return health_status

    def print_config(self) -> None:
        """Print current configuration information (hide sensitive information)"""
        print("\n" + "=" * 50)
        print("Configuration Information")
        print("=" * 50)

        try:
            app_config = self.get_app_config()
            print(f"Environment: {app_config.env}")
            print(f"Application Name: {app_config.app_name}")
            print(f"Application Version: {app_config.app_version}")
        except ConfigError:
            print("Unable to load application configuration")

        print("=" * 50)

        # Print environment variables (hide sensitive information)
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
# Global Configuration Instance
# =============================================================================

# Create global configuration manager instance
config_manager = ConfigManager()

# Export convenience access functions


def get_app_config() -> AppConfig:
    """Get application configuration"""
    return config_manager.get_app_config()


def get_workflow_config() -> WorkflowConfig:
    """Get workflow configuration"""
    return config_manager.get_workflow_config()


def get_logging_config() -> LoggingConfig:
    """Get logging configuration"""
    return config_manager.get_logging_config()


# Export public interface
__all__ = [
    # Exception classes
    'ConfigError',

    # Configuration manager
    'ConfigManager',
    'config_manager',

    # Pydantic models
    'AppConfig',
    'WorkflowConfig',
    'LoggingConfig',

    # Convenience functions
    'get_app_config',
    'get_workflow_config',
    'get_logging_config',
]

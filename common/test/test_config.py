import os
import unittest

from common.config.config import (
    ConfigManager,
    get_app_config,
    get_logging_config,
    get_workflow_config,
)


class TestConfigPrint(unittest.TestCase):
    """Test whether configuration can be loaded and printed correctly"""

    @classmethod
    def setUpClass(cls):
        """Set up environment before all tests"""
        # Intelligently select available environment
        import pathlib
        project_root = pathlib.Path(__file__).resolve().parent.parent.parent

        # Check available environment files
        available_envs = []
        for env_file in project_root.glob('.env.*'):
            if not env_file.name.endswith('.template'):
                env_name = env_file.name.replace('.env.', '')
                available_envs.append(env_name)

        # Prefer local, then dev, finally the first available
        env_to_use = None
        if 'local' in available_envs:
            env_to_use = 'local'
        elif 'dev' in available_envs:
            env_to_use = 'dev'
        elif available_envs:
            env_to_use = available_envs[0]

        if env_to_use:
            os.environ['ENV'] = env_to_use
            print(f"Test using environment: {env_to_use} (detected environment files: {available_envs})")
        else:
            print("Warning: No environment files found, using default configuration")

        print(f"After configuration loading, ENV = {os.environ.get('ENV')}")

    def test_print_all_configs(self):
        """Test printing all available configurations"""
        print("\n" + "="*80)
        print("Configuration Test - Print All Configuration Information")
        print("="*80)

        # Test application configuration
        try:
            app_config = get_app_config()
            print(f"\n✓ Application Configuration:")
            print(f"  Application Name: {app_config.app_name}")
            print(f"  Version: {app_config.app_version}")
            print(f"  Environment: {app_config.env}")
        except Exception as e:
            print(f"✗ Application configuration loading failed: {e}")

        # Test logging configuration
        try:
            logging_config = get_logging_config()
            print(f"\n✓ Logging Configuration:")
            print(f"  Level: {logging_config.level}")
            print(f"  Format: {logging_config.format}")
            print(f"  Date Format: {logging_config.datefmt}")
            print(f"  Color Configuration: {logging_config.colors[:50]}...")
        except Exception as e:
            print(f"✗ Logging configuration loading failed: {e}")

        # Test workflow configuration
        try:
            workflow_config = get_workflow_config()
            print(f"\n✓ Workflow Configuration:")
            print(f"  OpenAI API: {workflow_config.openai_api_key[:15]}...")
        except Exception as e:
            print(f"✗ Workflow configuration loading failed: {e}")

        print("\n" + "="*80)
        print("Configuration Test Completed")
        print("="*80)

    def test_config_health_check(self):
        """Test configuration health check"""
        print("\n" + "="*80)
        print("Configuration Health Check")
        print("="*80)

        manager = ConfigManager()
        health = manager.get_health_status()

        print(f"Configuration manager initialized: {health['initialized']}")
        print(f"Overall status: {health['overall_status']}")

        print("\nEach configuration item status:")
        for config_name, status in health['configs'].items():
            status_symbol = "✓" if status['status'] == 'ok' else "✗"
            print(f"  {status_symbol} {config_name}: {status['status']}")
            if status['status'] != 'ok' and 'message' in status:
                print(f"    Error message: {status['message']}")

        print("="*80)

    def test_print_config_summary(self):
        """Test printing configuration summary"""
        print("\n" + "="*80)
        print("Configuration Summary Print Test")
        print("="*80)

        manager = ConfigManager()
        manager.print_config()

        print("="*80)
        print("Configuration Summary Print Completed")
        print("="*80)


if __name__ == '__main__':
    unittest.main()

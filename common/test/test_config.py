import os
import unittest

from common.config.config import (
    ConfigManager,
    get_app_config,
    get_logging_config,
    get_workflow_config,
)


class TestConfigPrint(unittest.TestCase):
    """测试配置能否正确加载和打印"""

    @classmethod
    def setUpClass(cls):
        """在所有测试之前设置环境"""
        # 智能选择可用的环境
        import pathlib
        project_root = pathlib.Path(__file__).resolve().parent.parent.parent

        # 检查可用的环境文件
        available_envs = []
        for env_file in project_root.glob('.env.*'):
            if not env_file.name.endswith('.template'):
                env_name = env_file.name.replace('.env.', '')
                available_envs.append(env_name)

        # 优先选择 local，然后是 dev，最后是第一个可用的
        env_to_use = None
        if 'local' in available_envs:
            env_to_use = 'local'
        elif 'dev' in available_envs:
            env_to_use = 'dev'
        elif available_envs:
            env_to_use = available_envs[0]

        if env_to_use:
            os.environ['ENV'] = env_to_use
            print(f"测试使用环境: {env_to_use} (检测到环境文件: {available_envs})")
        else:
            print("警告: 未找到任何环境文件，使用默认配置")

        print(f"配置加载后，ENV = {os.environ.get('ENV')}")

    def test_print_all_configs(self):
        """测试打印所有可用的配置"""
        print("\n" + "="*80)
        print("配置测试 - 打印所有配置信息")
        print("="*80)

        # 测试应用配置
        try:
            app_config = get_app_config()
            print(f"\n✓ 应用配置:")
            print(f"  应用名称: {app_config.app_name}")
            print(f"  版本: {app_config.app_version}")
            print(f"  环境: {app_config.env}")
        except Exception as e:
            print(f"✗ 应用配置加载失败: {e}")

        # 测试日志配置
        try:
            logging_config = get_logging_config()
            print(f"\n✓ 日志配置:")
            print(f"  级别: {logging_config.level}")
            print(f"  格式: {logging_config.format}")
            print(f"  日期格式: {logging_config.datefmt}")
            print(f"  颜色配置: {logging_config.colors[:50]}...")
        except Exception as e:
            print(f"✗ 日志配置加载失败: {e}")

        # 测试工作流配置
        try:
            workflow_config = get_workflow_config()
            print(f"\n✓ 工作流配置:")
            print(
                f"  Anthropic API: {workflow_config.anthropic_api_key[:15]}...")
            print(f"  OpenAI API: {workflow_config.openai_api_key[:15]}...")
            print(f"  Exa API: {workflow_config.exa_api_key[:15]}...")
            print(
                f"  Twitter API: {workflow_config.twitterapi_api_key[:15]}...")
        except Exception as e:
            print(f"✗ 工作流配置加载失败: {e}")

        print("\n" + "="*80)
        print("配置测试完成")
        print("="*80)

    def test_config_health_check(self):
        """测试配置健康检查"""
        print("\n" + "="*80)
        print("配置健康检查")
        print("="*80)

        manager = ConfigManager()
        health = manager.get_health_status()

        print(f"配置管理器已初始化: {health['initialized']}")
        print(f"整体状态: {health['overall_status']}")

        print("\n各配置项状态:")
        for config_name, status in health['configs'].items():
            status_symbol = "✓" if status['status'] == 'ok' else "✗"
            print(f"  {status_symbol} {config_name}: {status['status']}")
            if status['status'] != 'ok' and 'message' in status:
                print(f"    错误信息: {status['message']}")

        print("="*80)

    def test_print_config_summary(self):
        """测试打印配置摘要"""
        print("\n" + "="*80)
        print("配置摘要打印测试")
        print("="*80)

        manager = ConfigManager()
        manager.print_config()

        print("="*80)
        print("配置摘要打印完成")
        print("="*80)


if __name__ == '__main__':
    unittest.main()

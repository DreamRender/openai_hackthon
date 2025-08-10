import os
import unittest

from common.utils.logger import get_logger


class TestLoggerPrint(unittest.TestCase):
    """测试日志记录器功能 - 重点是能否正常打印日志"""

    @classmethod
    def setUpClass(cls):
        """在所有测试之前设置环境"""
        # 确保ENV设置为local，以便加载.env和.env.local
        os.environ['ENV'] = 'local'

    def test_logger_basic_functionality(self):
        """测试日志记录器基本功能 - 能否正常打印不同级别的日志"""
        print("\n" + "="*80)
        print("日志记录器测试 - 基本功能")
        print("="*80)
        
        # 创建几个不同名称的logger
        loggers = [
            ('app_logger', get_logger('app')),
            ('service_logger', get_logger('service')),
            ('worker_logger', get_logger('worker'))
        ]
        
        for logger_name, logger in loggers:
            print(f"\n✓ 测试 {logger_name}:")
            print(f"  Logger名称: {logger.name}")
            print(f"  Logger级别: {logger.level}")
            print(f"  Handler数量: {len(logger.handlers)}")
            print(f"  传播设置: {logger.propagate}")
            
            # 测试不同级别的日志输出
            print(f"  日志输出测试:")
            logger.debug(f"这是来自 {logger_name} 的调试信息")
            logger.info(f"这是来自 {logger_name} 的信息日志")
            logger.warning(f"这是来自 {logger_name} 的警告日志")
            logger.error(f"这是来自 {logger_name} 的错误日志")
            logger.critical(f"这是来自 {logger_name} 的严重错误日志")
        
        print("\n" + "="*80)
        print("基本功能测试完成")
        print("="*80)

    def test_logger_duplicate_prevention(self):
        """测试重复创建相同名称的logger不会重复添加handler"""
        print("\n" + "="*80)
        print("日志记录器测试 - 重复创建防护")
        print("="*80)
        
        # 创建相同名称的logger多次
        logger1 = get_logger('duplicate_test')
        logger2 = get_logger('duplicate_test')
        logger3 = get_logger('duplicate_test')
        
        print(f"✓ 创建了3次名为 'duplicate_test' 的logger")
        print(f"  是否为同一实例: {logger1 is logger2 and logger2 is logger3}")
        print(f"  Handler数量: {len(logger1.handlers)}")
        print(f"  测试日志输出:")
        
        logger1.info("第一个logger的消息")
        logger2.warning("第二个logger的消息")
        logger3.error("第三个logger的消息")
        
        print("\n" + "="*80)
        print("重复创建防护测试完成")
        print("="*80)

    def test_logger_with_different_names(self):
        """测试创建不同名称的logger"""
        print("\n" + "="*80)
        print("日志记录器测试 - 不同名称的logger")
        print("="*80)
        
        # 创建不同名称的logger
        logger_configs = [
            ('database', 'debug'),
            ('api', 'info'),
            ('auth', 'warning'),
            ('cache', 'error')
        ]
        
        for name, test_level in logger_configs:
            logger = get_logger(name)
            print(f"\n✓ Logger '{name}':")
            print(f"  名称: {logger.name}")
            print(f"  配置级别: {logger.level}")
            print(f"  测试消息 ({test_level}):")
            
            # 根据测试级别输出相应的日志
            if test_level == 'debug':
                logger.debug(f"调试消息来自 {name} logger")
            elif test_level == 'info':
                logger.info(f"信息消息来自 {name} logger")
            elif test_level == 'warning':
                logger.warning(f"警告消息来自 {name} logger")
            elif test_level == 'error':
                logger.error(f"错误消息来自 {name} logger")
        
        print("\n" + "="*80)
        print("不同名称logger测试完成")
        print("="*80)

    def test_logger_error_handling(self):
        """测试日志记录器的异常处理"""
        print("\n" + "="*80)
        print("日志记录器测试 - 异常处理")
        print("="*80)
        
        logger = get_logger('error_test')
        
        # 测试记录异常信息
        try:
            # 故意触发一个异常
            _ = 10 / 0
        except ZeroDivisionError as e:
            print("✓ 捕获到除零异常，测试异常日志记录:")
            logger.error(f"捕获到异常: {e}")
            logger.exception("使用exception方法记录异常（包含堆栈跟踪）:")
        
        # 测试记录复杂对象
        complex_data = {
            'user_id': 12345,
            'action': 'login',
            'timestamp': '2024-01-01T10:00:00Z',
            'metadata': {
                'ip': '192.168.1.1',
                'user_agent': 'Mozilla/5.0...'
            }
        }
        
        print("\n✓ 测试记录复杂数据:")
        logger.info(f"用户操作记录: {complex_data}")
        
        print("\n" + "="*80)
        print("异常处理测试完成")
        print("="*80)


if __name__ == '__main__':
    unittest.main()
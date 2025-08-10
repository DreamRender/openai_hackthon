import os
import unittest

from common.utils.logger import get_logger


class TestLoggerPrint(unittest.TestCase):
    """Test logger functionality - focus on whether logs can be printed normally"""

    @classmethod
    def setUpClass(cls):
        """Set up environment before all tests"""
        # Ensure ENV is set to local to load .env and .env.local
        os.environ['ENV'] = 'local'

    def test_logger_basic_functionality(self):
        """Test basic logger functionality - whether logs of different levels can be printed normally"""
        print("\n" + "="*80)
        print("Logger Test - Basic Functionality")
        print("="*80)
        
        # Create several loggers with different names
        loggers = [
            ('app_logger', get_logger('app')),
            ('service_logger', get_logger('service')),
            ('worker_logger', get_logger('worker'))
        ]
        
        for logger_name, logger in loggers:
            print(f"\n✓ Testing {logger_name}:")
            print(f"  Logger Name: {logger.name}")
            print(f"  Logger Level: {logger.level}")
            print(f"  Handler Count: {len(logger.handlers)}")
            print(f"  Propagate Setting: {logger.propagate}")
            
            # Test log output of different levels
            print(f"  Log Output Test:")
            logger.debug(f"This is debug information from {logger_name}")
            logger.info(f"This is info log from {logger_name}")
            logger.warning(f"This is warning log from {logger_name}")
            logger.error(f"This is error log from {logger_name}")
            logger.critical(f"This is critical error log from {logger_name}")
        
        print("\n" + "="*80)
        print("Basic Functionality Test Completed")
        print("="*80)

    def test_logger_duplicate_prevention(self):
        """Test that creating duplicate loggers with the same name will not add handlers repeatedly"""
        print("\n" + "="*80)
        print("Logger Test - Duplicate Creation Prevention")
        print("="*80)
        
        # Create logger with same name multiple times
        logger1 = get_logger('duplicate_test')
        logger2 = get_logger('duplicate_test')
        logger3 = get_logger('duplicate_test')
        
        print(f"✓ Created logger named 'duplicate_test' 3 times")
        print(f"  Are they the same instance: {logger1 is logger2 and logger2 is logger3}")
        print(f"  Handler Count: {len(logger1.handlers)}")
        print(f"  Test Log Output:")
        
        logger1.info("Message from first logger")
        logger2.warning("Message from second logger")
        logger3.error("Message from third logger")
        
        print("\n" + "="*80)
        print("Duplicate Creation Prevention Test Completed")
        print("="*80)

    def test_logger_with_different_names(self):
        """Test creating loggers with different names"""
        print("\n" + "="*80)
        print("Logger Test - Loggers with Different Names")
        print("="*80)
        
        # Create loggers with different names
        logger_configs = [
            ('database', 'debug'),
            ('api', 'info'),
            ('auth', 'warning'),
            ('cache', 'error')
        ]
        
        for name, test_level in logger_configs:
            logger = get_logger(name)
            print(f"\n✓ Logger '{name}':")
            print(f"  Name: {logger.name}")
            print(f"  Configuration Level: {logger.level}")
            print(f"  Test Message ({test_level}):")
            
            # Output corresponding log based on test level
            if test_level == 'debug':
                logger.debug(f"Debug message from {name} logger")
            elif test_level == 'info':
                logger.info(f"Info message from {name} logger")
            elif test_level == 'warning':
                logger.warning(f"Warning message from {name} logger")
            elif test_level == 'error':
                logger.error(f"Error message from {name} logger")
        
        print("\n" + "="*80)
        print("Different Names Logger Test Completed")
        print("="*80)

    def test_logger_error_handling(self):
        """Test exception handling of logger"""
        print("\n" + "="*80)
        print("Logger Test - Exception Handling")
        print("="*80)
        
        logger = get_logger('error_test')
        
        # Test logging exception information
        try:
            # Intentionally trigger an exception
            _ = 10 / 0
        except ZeroDivisionError as e:
            print("✓ Caught division by zero exception, testing exception logging:")
            logger.error(f"Caught exception: {e}")
            logger.exception("Using exception method to log exception (including stack trace):")
        
        # Test logging complex objects
        complex_data = {
            'user_id': 12345,
            'action': 'login',
            'timestamp': '2024-01-01T10:00:00Z',
            'metadata': {
                'ip': '192.168.1.1',
                'user_agent': 'Mozilla/5.0...'
            }
        }
        
        print("\n✓ Test logging complex data:")
        logger.info(f"User operation record: {complex_data}")
        
        print("\n" + "="*80)
        print("Exception Handling Test Completed")
        print("="*80)


if __name__ == '__main__':
    unittest.main()
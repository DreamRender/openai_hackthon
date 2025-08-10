import logging
import sys
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取配置好的 logger 实例
    
    Args:
        name: logger 名称，默认使用调用模块的名称
        
    Returns:
        logging.Logger: 配置好的 logger 实例
    """
    logger = logging.getLogger(name or __name__)
    
    # 如果 logger 已经有 handler，则直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    logger.setLevel(logging.INFO)
    
    # 创建控制台 handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # 添加 handler 到 logger
    logger.addHandler(handler)
    
    return logger


# 创建默认 logger 实例
usebase_logger = get_logger('workflow')
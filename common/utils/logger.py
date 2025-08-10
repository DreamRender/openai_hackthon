import json

import colorlog

from common.config.config import get_logging_config


def get_logger(name: str):
    """
    获取一个基于配置的彩色日志记录器

    参数:
        name: 日志记录器名称

    返回:
        配置好的彩色Logger实例
    """
    # 获取日志配置
    logging_config = get_logging_config()

    # 从配置中读取级别、格式和日期格式
    log_level = logging_config.level
    log_format = logging_config.format
    date_format = logging_config.datefmt
    log_colors = logging_config.colors
    if log_colors:
        try:
            log_colors = json.loads(log_colors)
        except json.JSONDecodeError:
            log_colors = None
    else:
        log_colors = None

    # 创建Logger
    logger = colorlog.getLogger(name)

    # 防止重复添加handler
    if logger.handlers:
        return logger

    if not log_level:
        log_level = 'DEBUG'
        print(f"警告！日志级别未配置，使用默认值: {log_level}")

    # 设置日志级别
    logger.setLevel(log_level)

    # 创建处理器
    handler = colorlog.StreamHandler()

    # 创建格式化器
    formatter = colorlog.ColoredFormatter(
        log_format,
        datefmt=date_format,
        log_colors=log_colors,
        reset=True
    )

    # 设置格式化器
    handler.setFormatter(formatter)

    # 添加处理器
    logger.addHandler(handler)

    # 禁止向上传播日志消息到父日志器
    logger.propagate = False

    return logger
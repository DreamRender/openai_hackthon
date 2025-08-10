import json

import colorlog

from common.config.config import get_logging_config


def get_logger(name: str):
    """
    Get a color logger based on configuration

    Args:
        name: Logger name

    Returns:
        Configured color Logger instance
    """
    # Get logging configuration
    logging_config = get_logging_config()

    # Read level, format and date format from configuration
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

    # Create Logger
    logger = colorlog.getLogger(name)

    # Prevent duplicate handler addition
    if logger.handlers:
        return logger

    if not log_level:
        log_level = 'DEBUG'
        print(f"Warning! Log level not configured, using default value: {log_level}")

    # Set log level
    logger.setLevel(log_level)

    # Create handler
    handler = colorlog.StreamHandler()

    # Create formatter
    formatter = colorlog.ColoredFormatter(
        log_format,
        datefmt=date_format,
        log_colors=log_colors,
        reset=True
    )

    # Set formatter
    handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(handler)

    # Disable propagating log messages to parent logger
    logger.propagate = False

    return logger
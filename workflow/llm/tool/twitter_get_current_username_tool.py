"""
Twitter 获取当前用户名工具模块。

本模块为 LiteLLM 提供了获取当前登录 Twitter 用户用户名的工具定义。
工具会返回当前登录用户的用户名字符串。
"""

from common.utils.logger import get_logger

logger = get_logger(__name__)
"""日志记录器实例，用于记录模块运行时的日志信息。"""

# LiteLLM 工具定义
twitter_get_current_username_tool_definition = {
    "type": "function",
    "function": {
        "name": "twitter_get_current_username",
        "description": "Get the username of the currently authenticated Twitter user.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}
"""
LiteLLM 工具定义字典。

定义了 twitter_get_current_username 工具的结构，包括：
- type: 工具类型，固定为 "function"
- function: 包含函数名称、描述和参数定义
- name: 工具名称
- description: 工具功能描述（英文）
- parameters: 参数 schema，无需参数
"""


async def twitter_get_current_username() -> str:
    """
    获取当前登录 Twitter 用户的用户名。

    该函数会获取当前登录用户的用户名信息并返回。

    Returns:
        str: 当前用户名（不包含@符号）。

    Examples:
        >>> # 获取当前用户的用户名
        >>> username = await twitter_get_current_username()
        >>> print(f"当前登录用户: @{username}")
        当前登录用户: @KerryKonWang

    Note:
        - 返回的用户名是当前的用户名，可能与用户创建账号时不同
    """
    # 获取当前用户名
    username = "KerryKonWang"
    """当前用户名，不包含@符号的纯用户名字符串。"""

    logger.info(f"获取到当前用户名: @{username}")
    return username


# 导出工具定义和函数，供其他模块使用
__all__ = [
    "twitter_get_current_username_tool_definition",
    "twitter_get_current_username",
]
"""
模块导出列表。

包含：
- twitter_get_current_username_tool_definition: LiteLLM 工具定义
- twitter_get_current_username: 获取当前用户名的异步函数
"""

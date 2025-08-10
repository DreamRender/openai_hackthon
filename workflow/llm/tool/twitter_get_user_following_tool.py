"""
Twitter 获取用户关注列表工具模块。

本模块为 LiteLLM 提供了获取 Twitter 用户关注列表的工具定义。
工具会返回指定用户关注的所有用户的用户名列表。
"""

from typing import List, Optional

from workflow.service.twitter_service import TwitterService
from common.utils.logger import get_logger

logger = get_logger(__name__)
"""日志记录器实例，用于记录模块运行时的日志信息。"""

# LiteLLM 工具定义
twitter_get_user_following_tool_definition = {
    "type": "function",
    "function": {
        "name": "twitter_get_user_following",
        "description": "Get the list of all usernames that a specified Twitter user is following. Returns a list of usernames (without @ symbol) for all accounts the target user follows.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "The Twitter username to query (without @ symbol). For example: 'elonmusk', 'openai', etc.",
                }
            },
            "required": ["username"],
        },
    },
}
"""
LiteLLM 工具定义字典。

定义了 twitter_get_user_following 工具的结构，包括：
- type: 工具类型，固定为 "function"
- function: 包含函数名称、描述和参数定义
- name: 工具名称
- description: 工具功能描述（英文）
- parameters: 参数 schema，包含 username 参数的定义
"""


async def twitter_get_user_following(username: str) -> Optional[List[str]]:
    """
    获取 Twitter 用户关注的所有用户的用户名列表。

    该函数是对 TwitterService.get_following() 的包装，专门为 LiteLLM 工具调用设计。
    它会获取指定用户关注的所有用户信息，并提取出用户名列表返回。

    Args:
        username (str): 要查询的 Twitter 用户名（不包含@符号）。
                       示例: "elonmusk", "openai", "nasa" 等。

    Returns:
        Optional[List[str]]: 成功时返回用户名列表，失败时返回 None。
                            - 列表中的每个元素都是一个用户名字符串（不包含@符号）
                            - 列表按照 API 返回的顺序排列（通常是按关注时间倒序）
                            - 如果用户没有关注任何人，返回空列表 []
                            - 如果发生错误（如用户不存在、API 限制等），返回 None

    Raises:
        无异常抛出，所有异常都在内部处理并记录日志。

    Examples:
        >>> # 获取 Elon Musk 关注的所有用户
        >>> following_list = await twitter_get_user_following("elonmusk")
        >>> if following_list is not None:
        ...     print(f"Elon Musk 关注了 {len(following_list)} 个用户")
        ...     for username in following_list[:10]:  # 打印前10个
        ...         print(f"- @{username}")
        ... else:
        ...     print("获取关注列表失败")

    Note:
        - 该函数需要有效的 Twitter API 配置（在 workflow_config 中设置）
        - API 有速率限制，频繁调用可能会被限制
        - 获取大量关注者可能需要较长时间（需要多次 API 调用）
        - 返回的用户名是当前的用户名，可能与用户创建账号时不同
    """
    try:
        # 创建 Twitter 服务实例
        twitter_service = TwitterService()

        # 调用服务获取关注列表，获取所有关注的用户
        logger.info(f"正在获取用户 @{username} 的完整关注列表")
        following_response = await twitter_service.get_following(
            username=username, max_results=999999  # 获取所有关注者
        )

        # 检查响应
        if following_response is None:
            logger.warning(f"获取用户 @{username} 的关注列表失败：API 返回 None")
            return None

        # 提取用户名列表
        usernames: List[str] = [
            user.username
            for user in following_response.users
            if user.username is not None
        ]
        """从响应中提取的用户名列表，每个元素都是不包含@符号的用户名字符串。"""

        logger.info(
            f"成功获取用户 @{username} 的关注列表，"
            f"共 {len(usernames)} 个用户（总关注数: {following_response.total_count}）"
        )

        return usernames

    except Exception as e:
        logger.error(f"获取用户 @{username} 的关注列表时发生异常: {str(e)}")
        return None


# 导出工具定义和函数，供其他模块使用
__all__ = ["twitter_get_user_following_tool_definition", "twitter_get_user_following"]
"""
模块导出列表。

包含：
- twitter_get_user_following_tool_definition: LiteLLM 工具定义
- twitter_get_user_following: 获取用户关注列表的异步函数
"""

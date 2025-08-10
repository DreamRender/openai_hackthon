"""
Twitter 获取用户关注列表工具的测试模块。

运行命令：
    poetry run python -m workflow.test.tool.test_twitter_get_user_following_tool
"""

from typing import Dict, Any, List, Optional

from workflow.test.tool.base_tool_test import BaseToolTest, create_test_runner
from workflow.llm.tool.twitter_get_user_following_tool import (
    twitter_get_user_following_tool_definition,
    twitter_get_user_following,
)
from common.utils.logger import get_logger

logger = get_logger(__name__)


class TwitterGetUserFollowingToolTest(BaseToolTest):
    """
    Twitter 获取用户关注列表工具的测试类。

    继承自 BaseToolTest，实现了所有必要的方法来测试
    twitter_get_user_following 工具的功能。
    """

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        获取工具定义列表。

        Returns:
            List[Dict[str, Any]]: 包含 twitter_get_user_following 工具定义的列表
        """
        return [twitter_get_user_following_tool_definition]

    def get_test_prompt(self) -> str:
        """
        获取测试提示。

        Returns:
            str: 用于触发工具调用的测试提示
        """
        return "请帮我获取 KerryKonWang 关注的所有用户，并全部列出来，不要省略"

    async def execute_tool_function(self, tool_name: str, args: Dict[str, Any]) -> None:
        """
        执行工具函数。

        Args:
            tool_name (str): 工具名称
            args (Dict[str, Any]): 包含工具参数的字典，应包含 'username' 键
        """
        # 根据工具名称执行相应的工具函数
        if tool_name == "twitter_get_user_following":
            username: str = args.get("username", "")
            """要查询的 Twitter 用户名。"""

            logger.info(f"正在获取用户 {username} 的关注列表")

            result: Optional[List[str]] = await twitter_get_user_following(username)
            """工具函数返回的用户名列表。"""

            if result is not None:
                logger.info(f"成功获取 {len(result)} 个关注的用户")

                # 输出用户列表
                for i, name in enumerate(result, 1):
                    logger.info(f"{i:4d}. @{name}")

                logger.info(f"总计: {len(result)} 个用户")
            else:
                logger.error(f"获取用户 {username} 的关注列表失败")
        else:
            logger.error(f"未知的工具名称: {tool_name}")

    def get_test_name(self) -> str:
        """
        获取测试名称。

        Returns:
            str: 测试的显示名称
        """
        return "Twitter 获取用户关注列表工具"


# 运行命令：poetry run python -m workflow.test.tool.test_twitter_get_user_following_tool
if __name__ == "__main__":
    create_test_runner(TwitterGetUserFollowingToolTest)

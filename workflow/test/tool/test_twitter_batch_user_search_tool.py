"""
Twitter 批量用户搜索工具的测试模块。

运行命令：
    poetry run python -m workflow.test.tool.test_twitter_batch_user_search_tool
"""

from typing import Dict, Any, List, Optional

from workflow.test.tool.base_tool_test import BaseToolTest, create_test_runner
from workflow.llm.tool.twitter_batch_user_search_tool import (
    twitter_batch_user_search_tool_definition,
    twitter_batch_user_search,
)
from common.utils.logger import get_logger

logger = get_logger(__name__)


class TwitterBatchUserSearchToolTest(BaseToolTest):
    """
    Twitter 批量用户搜索工具的测试类。

    继承自 BaseToolTest，实现了所有必要的方法来测试
    twitter_batch_user_search 工具的功能。
    """

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        获取工具定义列表。

        Returns:
            List[Dict[str, Any]]: 包含 twitter_batch_user_search 工具定义的列表
        """
        return [twitter_batch_user_search_tool_definition]

    def get_test_prompt(self) -> str:
        """
        获取测试提示。

        Returns:
            str: 用于触发工具调用的测试提示
        """
        return "请帮我批量搜索 elonmusk 在2025年8月3日到8月4日期间的推文"

    async def execute_tool_function(self, tool_name: str, args: Dict[str, Any]) -> None:
        """
        执行工具函数。

        Args:
            tool_name (str): 工具名称
            args (Dict[str, Any]): 包含工具参数的字典，应包含 'usernames'、'start_time'、'end_time' 键
        """
        # 根据工具名称执行相应的工具函数
        if tool_name == "twitter_batch_user_search":
            usernames: List[str] = args.get("usernames", [])
            """要搜索的用户名列表。"""

            start_time: str = args.get("start_time", "")
            """搜索开始时间。"""

            end_time: str = args.get("end_time", "")
            """搜索结束时间。"""

            logger.info(
                f"正在执行 twitter_batch_user_search 工具 - "
                f"用户: {usernames}, "
                f"时间范围: {start_time} 至 {end_time}"
            )

            result: Optional[str] = await twitter_batch_user_search(
                usernames=usernames, start_time=start_time, end_time=end_time
            )
            """工具函数返回的格式化搜索结果。"""

            if result is not None:
                # 成功执行，简洁输出结果
                logger.info(f"Twitter 批量用户搜索完成，查询用户: {usernames}")
                logger.info(f"搜索结果:\n{result}")
            else:
                # 搜索失败，简洁错误日志
                logger.error(
                    f"Twitter 批量用户搜索失败 - 用户: {usernames}, "
                    f"时间范围: {start_time} 至 {end_time}"
                )
        else:
            logger.error(f"未知的工具名称: {tool_name}")

    def get_test_name(self) -> str:
        """
        获取测试名称。

        Returns:
            str: 测试的显示名称
        """
        return "Twitter 批量用户搜索工具"


# 运行命令：poetry run python -m workflow.test.tool.test_twitter_batch_user_search_tool
if __name__ == "__main__":
    create_test_runner(TwitterBatchUserSearchToolTest)

"""
Twitter 推文高级搜索工具的测试模块。

运行命令：
    poetry run python -m workflow.test.tool.test_twitter_tweet_advance_search_tool
"""

from typing import Dict, Any, List, Optional

from workflow.test.tool.base_tool_test import BaseToolTest, create_test_runner
from workflow.llm.tool.twitter_tweet_advance_search_tool import (
    twitter_tweet_advance_search_tool_definition,
    twitter_tweet_advance_search,
)
from workflow.schema.twitter import TweetListResponse
from common.utils.logger import get_logger

logger = get_logger(__name__)


class TwitterTweetAdvanceSearchToolTest(BaseToolTest):
    """
    Twitter 推文高级搜索工具的测试类。

    继承自 BaseToolTest，实现了所有必要的方法来测试
    twitter_tweet_advance_search 工具的功能。
    """

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        获取工具定义列表。

        Returns:
            List[Dict[str, Any]]: 包含 twitter_tweet_advance_search 工具定义的列表
        """
        return [twitter_tweet_advance_search_tool_definition]

    def get_test_prompt(self) -> str:
        """
        获取测试提示。

        Returns:
            str: 用于触发工具调用的测试提示
        """
        return "请帮我搜索 Elon Musk 在最近一周内的推文"

    async def execute_tool_function(self, tool_name: str, args: Dict[str, Any]) -> None:
        """
        执行工具函数。

        Args:
            tool_name (str): 工具名称
            args (Dict[str, Any]): 包含工具参数的字典，应包含 'query' 键
        """
        # 根据工具名称执行相应的工具函数
        if tool_name == "twitter_tweet_advance_search":
            query: str = args.get("query", "")
            """要执行的搜索查询。"""

            logger.info(f"正在执行 twitter_tweet_advance_search 工具，查询: {query}")

            result: Optional[TweetListResponse] = await twitter_tweet_advance_search(
                query, max_results=20
            )
            """工具函数返回的搜索结果。"""

            if result is not None and result.tweets:
                # 简洁输出搜索结果
                logger.info(
                    f"Twitter 推文搜索完成，查询: {query}，找到 {len(result.tweets)} 条推文"
                )

                # 输出推文详情
                for i, tweet in enumerate(result.tweets, 1):
                    author_name = tweet.author.name if tweet.author else "未知作者"
                    author_username = (
                        tweet.author.username if tweet.author else "unknown"
                    )

                    logger.info(
                        f"推文 #{i}: @{author_username} ({author_name}) - {tweet.created_at}\n"
                        f"内容: {tweet.text}\n"
                        f"互动: 👍{tweet.like_count} 🔄{tweet.retweet_count} 💬{tweet.reply_count}"
                    )

            elif result is not None and not result.tweets:
                logger.warning(f"Twitter 推文搜索结果为空，查询: {query}")

            else:
                logger.error(f"Twitter 推文搜索失败，查询: {query}")
        else:
            logger.error(f"未知的工具名称: {tool_name}")

    def get_test_name(self) -> str:
        """
        获取测试名称。

        Returns:
            str: 测试的显示名称
        """
        return "Twitter 推文高级搜索工具"


# 运行命令：poetry run python -m workflow.test.tool.test_twitter_tweet_advance_search_tool
if __name__ == "__main__":
    create_test_runner(TwitterTweetAdvanceSearchToolTest)

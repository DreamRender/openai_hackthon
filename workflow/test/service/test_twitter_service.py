import asyncio
from unittest.mock import AsyncMock, patch

from common.utils.logger import get_logger
from workflow.schema.twitter import (
    Tweet,
    TweetListResponse,
    TwitterUser,
    UserLastTweetsResponse,
    format_tweet_for_analysis,
    format_tweets_batch,
    format_user_for_analysis,
)
from workflow.service.twitter_service import TwitterService

logger = get_logger(__name__)


async def test_get_me():
    """测试 get_me 方法"""
    logger.info("=== 测试 get_me 方法 ===")

    # 创建 TwitterService 实例
    twitter_service = TwitterService()

    # 使用测试 access token（实际使用时需要真实的 token）
    test_access_token = "RnEzVUJ3U1FfNEhZYzRwUnR2bDJ5WFhlXzlLZVUxYjVwMTNjZXdlMS05TTJ0OjE3NTQwNDk5NzIzNjY6MTowOmF0OjE"

    user_info = None

    try:
        # 调用 get_me 方法
        user_info = await twitter_service.get_me(test_access_token)

        if user_info:
            formatted_user = format_user_for_analysis(user_info)
            user_output = f"用户信息获取成功:\n{formatted_user}"
            logger.info(user_output)
        else:
            logger.warning("未能获取用户信息")

    except Exception as e:
        logger.error(f"调用失败: {e}")

    return user_info


async def test_get_following():
    """测试 get_following 方法"""
    logger.info("\n=== 测试 get_following 方法 ===")

    # 创建 TwitterService 实例
    twitter_service = TwitterService()

    # 测试用户名（可以替换为任何真实的Twitter用户名）
    test_username = "KerryKonWang"
    max_results = 1000  # 限制结果数量以便测试

    following_info = None

    try:
        # 调用 get_following 方法
        following_info = await twitter_service.get_following(test_username, max_results)

        if following_info:
            summary = f"""关注列表获取成功:
  用户名: {test_username}
  总关注数: {following_info.total_count}
  获取到的用户数: {len(following_info.users)}
  下一页令牌: {following_info.next_token}"""
            logger.info(summary)

            # 显示所有关注的用户
            if following_info.users:
                users_details = []
                for i, user in enumerate(following_info.users):
                    users_details.append(
                        f"\n关注用户 {i+1}/{len(following_info.users)}:\n"
                    )
                    formatted_user = format_user_for_analysis(user)
                    users_details.append(formatted_user)

                logger.info("\n关注的用户详情:\n" + "\n".join(users_details))
        else:
            logger.warning("未能获取关注列表")

    except Exception as e:
        logger.error(f"调用失败: {e}")

    return following_info


async def test_get_user_last_tweets():
    """测试 get_user_last_tweets 方法 - 获取 KerryKonWang 的所有推文"""
    logger.info("\n=== 测试 get_user_last_tweets 方法 ===")

    # 创建 TwitterService 实例
    twitter_service = TwitterService()

    # 测试用户名
    test_username = "elonmusk"
    max_results = 20  # 限制结果数量以便测试

    result = None

    try:
        # 调用 get_user_last_tweets 方法
        result = await twitter_service.get_user_last_tweets(
            username=test_username,
            max_results=max_results,
            include_replies=True,  # 包含回复以获取更多推文
        )

        if result:
            summary = f"""获取 {test_username} 的推文成功!
  推文数量: {len(result.tweets)}
  状态: {result.status}
  消息: {result.message}
  有下一页: {result.has_next_page}
  下一页游标: {result.next_cursor}"""
            logger.info(summary)

            # 使用格式化函数显示推文
            if result.tweets:
                formatted_tweets = format_tweets_batch(result.tweets)
                tweets_output = f"\n获取到的推文:\n{formatted_tweets}\n\n显示了全部 {len(result.tweets)} 条推文"
                logger.info(tweets_output)
            else:
                logger.warning("没有获取到推文")
        else:
            logger.warning("获取推文失败，返回 None")

    except Exception as e:
        logger.error(f"调用失败: {str(e)}")
        import traceback

        traceback.print_exc()

    return result


async def test_tweet_advanced_search():
    """
    测试 Twitter 高级搜索功能
    """
    logger.info("开始测试 Twitter 高级搜索功能...")

    try:
        # 创建 TwitterService 实例
        service = TwitterService()

        # 测试参数
        query = "AI OR 人工智能"  # 搜索包含 AI 或人工智能的推文
        query_type = "Latest"  # 获取最新推文
        max_results = 50  # 限制结果数量以便测试

        logger.info(f"搜索查询: {query}")
        logger.info(f"查询类型: {query_type}")
        logger.info(f"最大结果数: {max_results}")

        # 调用高级搜索方法
        result = await service.tweet_advanced_search(
            query=query, query_type=query_type, max_results=max_results
        )

        if result:
            summary = f"""高级搜索结果统计：
  搜索查询: {query}
  查询类型: {query_type}
  推文数量: {len(result.tweets)}
  是否有下一页: {result.has_next_page}
  下一页游标: {result.next_cursor}"""
            logger.info(summary)

            # 使用格式化函数显示推文
            if result.tweets:
                formatted_tweets = format_tweets_batch(result.tweets)
                tweets_output = f"\n搜索到的推文:\n{formatted_tweets}\n\n显示了全部 {len(result.tweets)} 条推文"
                logger.info(tweets_output)
            else:
                logger.warning("没有搜索到推文")
        else:
            logger.warning("高级搜索失败，返回 None")

    except Exception as e:
        logger.error(f"高级搜索调用失败: {str(e)}")
        import traceback

        traceback.print_exc()
        result = None  # 确保在异常情况下 result 被初始化

    return result


if __name__ == "__main__":
    # 运行 poetry run python -m workflow.test.service.test_twitter_service
    # 可以选择运行不同的测试函数
    import sys

    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "advanced_search":
            asyncio.run(test_tweet_advanced_search())
        elif test_name == "get_me":
            asyncio.run(test_get_me())
        elif test_name == "get_following":
            asyncio.run(test_get_following())
        elif test_name == "last_tweets":
            asyncio.run(test_get_user_last_tweets())
        else:
            print("可用的测试: advanced_search, user_search, last_tweets")
    else:
        # 默认运行所有测试
        asyncio.run(test_get_user_last_tweets())

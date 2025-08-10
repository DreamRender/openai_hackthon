from datetime import datetime
from typing import Optional

import httpx
import tweepy

from common.config.config import get_workflow_config
from common.utils.logger import get_logger
from workflow.schema.twitter import (
    TwitterFollowingResponse,
    TwitterUser,
    TweetListResponse,
    Tweet,
    UserLastTweetsResponse,
)

logger = get_logger(__name__)


class TwitterService:
    """
    Twitter API 服务类

    负责与 Twitter API 交互和管理推文数据。
    提供用户搜索、推文获取、推文搜索等功能。
    """

    def __init__(self):
        """
        初始化 Twitter 服务
        """
        # 从配置中获取 Twitter API 密钥和基础配置信息
        workflow_config = get_workflow_config()
        self.twitterapi_api_key = workflow_config.twitterapi_api_key

    async def get_me(self, access_token: str) -> Optional[TwitterUser]:
        """
        使用 access token 获取当前用户信息

        Args:
            access_token: Twitter OAuth 2.0 访问令牌

        Returns:
            TwitterUser 实例，失败时返回 None
        """
        try:
            # 创建 Tweepy Client 实例，使用 Bearer Token
            client = tweepy.Client(
                bearer_token=access_token,
            )

            # 获取当前用户信息
            response = client.get_me(
                user_fields=[
                    "id",
                    "name",
                    "username",
                    "created_at",
                    "description",
                    "location",
                    "verified",
                    "profile_image_url",
                    "public_metrics",
                ],
                user_auth=False,  # 使用 OAuth 2.0
            )

            # 处理响应 - Response 是 namedtuple，包含 data, includes, errors, meta
            if response and getattr(response, "data", None):
                user_data = getattr(response, "data")

                # 使用 TwitterUser 的类方法创建实例
                return TwitterUser.from_twitter_official_api(user_data)
            else:
                logger.warning("No user data returned from Twitter API")
                return None

        except tweepy.TweepyException as e:
            logger.error(f"Tweepy error when getting user info: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when getting user info: {str(e)}")
            return None

    async def get_following(
        self, username: str, max_results: int = 1000
    ) -> Optional[TwitterFollowingResponse]:
        """
        获取用户关注的所有人的信息

        Args:
            username: Twitter 用户名（不包含@符号）
            max_results: 最大返回结果数量，默认1000

        Returns:
            TwitterFollowingResponse 实例，包含关注的用户列表，失败时返回 None
        """
        try:
            url = "https://api.twitterapi.io/twitter/user/followings"

            headers = {"X-API-Key": self.twitterapi_api_key}

            all_users = []
            cursor = ""
            total_fetched = 0

            # 分页获取所有关注的用户
            async with httpx.AsyncClient() as client:
                while total_fetched < max_results:
                    # 计算本次请求的数量（API单次最多200）
                    page_size = min(200, max_results - total_fetched)

                    params = {
                        "userName": username,
                        "cursor": cursor,
                        "pageSize": page_size,
                    }

                    response = await client.get(url, headers=headers, params=params)

                    if response.status_code != 200:
                        logger.error(
                            f"Twitter API request failed with status {response.status_code}"
                        )
                        return None

                    data = response.json()

                    # 检查API响应格式
                    if not data or data.get("status") != "success":
                        logger.warning(
                            f"Twitter API returned error: {data.get('message', 'Unknown error')}"
                        )
                        return None

                    if "followings" not in data:
                        logger.warning("No followings data returned from Twitter API")
                        break

                    followings_data = data.get("followings", [])

                    # 使用 TwitterUser 的类方法转换用户数据
                    for user_data in followings_data:
                        twitter_user = TwitterUser.from_twitterapi_io(user_data)
                        all_users.append(twitter_user)

                    total_fetched += len(followings_data)

                    # 检查是否还有更多数据
                    has_next_page = data.get("has_next_page", False)
                    if not has_next_page or len(followings_data) == 0:
                        break

                    cursor = data.get("next_cursor", "")
                    if not cursor:
                        break

            return TwitterFollowingResponse(
                users=all_users,
                total_count=total_fetched,
                next_token=cursor if cursor else None,
            )

        except httpx.RequestError as e:
            logger.error(f"HTTP request error when getting following list: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when getting following list: {str(e)}")
            return None

    async def get_user_last_tweets(
        self,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        include_replies: bool = False,
        max_results: int = 1000,
    ) -> Optional[UserLastTweetsResponse]:
        """
        获取用户的最新推文，按创建时间排序

        注意：每页最多返回 20 条推文。如果你需要频繁获取单个用户的最新推文，
        请参考实时监控方案：https://twitterapi.io/blog/how-to-monitor-twitter-accounts-for-new-tweets-in-real-time

        Args:
            user_id: 用户ID，推荐使用（比用户名更稳定快速）
            username: 用户名（不包含@符号），与user_id互斥，如果都提供则使用user_id
            include_replies: 是否包含回复，默认为False
            max_results: 最大返回结果数量，默认1000

        Returns:
            UserLastTweetsResponse 实例，包含推文列表和分页信息，失败时返回 None

        Examples:
            # 使用用户ID获取推文（推荐）
            await get_user_last_tweets(user_id="123456789")

            # 使用用户名获取推文
            await get_user_last_tweets(username="elonmusk")

            # 包含回复的推文
            await get_user_last_tweets(username="nasa", include_replies=True)

            # 获取指定数量的推文
            await get_user_last_tweets(username="openai", max_results=100)
        """
        try:
            # 验证参数
            if not user_id and not username:
                logger.error("Either user_id or username must be provided")
                return None

            url = "https://api.twitterapi.io/twitter/user/last_tweets"
            headers = {"X-API-Key": self.twitterapi_api_key}

            all_tweets = []
            cursor = ""
            total_fetched = 0

            # 优先使用 user_id，如果没有则使用 username
            if user_id:
                logger.info(f"Getting last tweets for user ID: {user_id}")
            else:
                logger.info(f"Getting last tweets for username: {username}")

            # 分页获取所有推文
            async with httpx.AsyncClient() as client:
                while total_fetched < max_results:
                    params = {
                        "cursor": cursor,
                        "includeReplies": include_replies,
                    }

                    # 优先使用 user_id，如果没有则使用 username
                    if user_id:
                        params["userId"] = user_id
                    else:
                        params["userName"] = username

                    response = await client.get(url, headers=headers, params=params)

                    logger.info(f"Call Twitter API Success: {response.status_code}")

                    if response.status_code != 200:
                        logger.error(
                            f"Twitter API request failed with status {response.status_code}: {response.text}"
                        )
                        return None

                    data = response.json()

                    # 检查API响应格式
                    if not data or data.get("status") != "success":
                        logger.warning(
                            f"Twitter API returned error: {data.get('message', 'Unknown error')}"
                        )
                        return None

                    # 获取嵌套的数据结构
                    inner_data = data.get("data", {})
                    if "tweets" not in inner_data:
                        logger.warning("No tweets data returned from Twitter API")
                        break

                    tweets_data = inner_data.get("tweets", [])

                    # 使用 Tweet 的类方法转换推文数据
                    for tweet_data in tweets_data:
                        try:
                            tweet = Tweet.from_twitterapi_io(tweet_data)
                            all_tweets.append(tweet)
                        except Exception as e:
                            logger.warning(
                                f"Failed to parse tweet: {str(e)}, tweet_data: {tweet_data}"
                            )
                            continue

                    total_fetched += len(tweets_data)

                    # 检查是否还有更多数据
                    has_next_page = data.get("has_next_page", False)
                    if not has_next_page or len(tweets_data) == 0:
                        break

                    cursor = data.get("next_cursor", "")
                    if not cursor:
                        break

            return UserLastTweetsResponse(
                tweets=all_tweets,
                has_next_page=cursor != "" if cursor else False,
                next_cursor=cursor if cursor else None,
                status="success",
                message=f"Successfully fetched {len(all_tweets)} tweets",
            )

        except httpx.RequestError as e:
            logger.error(f"HTTP request error when getting user last tweets: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when getting user last tweets: {str(e)}")
            return None

    async def tweet_advanced_search(
        self,
        query: str,
        query_type: str = "Latest",
        max_results: int = 1000,
    ) -> Optional[TweetListResponse]:
        """
        执行 Twitter 高级搜索，获取符合查询条件的推文

        注意：每页最多返回 20 条推文（有时会更少，因为会过滤掉广告或其他非推文内容）。
        使用 cursor 进行分页。

        Args:
            query: 搜索查询字符串，例如：
                  - "AI" OR "Twitter" from:elonmusk since:2021-12-31_23:59:59_UTC
                  - 更多示例请参考：https://github.com/igorbrigadir/twitter-advanced-search
            query_type: 查询类型，"Latest"（最新）或 "Top"（热门），默认为 "Latest"
            max_results: 最大返回结果数量，默认1000

        Returns:
            TweetListResponse 实例，包含推文列表和分页信息，失败时返回 None

        Examples:
            # 搜索包含 AI 关键词的最新推文
            await tweet_advanced_search(query="AI")

            # 搜索特定用户的推文
            await tweet_advanced_search(query="from:elonmusk", query_type="Top")

            # 搜索特定时间范围的推文
            await tweet_advanced_search(
                query="AI since:2024-01-01 until:2024-12-31",
                max_results=100
            )

            # 搜索包含多个关键词的推文
            await tweet_advanced_search(
                query='"机器学习" OR "深度学习" lang:zh',
                query_type="Latest"
            )
        """
        try:
            # 验证参数
            if not query or not query.strip():
                logger.error("Query parameter is required and cannot be empty")
                return None

            if query_type not in ["Latest", "Top"]:
                logger.error(
                    f"Invalid query_type: {query_type}. Must be 'Latest' or 'Top'"
                )
                return None

            url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
            headers = {"X-API-Key": self.twitterapi_api_key}

            all_tweets = []
            cursor = ""
            total_fetched = 0

            logger.info(
                f"Starting advanced search with query: {query}, type: {query_type}"
            )

            # 分页获取所有推文
            async with httpx.AsyncClient() as client:
                while total_fetched < max_results:
                    params = {
                        "query": query,
                        "queryType": query_type,
                        "cursor": cursor,
                    }

                    response = await client.get(url, headers=headers, params=params)

                    logger.info(
                        f"Call Twitter Advanced Search API Success: {response.status_code}"
                    )

                    if response.status_code != 200:
                        logger.error(
                            f"Twitter Advanced Search API request failed with status {response.status_code}: {response.text}"
                        )
                        return None

                    # 尝试解析 JSON 响应，增加错误处理
                    try:
                        data = response.json()
                        logger.debug(
                            f"API 响应数据结构: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                        )
                    except Exception as json_error:
                        logger.error(
                            f"Failed to parse JSON response: {str(json_error)}, "
                            f"response text: {response.text[:500]}..."
                        )
                        return None

                    # 检查API响应格式（Advanced Search API 直接返回数据，不像 last_tweets 有嵌套结构）
                    if not data or "tweets" not in data:
                        logger.warning(
                            f"No tweets data returned from Twitter Advanced Search API. "
                            f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}, "
                            f"Data type: {type(data)}"
                        )
                        break

                    tweets_data = data.get("tweets", [])
                    logger.info(f"当前页面获取到 {len(tweets_data)} 条推文数据")

                    # 使用 Tweet 的类方法转换推文数据
                    parsed_tweets_count = 0
                    for i, tweet_data in enumerate(tweets_data):
                        try:
                            tweet = Tweet.from_twitterapi_io(tweet_data)
                            all_tweets.append(tweet)
                            parsed_tweets_count += 1
                        except Exception as e:
                            logger.warning(
                                f"Failed to parse tweet #{i+1} in advanced search: {str(e)}, "
                                f"tweet_data keys: {list(tweet_data.keys()) if isinstance(tweet_data, dict) else 'Not a dict'}"
                            )
                            continue

                    logger.info(
                        f"成功解析 {parsed_tweets_count}/{len(tweets_data)} 条推文"
                    )
                    total_fetched += len(tweets_data)

                    # 检查是否还有更多数据
                    has_next_page = data.get("has_next_page", False)
                    if not has_next_page or len(tweets_data) == 0:
                        break

                    cursor = data.get("next_cursor", "")
                    if not cursor:
                        break

            logger.info(
                f"Advanced search completed. Total tweets fetched: {len(all_tweets)}"
            )

            return TweetListResponse(
                tweets=all_tweets,
                has_next_page=cursor != "" if cursor else False,
                next_cursor=cursor if cursor else None,
            )

        except httpx.RequestError as e:
            logger.error(
                f"HTTP request error when performing advanced search: {str(e)}, "
                f"Error type: {type(e).__name__}, "
                f"Query: {query}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error when performing advanced search: {str(e)}, "
                f"Error type: {type(e).__name__}, "
                f"Query: {query}"
            )
            return None

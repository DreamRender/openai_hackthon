"""
Twitter 批量用户搜索工具模块。

本模块为 LiteLLM 提供了 Twitter 批量用户搜索功能。
该工具可以并发查询多个用户在指定时间范围内的推文，
并将结果整合后返回。
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading

import litellm
from jinja2 import Environment, FileSystemLoader

from workflow.service.twitter_service import TwitterService
from workflow.schema.twitter import TweetListResponse, Tweet
from common.config.config import get_workflow_config
from common.utils.logger import get_logger

logger = get_logger(__name__)
"""日志记录器实例，用于记录模块运行时的日志信息。"""

# LiteLLM 工具定义
twitter_batch_user_search_tool_definition = {
    "type": "function",
    "function": {
        "name": "twitter_batch_user_search",
        "description": "Batch search for tweets from multiple users within a specified time range. This tool searches for tweets from a list of usernames between start and end times, using concurrent execution for better performance.",
        "parameters": {
            "type": "object",
            "properties": {
                "usernames": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Twitter usernames to search (without @ symbol). Example: ['elonmusk', 'sundarpichai', 'satyanadella']",
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time MUST be in exact format: YYYY-MM-DD_HH:MM:SS_UTC. If no time is specified, use 00:00:00. Example: '2024-01-01_00:00:00_UTC' for start of day, '2024-01-01_10:30:00_UTC' for specific time. This format is mandatory and will be validated.",
                },
                "end_time": {
                    "type": "string",
                    "description": "End time MUST be in exact format: YYYY-MM-DD_HH:MM:SS_UTC. If no time is specified, use 00:00:00. Example: '2024-01-31_00:00:00_UTC' for start of day, '2024-01-31_23:59:59_UTC' for end of day. This format is mandatory and will be validated.",
                },
            },
            "required": ["usernames", "start_time", "end_time"],
        },
    },
}
"""
LiteLLM 工具定义字典。

定义了 twitter_batch_user_search 工具的结构，包括：
- type: 工具类型，固定为 "function"
- function: 包含函数名称、描述和参数定义
- name: 工具名称
- description: 工具功能描述（英文）
- parameters: 参数 schema，包含 usernames、start_time、end_time 参数的定义
"""


class BatchUserSearchResult:
    """
    批量用户搜索结果类。

    用于存储和管理批量用户搜索的结果数据。
    """

    def __init__(self):
        """初始化批量搜索结果。"""
        self.user_results: Dict[str, TweetListResponse] = {}
        """存储每个用户的搜索结果，键为用户名，值为推文列表响应。"""

        self.successful_users: List[str] = []
        """成功查询的用户列表。"""

        self.failed_users: List[str] = []
        """查询失败的用户列表。"""

        self.total_tweets: int = 0
        """所有用户的推文总数。"""

        self.start_time: str = ""
        """查询开始时间。"""

        self.end_time: str = ""
        """查询结束时间。"""


async def _search_user_tweets(
    username: str,
    start_time: str,
    end_time: str,
    twitter_service: TwitterService,
    max_results: int = 20,
) -> Optional[TweetListResponse]:
    """
    搜索单个用户在指定时间范围内的推文。

    Args:
        username (str): 用户名（不包含@符号）
        start_time (str): 开始时间，格式为 ISO 时间字符串
        end_time (str): 结束时间，格式为 ISO 时间字符串
        twitter_service (TwitterService): Twitter 服务实例

    Returns:
        Optional[TweetListResponse]: 搜索结果，失败时返回 None
    """
    try:
        # 构建单个用户的搜索查询
        search_query = f"from:{username} since:{start_time} until:{end_time}"
        """为单个用户构建的 Twitter 搜索查询。"""

        logger.info(f"正在搜索用户 {username} 的推文，查询: {search_query}")

        # 执行搜索
        result = await twitter_service.tweet_advanced_search(
            query=search_query,
            query_type="Latest",  # 搜索最新推文
            max_results=max_results,  # 每个用户最多20条推文
        )

        if result is not None:
            logger.info(f"用户 {username} 搜索成功，找到 {len(result.tweets)} 条推文")
        else:
            logger.warning(f"用户 {username} 搜索失败")

        return result

    except Exception as e:
        logger.error(f"搜索用户 {username} 推文时发生异常: {str(e)}")
        return None


async def _batch_search_users(
    usernames: List[str], start_time: str, end_time: str, max_results: int = 20
) -> BatchUserSearchResult:
    """
    并发搜索多个用户的推文。

    使用 asyncio 的并发机制同时查询多个用户的推文，提高查询效率。

    Args:
        usernames (List[str]): 用户名列表
        start_time (str): 开始时间
        end_time (str): 结束时间

    Returns:
        BatchUserSearchResult: 批量搜索结果
    """
    # 创建批量搜索结果对象
    batch_result = BatchUserSearchResult()
    batch_result.start_time = start_time
    batch_result.end_time = end_time

    # 创建 Twitter 服务实例
    twitter_service = TwitterService()
    """Twitter 服务实例，用于执行实际的 API 调用。"""

    logger.info(f"开始并发搜索 {len(usernames)} 个用户的推文")

    # 创建并发任务列表
    tasks = []
    for username in usernames:
        task = _search_user_tweets(
            username, start_time, end_time, twitter_service, max_results
        )
        tasks.append((username, task))

    # 执行并发搜索
    results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
    """并发执行所有搜索任务的结果列表。"""

    # 处理搜索结果
    for (username, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            # 处理异常情况
            logger.error(f"用户 {username} 搜索异常: {str(result)}")
            batch_result.failed_users.append(username)
        elif isinstance(result, TweetListResponse):
            # 成功的搜索结果
            batch_result.user_results[username] = result
            batch_result.successful_users.append(username)
            batch_result.total_tweets += len(result.tweets)
            logger.info(f"用户 {username} 成功搜索到 {len(result.tweets)} 条推文")
        else:
            # 搜索失败（result 为 None）
            batch_result.failed_users.append(username)
            logger.warning(f"用户 {username} 搜索失败，返回结果为 None")

    logger.info(
        f"批量搜索完成 - 成功: {len(batch_result.successful_users)} 个用户, "
        f"失败: {len(batch_result.failed_users)} 个用户, "
        f"总推文数: {batch_result.total_tweets}"
    )

    return batch_result


def _render_batch_search_result(batch_result: BatchUserSearchResult) -> str:
    """
    渲染批量搜索结果为格式化的文本。

    使用 Jinja2 模板引擎渲染批量搜索结果。

    Args:
        batch_result (BatchUserSearchResult): 批量搜索结果

    Returns:
        str: 渲染后的格式化文本
    """
    try:
        # 设置模板路径
        template_dir = Path(__file__).parent.parent.parent / "template"
        """模板文件目录路径。"""

        # 加载模板
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("batch_user_search_result.j2")
        """加载的 Jinja2 模板实例。"""

        # 渲染模板
        rendered_result = template.render(
            batch_result=batch_result,
            successful_count=len(batch_result.successful_users),
            failed_count=len(batch_result.failed_users),
            total_users=len(batch_result.successful_users)
            + len(batch_result.failed_users),
            current_time=datetime.utcnow().strftime("%Y-%m-%d_%H:%M:%S_UTC"),
        )
        """渲染后的完整结果文本。"""

        return rendered_result

    except Exception as e:
        logger.error(f"渲染批量搜索结果时发生异常: {str(e)}")
        # 返回简单的文本格式作为后备
        return f"""
批量用户搜索结果

时间范围: {batch_result.start_time} 至 {batch_result.end_time}
成功用户: {len(batch_result.successful_users)}
失败用户: {len(batch_result.failed_users)}
总推文数: {batch_result.total_tweets}

详细结果渲染失败，请检查模板配置。
"""


async def twitter_batch_user_search(
    usernames: List[str], start_time: str, end_time: str, max_results: int = 20
) -> Optional[str]:
    """
    执行 Twitter 批量用户搜索。

    该函数接受多个用户名和时间范围，并发搜索每个用户在指定时间内的推文，
    然后将结果整合并格式化返回。

    工作流程：
    1. 验证输入参数
    2. 为每个用户构建搜索查询
    3. 使用 asyncio 并发执行搜索
    4. 整合和格式化搜索结果
    5. 返回渲染后的结果

    Args:
        usernames (List[str]): 要搜索的用户名列表（不包含@符号）
                              示例: ["elonmusk", "sundarpichai", "satyanadella"]
        start_time (str): 搜索开始时间，支持以下格式：
                         - 日期格式: "2024-01-01"
                         - 完整时间格式: "2024-01-01_10:30:00_UTC"
        end_time (str): 搜索结束时间，格式同 start_time

    Returns:
        Optional[str]: 成功时返回格式化的搜索结果文本，失败时返回 None
                      结果包含：
                      - 每个用户的搜索统计
                      - 成功和失败的用户列表
                      - 所有找到的推文详情
                      - 搜索汇总信息

    Raises:
        无异常抛出，所有异常都在内部处理并记录日志。

    Examples:
        >>> # 搜索多个科技公司CEO的推文
        >>> result = await twitter_batch_user_search(
        ...     usernames=["elonmusk", "sundarpichai", "satyanadella"],
        ...     start_time="2024-01-01",
        ...     end_time="2024-01-31"
        ... )
        >>> if result:
        ...     print(result)  # 显示格式化的搜索结果

        >>> # 搜索特定时间段的推文
        >>> result = await twitter_batch_user_search(
        ...     usernames=["tim_cook", "jeffweiner"],
        ...     start_time="2024-01-15_09:00:00_UTC",
        ...     end_time="2024-01-15_18:00:00_UTC"
        ... )

    Note:
        - 该函数需要有效的 Twitter API 配置
        - 使用并发机制提高查询效率，但仍受 API 速率限制约束
        - 建议每次搜索的用户数量不超过10个，以避免 API 限制
        - 搜索结果按用户分组，每个用户最多返回20条推文
        - 时间格式严格按照 Twitter API 要求，建议使用 UTC 时间
    """
    try:
        # 验证输入参数
        if not usernames or len(usernames) == 0:
            logger.error("用户名列表不能为空")
            return None

        if not start_time or not end_time:
            logger.error("开始时间和结束时间不能为空")
            return None

        # 验证时间格式是否为标准格式 YYYY-MM-DD_HH:MM:SS_UTC
        time_format_pattern = r"^\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2}_UTC$"
        if not re.match(time_format_pattern, start_time):
            logger.error(
                f"开始时间格式错误: {start_time}，必须使用格式 YYYY-MM-DD_HH:MM:SS_UTC"
            )
            return None

        if not re.match(time_format_pattern, end_time):
            logger.error(
                f"结束时间格式错误: {end_time}，必须使用格式 YYYY-MM-DD_HH:MM:SS_UTC"
            )
            return None

        logger.info(f"时间格式验证通过 - 开始时间: {start_time}, 结束时间: {end_time}")

        # 清理用户名列表（移除@符号和空格）
        cleaned_usernames = []
        for username in usernames:
            if isinstance(username, str):
                clean_username = username.strip().lstrip("@")
                if clean_username:
                    cleaned_usernames.append(clean_username)

        if not cleaned_usernames:
            logger.error("清理后的用户名列表为空")
            return None

        logger.info(
            f"开始执行批量用户搜索 - "
            f"用户数量: {len(cleaned_usernames)}, "
            f"时间范围: {start_time} 至 {end_time}"
        )

        # 执行批量搜索
        batch_result = await _batch_search_users(
            cleaned_usernames, start_time, end_time, max_results
        )
        """批量搜索的完整结果。"""

        # 检查是否有任何成功的结果
        if len(batch_result.successful_users) == 0:
            logger.warning("所有用户搜索都失败，没有找到任何推文")
            return _render_batch_search_result(
                batch_result
            )  # 仍然返回结果以显示失败信息

        # 渲染搜索结果
        rendered_result = _render_batch_search_result(batch_result)
        """渲染后的最终搜索结果文本。"""

        logger.info(
            f"批量用户搜索完成 - "
            f"成功用户: {len(batch_result.successful_users)}, "
            f"失败用户: {len(batch_result.failed_users)}, "
            f"总推文数: {batch_result.total_tweets}"
        )

        return rendered_result

    except Exception as e:
        logger.error(f"执行批量用户搜索时发生异常: {str(e)}")
        return None


# 导出工具定义和函数，供其他模块使用
__all__ = [
    "twitter_batch_user_search_tool_definition",
    "twitter_batch_user_search",
    "BatchUserSearchResult",
]
"""
模块导出列表。

包含：
- twitter_batch_user_search_tool_definition: LiteLLM 工具定义
- twitter_batch_user_search: 执行批量用户搜索的异步函数
- BatchUserSearchResult: 批量搜索结果数据类
"""

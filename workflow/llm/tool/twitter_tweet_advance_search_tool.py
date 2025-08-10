"""
Twitter 推文高级搜索工具模块。

本模块为 LiteLLM 提供了 Twitter 推文高级搜索功能。
该工具使用 AI 辅助将自然语言查询转换为 Twitter 高级搜索语法，
然后执行搜索并返回相关推文。
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import litellm
from jinja2 import Environment, FileSystemLoader

from workflow.service.twitter_service import TwitterService
from workflow.schema.twitter import TweetListResponse
from common.config.config import get_workflow_config
from common.utils.logger import get_logger

logger = get_logger(__name__)
"""日志记录器实例，用于记录模块运行时的日志信息。"""

# LiteLLM 工具定义
twitter_tweet_advance_search_tool_definition = {
    "type": "function",
    "function": {
        "name": "twitter_tweet_advance_search",
        "description": "Search for tweets using natural language queries. This tool converts natural language search requests into proper Twitter advanced search syntax and returns relevant tweets. Supports searching by keywords, users, time ranges, hashtags, and more complex queries. IMPORTANT: When time ranges are specified in the query, they MUST be formatted as YYYY-MM-DD_HH:MM:SS_UTC (e.g., 'since 2024-01-01_00:00:00_UTC', 'until 2024-01-31_23:59:59_UTC'). Use 00:00:00 if no specific time is mentioned.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query. For example: 'tweets from Elon Musk about AI in the last week', 'hashtag #AI in English tweets', 'tweets mentioning OpenAI since 2024-01-01_00:00:00_UTC', etc. CRITICAL: If your query includes time ranges (since/until), you MUST use the exact format YYYY-MM-DD_HH:MM:SS_UTC.",
                }
            },
            "required": ["query"],
        },
    },
}
"""
LiteLLM 工具定义字典。

定义了 twitter_tweet_advance_search 工具的结构，包括：
- type: 工具类型，固定为 "function"
- function: 包含函数名称、描述和参数定义
- name: 工具名称
- description: 工具功能描述（英文）
- parameters: 参数 schema，包含 query 参数的定义
"""


def _validate_time_format_in_query(query: str) -> bool:
    """
    验证Twitter搜索查询中的时间格式是否符合标准。

    检查查询中的since和until参数是否使用正确的YYYY-MM-DD_HH:MM:SS_UTC格式。

    Args:
        query (str): Twitter搜索查询字符串

    Returns:
        bool: 如果所有时间格式都正确或查询中没有时间参数则返回True，否则返回False

    Examples:
        >>> _validate_time_format_in_query("from:elonmusk since:2024-01-01_00:00:00_UTC")
        True

        >>> _validate_time_format_in_query("from:elonmusk since:2024-01-01")
        False

        >>> _validate_time_format_in_query("from:elonmusk AI")
        True
    """
    try:
        # 标准时间格式正则表达式
        time_format_pattern = r"\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2}_UTC"
        """标准时间格式的正则表达式模式。"""

        # 查找since参数
        since_matches = re.findall(r"since:(\S+)", query, re.IGNORECASE)
        for since_time in since_matches:
            if not re.match(rf"^{time_format_pattern}$", since_time):
                logger.error(
                    f"无效的since时间格式: {since_time}，必须使用 YYYY-MM-DD_HH:MM:SS_UTC"
                )
                return False

        # 查找until参数
        until_matches = re.findall(r"until:(\S+)", query, re.IGNORECASE)
        for until_time in until_matches:
            if not re.match(rf"^{time_format_pattern}$", until_time):
                logger.error(
                    f"无效的until时间格式: {until_time}，必须使用 YYYY-MM-DD_HH:MM:SS_UTC"
                )
                return False

        # 如果找到了时间参数，记录验证成功
        if since_matches or until_matches:
            logger.info(
                f"查询中的时间格式验证通过: since={since_matches}, until={until_matches}"
            )

        return True

    except Exception as e:
        logger.error(f"验证时间格式时发生异常: {str(e)}")
        return False


def _extract_constructed_query(llm_response: str) -> Optional[str]:
    """
    从 LLM 响应中提取构造的 Twitter 搜索查询。

    使用正则表达式从 LLM 的响应文本中提取 <constructed_query> 标签中的内容。

    Args:
        llm_response (str): LLM 返回的完整响应文本

    Returns:
        Optional[str]: 提取的查询字符串，如果未找到则返回 None

    Examples:
        >>> response = "Here is your query: <constructed_query>from:elonmusk AI</constructed_query>"
        >>> _extract_constructed_query(response)
        'from:elonmusk AI'

        >>> response = "No query found"
        >>> _extract_constructed_query(response)
        None
    """
    try:
        # 使用正则表达式提取 <constructed_query> 标签中的内容
        pattern = r"<constructed_query>\s*(.*?)\s*</constructed_query>"
        match = re.search(pattern, llm_response, re.DOTALL | re.IGNORECASE)

        if match:
            extracted_query = match.group(1).strip()
            logger.info(f"成功从 LLM 响应中提取查询: {extracted_query}")
            return extracted_query
        else:
            logger.warning("未在 LLM 响应中找到 <constructed_query> 标签")
            return None

    except Exception as e:
        logger.error(f"提取构造查询时发生异常: {str(e)}")
        return None


async def _generate_twitter_search_query(user_query: str) -> Optional[str]:
    """
    使用 LLM 将用户的自然语言查询转换为 Twitter 高级搜索语法。

    该函数使用预定义的 Jinja2 模板和 LiteLLM 来生成适当的 Twitter 搜索查询。

    Args:
        user_query (str): 用户的自然语言搜索查询

    Returns:
        Optional[str]: 构造的 Twitter 搜索查询字符串，失败时返回 None

    Raises:
        无异常抛出，所有异常都在内部处理并记录日志。

    Examples:
        >>> query = await _generate_twitter_search_query("tweets from Elon Musk about AI")
        >>> print(query)  # "from:elonmusk AI"
    """
    try:
        # 获取配置
        workflow_config = get_workflow_config()
        api_key = workflow_config.anthropic_api_key
        """Anthropic API 密钥，用于调用 Claude 模型。"""

        # 获取当前 UTC 时间
        current_utc_time = datetime.utcnow().strftime("%Y-%m-%d_%H:%M:%S_UTC")
        """当前 UTC 时间字符串，用于模板渲染。"""

        # 设置模板路径
        template_dir = Path(__file__).parent.parent.parent / "template"
        """模板文件目录路径。"""

        # 渲染 Jinja2 模板
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("twitter_advance_search_prompt.j2")
        """加载的 Jinja2 模板实例。"""

        prompt = template.render(
            search_query=user_query, current_utc_time=current_utc_time
        )
        """渲染后的完整提示文本。"""

        logger.info(f"正在使用 LLM 生成 Twitter 搜索查询，用户查询: {user_query}")

        # 调用 LiteLLM
        response = await litellm.acompletion(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
        )

        # 处理响应
        choices = getattr(response, "choices", None)
        if choices and len(choices) > 0:
            choice = choices[0]
            message = getattr(choice, "message", None)
            if message:
                content = getattr(message, "content", None)
                if content:
                    # 从响应中提取构造的查询
                    constructed_query = _extract_constructed_query(content)
                    if constructed_query:
                        # 验证时间格式
                        if _validate_time_format_in_query(constructed_query):
                            logger.info(
                                f"LLM 成功生成 Twitter 搜索查询: {constructed_query}"
                            )
                            return constructed_query
                        else:
                            logger.error(
                                f"LLM 生成的查询包含无效时间格式: {constructed_query}"
                            )
                            return None
                    else:
                        logger.warning("LLM 响应中未找到有效的构造查询")
                        return None
                else:
                    logger.warning("LLM 响应消息中没有内容")
                    return None
            else:
                logger.warning("LLM 响应中没有消息对象")
                return None
        else:
            logger.warning("LLM 响应格式异常")
            return None

    except Exception as e:
        logger.error(f"生成 Twitter 搜索查询时发生异常: {str(e)}")
        return None


async def twitter_tweet_advance_search(
    query: str, max_results: int = 20
) -> Optional[TweetListResponse]:
    """
    执行 Twitter 推文高级搜索，使用 AI 辅助查询构造。

    该函数是对 TwitterService.tweet_advanced_search() 的智能包装，专门为 LiteLLM 工具调用设计。
    它接受自然语言查询，使用 AI 将其转换为 Twitter 高级搜索语法，然后执行搜索。

    工作流程：
    1. 接收用户的自然语言查询
    2. 使用 AI 将查询转换为 Twitter 高级搜索语法
    3. 调用 Twitter API 执行搜索
    4. 返回搜索结果

    Args:
        query (str): 用户的自然语言搜索查询。
                    示例:
                    - "tweets from Elon Musk about AI in the last week"
                    - "hashtag #AI in English tweets"
                    - "tweets mentioning OpenAI since 2024-01-01"
                    - "最新的关于机器学习的中文推文"

    Returns:
        Optional[TweetListResponse]: 成功时返回包含推文列表的响应对象，失败时返回 None。
                                   - tweets: 符合条件的推文列表
                                   - has_next_page: 是否有更多结果
                                   - next_cursor: 用于分页的游标
                                   - 如果发生错误（如查询转换失败、API 限制等），返回 None

    Raises:
        无异常抛出，所有异常都在内部处理并记录日志。

    Examples:
        >>> # 搜索特定用户关于特定主题的推文
        >>> result = await twitter_tweet_advance_search("tweets from Elon Musk about AI")
        >>> if result and result.tweets:
        ...     print(f"找到 {len(result.tweets)} 条相关推文")
        ...     for tweet in result.tweets[:3]:  # 显示前3条
        ...         print(f"- {tweet.author.name}: {tweet.text[:100]}...")

        >>> # 搜索热门话题
        >>> result = await twitter_tweet_advance_search("热门的关于ChatGPT的中文推文")
        >>> if result:
        ...     print(f"搜索完成，共找到 {len(result.tweets)} 条推文")

    Note:
        - 该函数需要有效的 Twitter API 配置和 Anthropic API 配置
        - AI 查询转换可能需要几秒钟时间
        - API 有速率限制，频繁调用可能会被限制
        - 搜索结果按相关性或时间排序（取决于查询类型）
        - 返回的推文数量受 Twitter API 限制（通常每页最多20条）
    """
    try:
        # 验证输入参数
        if not query or not query.strip():
            logger.error("查询参数不能为空")
            return None

        logger.info(f"开始执行 Twitter 高级搜索，用户查询: {query}")

        # 第一步：使用 AI 生成 Twitter 搜索查询
        constructed_query = await _generate_twitter_search_query(query.strip())
        """AI 生成的 Twitter 高级搜索查询字符串。"""

        if not constructed_query:
            logger.error("AI 查询构造失败，无法生成有效的 Twitter 搜索语法")
            return None

        # 第二步：创建 Twitter 服务实例并执行搜索
        twitter_service = TwitterService()
        """Twitter 服务实例，用于执行实际的 API 调用。"""

        logger.info(f"正在执行 Twitter 搜索，构造的查询: {constructed_query}")

        # 执行搜索（默认获取最新推文）
        search_result = await twitter_service.tweet_advanced_search(
            query=constructed_query,
            query_type="Latest",  # 搜索最新推文
            max_results=max_results,  # 最大结果数量
        )
        """Twitter API 搜索结果。"""

        # 检查搜索结果
        if search_result is None:
            logger.warning(f"Twitter 搜索失败，查询: {constructed_query}")
            return None

        logger.info(
            f"Twitter 搜索成功完成，"
            f"原始查询: {query}, "
            f"构造查询: {constructed_query}, "
            f"找到推文数量: {len(search_result.tweets)}"
        )

        return search_result

    except Exception as e:
        logger.error(f"执行 Twitter 高级搜索时发生异常: {str(e)}")
        return None


# 导出工具定义和函数，供其他模块使用
__all__ = [
    "twitter_tweet_advance_search_tool_definition",
    "twitter_tweet_advance_search",
    "_validate_time_format_in_query",
]
"""
模块导出列表。

包含：
- twitter_tweet_advance_search_tool_definition: LiteLLM 工具定义
- twitter_tweet_advance_search: 执行 Twitter 高级搜索的异步函数
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field


class TweetUrl(BaseModel):
    """推文中的URL信息"""

    display_url: str = Field(..., description="显示的URL")
    expanded_url: str = Field(..., description="完整URL")
    url: str = Field(..., description="短链接")
    indices: List[int] = Field(..., description="URL在文本中的位置索引")


class ProfileBioEntity(BaseModel):
    """用户简介中的实体信息"""

    urls: Optional[List[TweetUrl]] = Field(default_factory=list, description="URL列表")


class ProfileBioEntities(BaseModel):
    """用户简介的实体集合"""

    description: Optional[ProfileBioEntity] = Field(None, description="简介中的实体")
    url: Optional[ProfileBioEntity] = Field(None, description="URL中的实体")


class ProfileBio(BaseModel):
    """用户简介详细信息"""

    description: Optional[str] = Field(None, description="简介文本")
    entities: Optional[ProfileBioEntities] = Field(None, description="简介中的实体信息")


class TwitterUser(BaseModel):
    """
    Twitter 用户信息模型 - 统一下划线命名风格

    注意：本模型主要基于 TwitterAPI.io 的数据结构设计，同时兼容 Twitter 官方 API

    字段映射说明：
    - TwitterAPI.io: 使用驼峰命名（如 userName, isBlueVerified, profilePicture）
    - Twitter 官方 API: 使用下划线命名（如 profile_image_url, public_metrics）
    - 本模型: 统一使用下划线命名，便于 Python 代码风格一致性

    数据来源：
    1. get_following() - 使用 TwitterAPI.io，字段丰富完整
    2. get_me() - 使用 Twitter 官方 API，字段相对基础，某些字段可能为 None
    """

    # 基础信息 - 可选字段（嵌套数据可能不完整）
    id: Optional[str] = Field(None, description="用户 ID")
    name: Optional[str] = Field(None, description="用户显示名称")
    username: Optional[str] = Field(None, description="用户名（不含@符号）")

    # 基础信息 - 可选字段
    url: Optional[str] = Field(None, description="用户主页URL")
    twitter_url: Optional[str] = Field(None, description="Twitter用户页面URL")

    # 认证信息
    is_verified: Optional[bool] = Field(None, description="是否认证")
    is_blue_verified: Optional[bool] = Field(None, description="是否蓝V认证")
    verified_type: Optional[str] = Field(None, description="认证类型")

    # 头像和封面
    profile_picture: Optional[str] = Field(None, description="用户头像 URL")
    cover_picture: Optional[str] = Field(None, description="封面图片 URL")

    # 用户信息
    description: Optional[str] = Field(None, description="用户简介")
    location: Optional[str] = Field(None, description="用户位置")
    created_at: Optional[str] = Field(None, description="账户创建时间")

    # 统计数据
    followers_count: Optional[int] = Field(None, description="粉丝数")
    following_count: Optional[int] = Field(None, description="关注数")
    statuses_count: Optional[int] = Field(None, description="推文数")
    favourites_count: Optional[int] = Field(None, description="点赞数")
    media_count: Optional[int] = Field(None, description="媒体数")
    fast_followers_count: Optional[int] = Field(None, description="快速关注者数")

    # 功能属性
    can_dm: Optional[bool] = Field(None, description="是否可私信")
    can_media_tag: Optional[bool] = Field(None, description="是否可标记媒体")
    has_custom_timelines: Optional[bool] = Field(None, description="是否有自定义时间线")
    is_translator: Optional[bool] = Field(None, description="是否是翻译者")
    is_automated: Optional[bool] = Field(None, description="是否是自动化账号")
    automated_by: Optional[str] = Field(None, description="自动化账号的管理者")
    possibly_sensitive: Optional[bool] = Field(None, description="是否可能敏感")
    status: Optional[str] = Field(None, description="用户状态")

    # 限制信息
    withheld_in_countries: Optional[List[str]] = Field(
        None, description="限制访问的国家"
    )
    unavailable: Optional[bool] = Field(None, description="是否不可用")
    unavailable_reason: Optional[str] = Field(None, description="不可用原因")
    message: Optional[str] = Field(None, description="消息")

    # 固定推文
    pinned_tweet_ids: Optional[List[str]] = Field(None, description="固定推文ID列表")

    # 高级标签
    affiliates_highlighted_label: Optional[Dict[str, Any]] = Field(
        None, description="关联高亮标签"
    )

    # 个人资料详情
    profile_bio: Optional[ProfileBio] = Field(None, description="个人资料详细信息")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    @classmethod
    def from_twitterapi_io(cls, api_data: dict) -> "TwitterUser":
        """
        从 TwitterAPI.io 返回的数据创建 TwitterUser 实例

        Args:
            api_data: TwitterAPI.io 返回的用户数据字典

        Returns:
            TwitterUser 实例
        """
        return cls(
            # 基础信息（允许为空）
            id=str(api_data.get("id")) if api_data.get("id") else None,
            name=api_data.get("name") or None,
            username=api_data.get("userName") or None,
            url=api_data.get("url"),
            twitter_url=api_data.get("twitterUrl"),
            # 认证信息
            is_verified=api_data.get("isVerified"),
            is_blue_verified=api_data.get("isBlueVerified"),
            verified_type=api_data.get("verifiedType"),
            # 头像和封面
            profile_picture=api_data.get("profilePicture"),
            cover_picture=api_data.get("coverPicture"),
            # 用户信息
            description=api_data.get("description"),
            location=api_data.get("location"),
            created_at=api_data.get("createdAt"),
            # 统计数据
            followers_count=api_data.get("followers"),
            following_count=api_data.get("following"),
            statuses_count=api_data.get("statusesCount"),
            favourites_count=api_data.get("favouritesCount"),
            media_count=api_data.get("mediaCount"),
            fast_followers_count=api_data.get("fastFollowersCount"),
            # 功能属性
            can_dm=api_data.get("canDm"),
            can_media_tag=api_data.get("canMediaTag"),
            has_custom_timelines=api_data.get("hasCustomTimelines"),
            is_translator=api_data.get("isTranslator"),
            is_automated=api_data.get("isAutomated"),
            automated_by=api_data.get("automatedBy"),
            possibly_sensitive=api_data.get("possiblySensitive"),
            status=api_data.get("status"),
            # 限制信息
            withheld_in_countries=api_data.get("withheldInCountries"),
            unavailable=api_data.get("unavailable"),
            unavailable_reason=api_data.get("unavailableReason"),
            message=api_data.get("message"),
            # 固定推文
            pinned_tweet_ids=api_data.get("pinnedTweetIds"),
            # 高级标签
            affiliates_highlighted_label=api_data.get("affiliatesHighlightedLabel"),
            # 个人资料详情
            profile_bio=(
                ProfileBio(**api_data["profile_bio"])
                if api_data.get("profile_bio")
                else None
            ),
        )

    @classmethod
    def from_twitter_official_api(cls, user_data) -> "TwitterUser":
        """
        从 Twitter 官方 API 返回的数据创建 TwitterUser 实例

        Args:
            user_data: Twitter 官方 API 返回的用户数据对象

        Returns:
            TwitterUser 实例
        """
        # 提取 public_metrics 中的统计数据
        public_metrics = getattr(user_data, "public_metrics", {}) or {}

        # 构建参数字典，只包含有值的字段
        kwargs = {
            # 基础信息（允许为空）
            "id": (
                str(user_data.id) if hasattr(user_data, "id") and user_data.id else None
            ),
            "name": (
                user_data.name
                if hasattr(user_data, "name") and user_data.name
                else None
            ),
            "username": (
                user_data.username
                if hasattr(user_data, "username") and user_data.username
                else None
            ),
        }

        # 可选字段 - 只有当值存在时才添加
        if hasattr(user_data, "url") and user_data.url:
            kwargs["url"] = user_data.url

        if hasattr(user_data, "verified") and user_data.verified is not None:
            kwargs["is_blue_verified"] = user_data.verified

        if hasattr(user_data, "profile_image_url") and user_data.profile_image_url:
            kwargs["profile_picture"] = user_data.profile_image_url

        if hasattr(user_data, "description") and user_data.description:
            kwargs["description"] = user_data.description

        if hasattr(user_data, "location") and user_data.location:
            kwargs["location"] = user_data.location

        if hasattr(user_data, "created_at") and user_data.created_at:
            kwargs["created_at"] = user_data.created_at.isoformat()

        # 统计数据 - 从 public_metrics 中提取
        if public_metrics.get("followers_count") is not None:
            kwargs["followers_count"] = public_metrics.get("followers_count")
        if public_metrics.get("following_count") is not None:
            kwargs["following_count"] = public_metrics.get("following_count")
        if public_metrics.get("tweet_count") is not None:
            kwargs["statuses_count"] = public_metrics.get("tweet_count")
        if public_metrics.get("like_count") is not None:
            kwargs["favourites_count"] = public_metrics.get("like_count")

        return cls(**kwargs)


class TweetHashtag(BaseModel):
    """推文中的话题标签"""

    text: str = Field(..., description="话题标签文本（不含#）")
    indices: List[int] = Field(..., description="话题标签在文本中的位置索引")


class TweetUserMention(BaseModel):
    """推文中的用户提及"""

    id_str: str = Field(..., description="被提及用户的ID")
    name: str = Field(..., description="被提及用户的显示名称")
    screen_name: str = Field(..., description="被提及用户的用户名")


class TweetEntities(BaseModel):
    """推文实体信息"""

    hashtags: Optional[List[TweetHashtag]] = Field(
        default_factory=list, description="话题标签列表"
    )
    urls: Optional[List[TweetUrl]] = Field(default_factory=list, description="URL列表")
    user_mentions: Optional[List[TweetUserMention]] = Field(
        default_factory=list, description="用户提及列表"
    )


class Tweet(BaseModel):
    """
    Twitter 推文模型 - 完整版

    支持 TwitterAPI.io 返回的所有推文字段，包括基础信息、互动指标、实体信息等。
    """

    # 基础信息
    type: str = Field(default="tweet", description="内容类型")
    id: str = Field(..., description="推文 ID")
    url: str = Field(..., description="推文URL")
    twitter_url: Optional[str] = Field(None, description="Twitter推文URL")
    text: str = Field(..., description="推文内容")
    source: Optional[str] = Field(None, description="推文来源")
    lang: Optional[str] = Field(None, description="推文语言")
    created_at: str = Field(..., description="创建时间")

    # 作者信息（嵌套推文可能没有完整作者信息）
    author: Optional[TwitterUser] = Field(None, description="推文作者信息")

    # 互动指标
    retweet_count: int = Field(0, description="转发数")
    reply_count: int = Field(0, description="回复数")
    like_count: int = Field(0, description="点赞数")
    quote_count: int = Field(0, description="引用数")
    view_count: Optional[int] = Field(None, description="浏览数")
    bookmark_count: Optional[int] = Field(None, description="收藏数")

    # 回复相关
    is_reply: bool = Field(False, description="是否是回复")
    in_reply_to_id: Optional[str] = Field(None, description="回复的推文ID")
    conversation_id: Optional[str] = Field(None, description="对话ID")
    in_reply_to_user_id: Optional[str] = Field(None, description="回复的用户ID")
    in_reply_to_username: Optional[str] = Field(None, description="回复的用户名")

    # 实体信息
    entities: Optional[TweetEntities] = Field(None, description="推文中的实体信息")

    # 附加信息
    extended_entities: Optional[Dict[str, Any]] = Field(
        None, description="扩展实体信息（媒体等）"
    )
    card: Optional[Dict[str, Any]] = Field(None, description="Twitter卡片信息")
    place: Optional[Dict[str, Any]] = Field(None, description="位置信息")
    article: Optional[Dict[str, Any]] = Field(None, description="文章信息")

    # 引用和转发
    quoted_tweet: Optional["Tweet"] = Field(None, description="引用的推文")
    retweeted_tweet: Optional["Tweet"] = Field(None, description="转发的推文")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    @classmethod
    def from_twitterapi_io(cls, api_data: dict) -> "Tweet":
        """
        从 TwitterAPI.io 返回的数据创建 Tweet 实例

        Args:
            api_data: TwitterAPI.io 返回的推文数据字典

        Returns:
            Tweet 实例
        """
        # 处理作者信息
        try:
            author = (
                TwitterUser.from_twitterapi_io(api_data["author"])
                if api_data.get("author")
                else None
            )
        except Exception:
            author = None

        # 处理实体信息
        entities_data = api_data.get("entities", {})
        entities = None
        if entities_data:
            entities = TweetEntities(
                hashtags=[TweetHashtag(**h) for h in entities_data.get("hashtags", [])],
                urls=[TweetUrl(**u) for u in entities_data.get("urls", [])],
                user_mentions=[
                    TweetUserMention(**m)
                    for m in entities_data.get("user_mentions", [])
                ],
            )

        # 递归处理引用和转发的推文（允许解析失败）
        quoted_tweet = None
        if api_data.get("quoted_tweet"):
            try:
                quoted_tweet = cls.from_twitterapi_io(api_data["quoted_tweet"])
            except Exception:
                # 如果解析引用推文失败，保持为None
                quoted_tweet = None

        retweeted_tweet = None
        if api_data.get("retweeted_tweet"):
            try:
                retweeted_tweet = cls.from_twitterapi_io(api_data["retweeted_tweet"])
            except Exception:
                # 如果解析转发推文失败，保持为None
                retweeted_tweet = None

        return cls(
            # 基础信息
            type=api_data.get("type", "tweet"),
            id=api_data.get("id", ""),
            url=api_data.get("url", ""),
            twitter_url=api_data.get("twitterUrl"),
            text=api_data.get("text", ""),
            source=api_data.get("source"),
            lang=api_data.get("lang"),
            created_at=api_data.get("createdAt", ""),
            # 作者信息
            author=author,
            # 互动指标
            retweet_count=api_data.get("retweetCount", 0),
            reply_count=api_data.get("replyCount", 0),
            like_count=api_data.get("likeCount", 0),
            quote_count=api_data.get("quoteCount", 0),
            view_count=api_data.get("viewCount"),
            bookmark_count=api_data.get("bookmarkCount"),
            # 回复相关
            is_reply=api_data.get("isReply", False),
            in_reply_to_id=api_data.get("inReplyToId"),
            conversation_id=api_data.get("conversationId"),
            in_reply_to_user_id=api_data.get("inReplyToUserId"),
            in_reply_to_username=api_data.get("inReplyToUsername"),
            # 实体信息
            entities=entities,
            # 附加信息
            extended_entities=api_data.get("extendedEntities"),
            card=api_data.get("card"),
            place=api_data.get("place"),
            article=api_data.get("article"),
            # 引用和转发
            quoted_tweet=quoted_tweet,
            retweeted_tweet=retweeted_tweet,
        )


# 更新模型前向引用
Tweet.model_rebuild()


class TwitterFollowingResponse(BaseModel):
    """Twitter 关注列表响应模型"""

    users: List[TwitterUser] = Field(..., description="用户关注的所有用户列表")
    total_count: int = Field(..., description="总关注数量")
    next_token: Optional[str] = Field(None, description="分页令牌，用于获取下一页数据")


class TweetListResponse(BaseModel):
    """Twitter 推文列表响应模型"""

    tweets: List[Tweet] = Field(..., description="推文列表")
    has_next_page: bool = Field(False, description="是否有下一页")
    next_cursor: Optional[str] = Field(None, description="下一页游标")


class UserLastTweetsResponse(BaseModel):
    """用户最新推文响应模型"""

    tweets: List[Tweet] = Field(..., description="推文列表，按创建时间排序")
    has_next_page: bool = Field(False, description="是否有下一页")
    next_cursor: Optional[str] = Field(None, description="下一页游标")
    status: str = Field(..., description="API响应状态")
    message: Optional[str] = Field(None, description="响应消息")


# 推文格式化工具函数


def format_tweet_for_analysis(tweet: Tweet) -> str:
    """
    将推文格式化为适合LLM分析的简洁字符串格式

    专注于推文的实际内容，包含推文ID和多媒体信息，便于LLM通过tool call
    进一步查看详细内容。适合RAG系统的LLM进行内容分析和处理。

    包含的关键信息：
    - 推文ID（原文、转发、引用、回复的ID）
    - 实际内容和作者信息
    - 多媒体内容标识（简单提示有无多媒体内容）
    - 简化的上下文信息

    Args:
        tweet: Tweet对象

    Returns:
        格式化后的推文字符串，包含ID和多媒体标识，便于LLM理解和后续tool call
    """
    # 获取模板文件路径
    template_dir = Path(__file__).parent.parent / "template"

    # 设置Jinja2环境
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("tweet_template.j2")

    # 渲染模板
    return template.render(tweet=tweet)


def format_tweets_batch(tweets: List[Tweet]) -> str:
    """
    批量格式化推文列表，专注于内容本身，包含ID和多媒体信息

    每条推文包含：
    - 推文ID（便于LLM调用tool进一步查看）
    - 实际内容和作者信息
    - 多媒体内容标识（简单提示有无多媒体内容）
    - 转发/引用/回复关系的ID

    Args:
        tweets: 推文列表

    Returns:
        格式化后的所有推文字符串，包含ID和多媒体标识，适合LLM分析和后续tool call
    """
    if not tweets:
        return "没有可用的推文数据"

    formatted_tweets = []
    for tweet in tweets:
        tweet_content = format_tweet_for_analysis(tweet)
        # 移除多余的标题，直接展示内容
        formatted_tweets.append(tweet_content)

    return "\n\n".join(formatted_tweets)


def format_user_for_analysis(user: TwitterUser) -> str:
    """
    将用户信息格式化为适合分析的字符串格式

    Args:
        user: TwitterUser对象

    Returns:
        格式化后的用户信息字符串
    """
    # 获取模板文件路径
    template_dir = Path(__file__).parent.parent / "template"

    # 设置Jinja2环境
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("user_template.j2")

    # 渲染模板
    return template.render(user=user)

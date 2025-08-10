"""
LiteLLM 工具测试基类。

提供了一个标准化的测试框架，用于测试 LiteLLM 工具的集成。
新的工具测试只需要继承 BaseToolTest 类并实现必要的方法即可。
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

import litellm

from common.config.config import get_workflow_config
from common.utils.logger import get_logger

logger = get_logger(__name__)
"""模块日志记录器。"""


class BaseToolTest(ABC):
    """
    LiteLLM 工具测试的基类。

    提供了标准化的测试流程，子类只需要实现以下抽象方法：
    - get_tool_definitions(): 返回工具定义列表
    - get_test_prompt(): 返回测试提示
    - execute_tool_function(): 执行实际的工具函数
    - get_test_name(): 返回测试名称

    Attributes:
        model (str): 使用的模型名称，默认为 Claude Sonnet 4
        api_key (str): API 密钥，从配置中自动获取
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """
        初始化测试类。

        Args:
            model (str): 使用的模型名称
        """
        self.model: str = model
        """LiteLLM 使用的模型名称。"""

        workflow_config = get_workflow_config()
        self.api_key: str = workflow_config.anthropic_api_key
        """Anthropic API 密钥。"""

    @abstractmethod
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        获取工具定义列表。

        Returns:
            List[Dict[str, Any]]: LiteLLM 工具定义字典列表
        """
        pass

    @abstractmethod
    def get_test_prompt(self) -> str:
        """
        获取测试提示。

        Returns:
            str: 用于触发工具调用的测试提示
        """
        pass

    @abstractmethod
    async def execute_tool_function(self, tool_name: str, args: Dict[str, Any]) -> None:
        """
        执行工具函数。

        Args:
            tool_name (str): 工具名称
            args (Dict[str, Any]): 工具参数字典
        """
        pass

    @abstractmethod
    def get_test_name(self) -> str:
        """
        获取测试名称。

        Returns:
            str: 测试的显示名称
        """
        pass

    async def test_with_litellm(self) -> None:
        """
        使用 LiteLLM 进行工具测试。

        执行完整的测试流程：
        1. 获取工具定义和测试提示
        2. 调用 LiteLLM
        3. 处理响应和工具调用
        4. 执行工具函数
        """
        # 准备工具和消息
        tools: List[Dict[str, Any]] = self.get_tool_definitions()
        """工具定义列表。"""

        messages: List[Dict[str, str]] = [
            {"role": "user", "content": self.get_test_prompt()}
        ]
        """对话消息列表。"""

        try:
            # 调用 LiteLLM
            print(f"正在使用 {self.model} 模型进行工具调用测试...")
            print(f"测试提示: {self.get_test_prompt()}")
            print("-" * 50)

            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                api_key=self.api_key,
            )

            # 处理响应
            await self._handle_response(response)

        except Exception as e:
            print(f"\n❌ LiteLLM 调用失败: {str(e)}")
            print("测试失败：无法完成 LiteLLM 工具调用测试")
            raise  # 重新抛出异常，让测试失败

    async def _handle_response(self, response: Any) -> None:
        """
        处理 LiteLLM 响应。

        Args:
            response: LiteLLM 响应对象
        """
        choices = getattr(response, "choices", None)
        if choices and len(choices) > 0:
            choice = choices[0]
            message = getattr(choice, "message", None)

            if message:
                # 检查是否有工具调用
                tool_calls = getattr(message, "tool_calls", None)
                if tool_calls:
                    print("\n✅ 模型请求使用工具:")

                    for tool_call in tool_calls:
                        function = getattr(tool_call, "function", None)
                        if function:
                            tool_name: str = getattr(function, "name", "")
                            tool_args_str: str = getattr(function, "arguments", "{}")
                            tool_args: Dict[str, Any] = json.loads(tool_args_str)

                            print(f"\n📋 工具名称: {tool_name}")
                            print(
                                f"📋 工具参数: {json.dumps(tool_args, ensure_ascii=False, indent=2)}"
                            )

                            # 执行工具函数
                            await self.execute_tool_function(tool_name, tool_args)
                else:
                    # 模型没有使用工具，直接返回了文本
                    print("\n⚠️  模型没有调用工具，而是返回了文本响应:")
                    content = getattr(message, "content", None)
                    if content:
                        print(content)
            else:
                print("\n❌ 无法获取消息对象")
        else:
            print("\n❌ 响应格式异常，无法解析")

    async def run(self) -> None:
        """
        运行测试。

        这是测试的主入口，打印测试标题并执行测试。
        """
        print("=" * 70)
        print(f"🚀 {self.get_test_name()} - LiteLLM 集成测试")
        print("=" * 70)

        await self.test_with_litellm()

        print("\n" + "=" * 70)
        print("测试完成")
        print("=" * 70)


def create_test_runner(test_class: type[BaseToolTest]) -> None:
    """
    创建测试运行器。

    这是一个辅助函数，用于在 if __name__ == "__main__" 中运行测试。

    Args:
        test_class: 继承自 BaseToolTest 的测试类

    Example:
        if __name__ == "__main__":
            create_test_runner(MyToolTest)
    """

    async def main():
        test = test_class()
        await test.run()

    asyncio.run(main())

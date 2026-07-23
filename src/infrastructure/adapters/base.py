"""Tool Adapter 抽象接口"""

from abc import ABC, abstractmethod

from src.core.models import FaultContext, ToolOutput


class ToolAdapter(ABC):
    """诊断工具适配器抽象基类

    所有诊断工具（MCP、网页抓取、API等）必须实现此接口。
    新增工具类型只需继承此类并实现 execute 方法。
    """

    def __init__(self, config: dict):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """显示名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """给 LLM 看的工具说明"""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """工具分类（electrical/environmental/biological/...）"""
        ...

    @abstractmethod
    async def execute(self, context: FaultContext) -> ToolOutput:
        """执行诊断

        Args:
            context: 故障上下文

        Returns:
            ToolOutput: 统一包装的工具输出
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, category={self.category})>"

"""Command 抽象基类"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from src.core.models import Event, ExecutionContext


class Command(ABC):
    """Command 抽象基类

    所有用户操作封装为独立 Command。
    """

    @abstractmethod
    async def execute(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        """执行 Command

        Args:
            ctx: 执行上下文

        Yields:
            Event: 执行过程中的事件
        """
        ...

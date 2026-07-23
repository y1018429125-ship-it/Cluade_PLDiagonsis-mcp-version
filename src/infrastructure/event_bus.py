"""事件总线

内存事件总线，支持发布-订阅模式。
预留 Redis 扩展接口。
"""

import asyncio
import logging
from collections import defaultdict
from typing import Callable, Dict, List

from src.core.models import Event

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], None]


class EventBus:
    """事件总线"""

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._session_subscribers: Dict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """订阅指定类型的事件"""
        self._subscribers[event_type].append(handler)
        logger.debug(f"订阅事件: {event_type}")

    def subscribe_session(self, session_id: str, handler: EventHandler) -> None:
        """订阅指定会话的所有事件"""
        self._session_subscribers[session_id].append(handler)
        logger.debug(f"订阅会话: {session_id}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消订阅"""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def unsubscribe_session(self, session_id: str, handler: EventHandler) -> None:
        """取消会话订阅"""
        if handler in self._session_subscribers[session_id]:
            self._session_subscribers[session_id].remove(handler)

    async def publish(self, event: Event) -> None:
        """发布事件"""
        # 按事件类型分发
        handlers = self._subscribers.get(event.event_type.value, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"事件处理失败: {e}")

        # 按会话 ID 分发
        session_handlers = self._session_subscribers.get(event.session_id, [])
        for handler in session_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"会话事件处理失败: {e}")

        logger.debug(f"发布事件: {event.event_type.value} -> session={event.session_id}")

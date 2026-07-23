"""Tests for src/infrastructure/event_bus.py — publish/subscribe mechanics."""

import asyncio

import pytest

from src.core.models import Event, EventType
from src.infrastructure.event_bus import EventBus


# ============================================================================
# subscribe / unsubscribe
# ============================================================================


def test_subscribe_stores_handler() -> None:
    """subscribe() registers a handler under the given event type."""
    bus = EventBus()
    called = []

    def handler(event: Event) -> None:
        called.append(event)

    bus.subscribe("start", handler)
    assert handler in bus._subscribers["start"]


def test_unsubscribe_removes_handler() -> None:
    """unsubscribe() removes a previously registered handler."""
    bus = EventBus()

    def handler(event: Event) -> None:
        pass

    bus.subscribe("start", handler)
    bus.unsubscribe("start", handler)
    assert handler not in bus._subscribers["start"]


def test_subscribe_session_stores_handler() -> None:
    """subscribe_session() registers a handler for a specific session id."""
    bus = EventBus()

    def handler(event: Event) -> None:
        pass

    bus.subscribe_session("sess_1", handler)
    assert handler in bus._session_subscribers["sess_1"]


def test_unsubscribe_session_removes_handler() -> None:
    """unsubscribe_session() removes a session-specific handler."""
    bus = EventBus()

    def handler(event: Event) -> None:
        pass

    bus.subscribe_session("sess_1", handler)
    bus.unsubscribe_session("sess_1", handler)
    assert handler not in bus._session_subscribers["sess_1"]


# ============================================================================
# publish — event type routing
# ============================================================================


@pytest.mark.asyncio
async def test_publish_delivers_to_type_subscribers() -> None:
    """publish() invokes handlers registered for the event's type."""
    bus = EventBus()
    received: list = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("start", handler)
    await bus.publish(Event.start("sess_1"))

    assert len(received) == 1
    assert received[0].event_type == EventType.START


@pytest.mark.asyncio
async def test_publish_delivers_to_session_subscribers() -> None:
    """publish() invokes handlers registered for the event's session id."""
    bus = EventBus()
    received: list = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe_session("sess_1", handler)
    await bus.publish(Event.start("sess_1"))

    assert len(received) == 1
    assert received[0].session_id == "sess_1"


@pytest.mark.asyncio
async def test_publish_does_not_deliver_to_other_types() -> None:
    """publish() skips handlers registered for different event types."""
    bus = EventBus()
    received: list = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("result", handler)
    await bus.publish(Event.start("sess_1"))

    assert len(received) == 0


@pytest.mark.asyncio
async def test_publish_does_not_deliver_to_other_sessions() -> None:
    """publish() skips session handlers for different session ids."""
    bus = EventBus()
    received: list = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe_session("sess_2", handler)
    await bus.publish(Event.start("sess_1"))

    assert len(received) == 0


# ============================================================================
# publish — sync and async handlers
# ============================================================================


@pytest.mark.asyncio
async def test_publish_supports_sync_handler() -> None:
    """publish() correctly calls synchronous handlers."""
    bus = EventBus()
    received: list = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("start", handler)
    await bus.publish(Event.start("sess_1"))

    assert len(received) == 1


@pytest.mark.asyncio
async def test_publish_supports_async_handler() -> None:
    """publish() correctly awaits asynchronous handlers."""
    bus = EventBus()
    received: list = []

    async def handler(event: Event) -> None:
        await asyncio.sleep(0)
        received.append(event)

    bus.subscribe("start", handler)
    await bus.publish(Event.start("sess_1"))

    assert len(received) == 1


# ============================================================================
# publish — error resilience
# ============================================================================


@pytest.mark.asyncio
async def test_publish_survives_handler_exception() -> None:
    """publish() continues delivering to other handlers when one raises."""
    bus = EventBus()
    received: list = []

    def bad_handler(event: Event) -> None:
        raise RuntimeError("boom")

    def good_handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("start", bad_handler)
    bus.subscribe("start", good_handler)
    await bus.publish(Event.start("sess_1"))

    assert len(received) == 1


@pytest.mark.asyncio
async def test_publish_survives_async_handler_exception() -> None:
    """publish() continues when an async handler raises."""
    bus = EventBus()
    received: list = []

    async def bad_handler(event: Event) -> None:
        raise RuntimeError("boom")

    async def good_handler(event: Event) -> None:
        received.append(event)

    bus.subscribe("start", bad_handler)
    bus.subscribe("start", good_handler)
    await bus.publish(Event.start("sess_1"))

    assert len(received) == 1

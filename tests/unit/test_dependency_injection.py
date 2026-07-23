"""Tests for src/interfaces/dependency_injection.py — Container and get_container."""

from unittest.mock import AsyncMock

import pytest

from src.interfaces.dependency_injection import Container, get_container


# ============================================================================
# Container
# ============================================================================


def test_container_initializes_components() -> None:
    """Container.__init__ wires all dependencies."""
    container = Container()

    assert container.config is not None
    assert container.event_bus is not None
    assert container.llm_service is not None
    assert container.tool_registry is not None
    assert container.state_machine is not None
    assert container.session_manager is not None
    assert container.intent_classifier is not None
    assert container.report_engine is not None
    assert container.template_parser is not None


@pytest.mark.asyncio
async def test_container_init_delegates_to_registry() -> None:
    """Container.init() awaits tool_registry.load_tools()."""
    container = Container()
    container.tool_registry.load_tools = AsyncMock()

    await container.init()

    container.tool_registry.load_tools.assert_awaited_once()


# ============================================================================
# get_container
# ============================================================================


def test_get_container_returns_same_instance() -> None:
    """get_container() is cached and returns the same object."""
    c1 = get_container()
    c2 = get_container()

    assert c1 is c2


def test_get_container_is_container_instance() -> None:
    """get_container() returns a Container."""
    container = get_container()

    assert isinstance(container, Container)

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.adapters.browser.controller import BrowserController


class TestBrowserController:
    @pytest.fixture
    def controller(self):
        return BrowserController(headless=True)

    @pytest.mark.asyncio
    async def test_launch_starts_browser(self, controller):
        """launch() 应启动 browser 和 context"""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch(
            "src.infrastructure.adapters.browser.controller.async_playwright",
            return_value=AsyncMock(
                start=AsyncMock(return_value=mock_playwright),
                stop=AsyncMock(),
            ),
        ):
            await controller.launch()

        assert controller.browser is mock_browser
        assert controller.context is mock_context
        assert controller.page is mock_page
        mock_playwright.chromium.launch.assert_awaited_once_with(headless=True)

    @pytest.mark.asyncio
    async def test_screenshot_returns_bytes(self, controller):
        """screenshot() 应返回 PNG 字节"""
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock(return_value=b"fake_png")
        controller.page = mock_page

        result = await controller.screenshot()
        assert result == b"fake_png"
        mock_page.screenshot.assert_awaited_once_with(full_page=True, type="png")

    @pytest.mark.asyncio
    async def test_screenshot_raises_when_not_launched(self, controller):
        """screenshot() 在浏览器未启动时应抛出 RuntimeError"""
        with pytest.raises(RuntimeError, match="浏览器未启动"):
            await controller.screenshot()

    @pytest.mark.asyncio
    async def test_close_releases_resources(self, controller):
        """close() 应关闭 context、browser 和 playwright"""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()

        mock_context.close = AsyncMock()
        mock_browser.close = AsyncMock()
        mock_playwright.stop = AsyncMock()

        controller._playwright = mock_playwright
        controller.browser = mock_browser
        controller.context = mock_context
        controller.page = MagicMock()

        await controller.close()

        mock_context.close.assert_awaited_once()
        mock_browser.close.assert_awaited_once()
        mock_playwright.stop.assert_awaited_once()
        assert controller.page is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """异步上下文管理器应正确启动和关闭"""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        mock_browser.close = AsyncMock()
        mock_playwright.stop = AsyncMock()

        with patch(
            "src.infrastructure.adapters.browser.controller.async_playwright",
            return_value=AsyncMock(
                start=AsyncMock(return_value=mock_playwright),
                stop=AsyncMock(),
            ),
        ):
            async with BrowserController(headless=True) as ctrl:
                assert ctrl.page is mock_page

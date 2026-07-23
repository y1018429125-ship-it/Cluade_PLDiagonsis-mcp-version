"""Playwright 浏览器生命周期管理器"""

import logging
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)


class BrowserController:
    """管理 Playwright 浏览器的启动、页面创建、截图和关闭。"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def launch(self) -> None:
        """启动 headless Chromium 浏览器。"""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        self.page = await self.context.new_page()
        logger.info("浏览器启动完成")

    async def screenshot(self) -> bytes:
        """截取当前页面全屏截图，返回 PNG 字节。"""
        if self.page is None:
            raise RuntimeError("浏览器未启动，请先调用 launch()")
        return await self.page.screenshot(full_page=True, type="png")

    async def close(self) -> None:
        """关闭浏览器并释放资源。"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.page = None
        self.context = None
        self.browser = None
        self._playwright = None
        logger.info("浏览器已关闭")

    async def __aenter__(self):
        await self.launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

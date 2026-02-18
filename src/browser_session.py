from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.config import EnvConfig
from src.proxy_provider import ProxyEndpoint


@dataclass
class BrowserSession:
    env: EnvConfig
    proxy: ProxyEndpoint | None = None

    def __post_init__(self) -> None:
        self._playwright = None
        self.browser = None
        self.context = None

    def __enter__(self) -> "BrowserSession":
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": self.env.browser_headless}
        if self.proxy:
            launch_kwargs["proxy"] = {
                "server": f"{self.proxy.protocol}://{self.proxy.host}:{self.proxy.port}",
                "username": self.proxy.username or None,
                "password": self.proxy.password or None,
            }
        self.browser = self._playwright.chromium.launch(**launch_kwargs)
        self.context = self.browser.new_context()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self._playwright:
            self._playwright.stop()

    def open_page(self, url: str):
        if not self.context:
            raise RuntimeError("BrowserSession is not initialized.")
        page = self.context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        return page


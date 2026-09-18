"""Headless browser capability check and page fetch, backed by Bundle's Playwright wrapper.

Atlas' Hermes gateway runs on Jetson (ARM64), where Chrome-for-Testing has no
build and `browser-use`/`agent-browser` can't launch without a system-apt
Chromium (root). Atlas itself (x86_64, RTX 3090) already ships a working
Chromium via Playwright in `.venv`, wrapped by `bundle.core.browser.Browser`.
This module exposes that as a reusable Atlas capability instead of a one-off
script, so any agent/script on Atlas can drive a real headless browser.
"""

from __future__ import annotations

from bundle.core import Data
from bundle.core.browser import Browser


class PageResult(Data):
    """Outcome of fetching one URL with a headless browser."""

    url: str
    title: str
    status: int | None = None


async def check() -> bool:
    """Launch and immediately close headless Chromium; True if it works end to end."""
    async with Browser.chromium(headless=True) as browser:
        page = await browser.new_page()
        await page.goto("https://example.com", wait_until="domcontentloaded")
        title = await page.title()
        return title == "Example Domain"


async def fetch(url: str, *, headless: bool = True, wait_until: str = "domcontentloaded") -> PageResult:
    """Fetch one URL with headless Chromium and return its title and HTTP status."""
    async with Browser.chromium(headless=headless) as browser:
        page = await browser.new_page()
        response = await page.goto(url, wait_until=wait_until)
        title = await page.title()
        return PageResult(url=url, title=title, status=response.status if response else None)

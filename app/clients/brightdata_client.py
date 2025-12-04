from typing import Any

import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from app.config import settings
from app.errors import ScraperError, ScraperErrorCode


class BrightDataClient:
    """
    Клиент для Browser API Bright Data.

    Сейчас у него одна ключевая функция:
    - fetch_page_html(url): вернуть HTML произвольной страницы (Google, сайт и т.д.)
    """

    def __init__(self, http_client: httpx.AsyncClient):
        # http_client оставляем на будущее (если понадобятся HTTP-эндпоинты Bright Data)
        self.http_client = http_client

    async def fetch_page_html(self, url: str) -> str:
        """
        Загружает страницу через удалённый браузер Bright Data (Browser API, WebSocket/CDP)
        и возвращает её HTML.

        Используется и для:
        - Google SERP (по заранее собранному URL),
        - fetch-site (главная + внутренние страницы).
        """
        ws_endpoint = settings.brightdata_browser_ws_url
        timeout_ms = settings.brightdata_page_timeout_sec * 1000

        try:
            async with async_playwright() as p:
                # подключаемся к удалённому браузеру Bright Data
                browser = await p.chromium.connect_over_cdp(ws_endpoint)
                page = await browser.new_page()

                try:
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                    html = await page.content()
                    return html
                finally:
                    await browser.close()

        except PlaywrightTimeoutError as e:
            # маппим на error_code="timeout"
            raise ScraperError(
                "Bright Data Browser API timeout",
                ScraperErrorCode.timeout,
            ) from e
        except Exception as e:
            # любая другая ошибка сети / браузера → source_unavailable
            raise ScraperError(
                "Bright Data Browser API error",
                ScraperErrorCode.source_unavailable,
            ) from e


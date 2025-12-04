from urllib.parse import urlencode

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from app.config import settings
from app.errors import (
    YandexCaptchaError,
    YandexTimeoutError,
    YandexSourceUnavailableError,
)


class YandexClient:
    def __init__(self):
        proxy_server = f"http://{settings.yandex_proxy_host}:{settings.yandex_proxy_port}"
        self._proxy = {
            "server": proxy_server,
            "username": settings.yandex_proxy_login,
            "password": settings.yandex_proxy_password,
        }
        self._timeout_ms = settings.yandex_request_timeout_sec

    def _build_url(self, query: str, page: int, locale: str, region: str) -> str:
        base = "https://yandex.ru/search/"
        params = {
            "text": query,
            "p": max(page - 1, 0),  # yandex pages start from 0
            "lr": region,
        }
        return f"{base}?{urlencode(params)}"

    @staticmethod
    def _contains_captcha(html: str) -> bool:
        markers = ["captcha", "robot", "Введите символы", "protect.yandex"]
        return any(m.lower() in html.lower() for m in markers)

    async def fetch_serp_html(self, query: str, page: int, locale: str, region: str) -> str:
        url = self._build_url(query, page, locale or "ru-RU", region)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    proxy=self._proxy,
                    locale=locale or "ru-RU",
                )
                page_obj = await context.new_page()
                await page_obj.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                html = await page_obj.content()
                await browser.close()
        except PlaywrightTimeout as e:
            raise YandexTimeoutError from e
        except Exception as e:
            raise YandexSourceUnavailableError from e

        if self._contains_captcha(html):
            raise YandexCaptchaError("Captcha / anti-bot detected")

        return html

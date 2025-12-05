# app/services/site_fetch_service.py

from __future__ import annotations
import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.brightdata_client import BrightDataClient
from app.errors import ScraperError, ErrorCode
from app.models.fetch_site import FetchSiteRequest, FetchSiteData, FetchedPage
from app.repositories.cache_repo import CacheRepo
from app.parsing.html_cleaner import clean_html, clean_html_minimal

logger = logging.getLogger(__name__)


class SiteFetchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.cache = CacheRepo(db)
        # свой http-клиент, который передаём в BrightDataClient
        self.http_client = httpx.AsyncClient()
        self.client = BrightDataClient(self.http_client)

    async def close(self) -> None:
        # закрываем httpx-клиент; BrightDataClient отдельного close не требует
        await self.http_client.aclose()

    # ---------- ВНУТРЕННИЙ HELPER ДЛЯ ОДНОЙ СТРАНИЦЫ ----------

    async def _fetch_single_page(self, url: str) -> str:
        """
        Забираем HTML одной страницы через Bright Data.
        Используем Browser / HTTP в зависимости от реализации BrightDataClient.
        """
        try:
            html = await self.client.fetch_page_html(url)
            return html
        except ScraperError:
            # пробрасываем наверх типизированную ошибку
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error while fetching single page: %s", url)
            raise ScraperError(ErrorCode.source_unavailable) from e

    # ---------- ПУБЛИЧНЫЙ МЕТОД ДЛЯ HTML-ЭНДПОИНТА ----------

    async def fetch_html_cleaned(self, url: str) -> str:
        """
        Для /api/v1/site/html:
        - забираем HTML главной страницы;
        - минимально очищаем (clean_html_minimal);
        - кэшируем по ключу site_request_hash.
        """
        params = FetchSiteRequest(url=url, max_pages=1)

        # кэш
        hash_key = self.cache.site_request_hash(params)
        cached = await self.cache.get_site(hash_key)
        if cached is not None:
            # из кэша берём уже очищенный HTML
            pages = cached.get("pages") or []
            if pages:
                return pages[0].get("html", "")

        raw_html = await self._fetch_single_page(str(params.url))
        cleaned = clean_html_minimal(raw_html)

        # сохраняем в кэш как "одна страница"
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self.cache.ttl_sec)

        page = FetchedPage(url=str(params.url), html=cleaned, truncated=False)
        data = FetchSiteData(pages=[page], partial=False)

        await self.cache.save_site(hash_key, params, data.dict(), created_at=now, expires_at=expires_at)

        return cleaned

    # ---------- СТАРЫЙ МЕТОД /api/v1/fetch-site (MVP ТЗ) ----------

    async def fetch_site(self, req: FetchSiteRequest) -> FetchSiteData:
        """
        Реализация ТЗ: главная страница + до N внутренних.
        Возвращает уже ОЧИЩЕННЫЙ HTML (clean_html).
        """

        params = req

        # кэш
        hash_key = self.cache.site_request_hash(params)
        cached = await self.cache.get_site(hash_key)
        if cached is not None:
            return FetchSiteData(**cached)

        # 1. загружаем главную
        root_html_raw = await self._fetch_single_page(str(params.url))
        root_html = clean_html(root_html_raw)

        root_page = FetchedPage(url=str(params.url), html=root_html, truncated=False)

        # 2. внутренние ссылки (в простом виде — парсинг через BeautifulSoup внутри BrightDataClient
        # или отдельного html_utils; тут не усложняю, оставляем как было в твоём коде).
        inner_urls = await self.client.extract_inner_links(str(params.url), root_html_raw, max_links=params.max_pages - 1)

        pages: List[FetchedPage] = [root_page]

        async def _fetch_inner(u: str) -> FetchedPage:
            raw = await self._fetch_single_page(u)
            cleaned_inner = clean_html(raw)
            return FetchedPage(url=u, html=cleaned_inner, truncated=False)

        tasks = [asyncio.create_task(_fetch_inner(u)) for u in inner_urls]
        if tasks:
            inner_pages = await asyncio.gather(*tasks, return_exceptions=False)
            pages.extend(inner_pages)

        data = FetchSiteData(pages=pages, partial=False)

        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self.cache.ttl_sec)
        await self.cache.save_site(hash_key, params, data.dict(), created_at=now, expires_at=expires_at)

        return data

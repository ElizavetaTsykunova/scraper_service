# app/services/site_fetch_service.py

from __future__ import annotations

import asyncio
import logging
from typing import List

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.brightdata_client import BrightDataClient
from app.errors import ScraperError, ErrorCode
from app.models.fetch_site import FetchSiteRequest, FetchSiteData, FetchedPage
from app.repositories.cache_repo import CacheRepo
from app.parsing.html_cleaner import clean_html, clean_html_minimal

logger = logging.getLogger(__name__)


class SiteFetchService:
    """
    Работа с сайтами:
    - fetch_site: главная + несколько внутренних страниц (старый /api/v1/fetch-site);
    - fetch_html_cleaned: только главная, минимально очищенный HTML (новый /api/v1/site/html).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.cache = CacheRepo(db)
        self.http_client = httpx.AsyncClient()
        self.client = BrightDataClient(self.http_client)

    async def close(self) -> None:
        await self.http_client.aclose()

    # ---------- ВНУТРЕННИЙ HELPER ДЛЯ ОДНОЙ СТРАНИЦЫ ----------

    async def _fetch_single_page(self, url: str) -> str:
        """
        Забираем HTML одной страницы через Bright Data.
        """
        try:
            html = await self.client.fetch_page_html(url)
            return html
        except ScraperError:
            # типизированные ошибки (timeout, source_unavailable и т.п.) пробрасываем как есть
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error while fetching single page: %s", url)
            raise ScraperError(ErrorCode.source_unavailable) from e

    # ---------- ПУБЛИЧНЫЙ МЕТОД ДЛЯ /api/v1/site/html ----------

    async def fetch_html_cleaned(self, url: str) -> str:
        """
        Для /api/v1/site/html:
        - забираем HTML главной страницы;
        - минимально очищаем (clean_html_minimal);
        - кэшируем как одну страницу в site_cache.
        """
        params = FetchSiteRequest(url=url, max_pages=1)

        # ---- пробуем взять из кэша
        hash_key = self.cache.site_request_hash(params)
        cached = await self.cache.get_site(hash_key)
        if cached is not None:
            try:
                payload = cached.response_data or {}
                pages = payload.get("pages") or []
                if pages:
                    return pages[0].get("html", "") or ""
            except Exception:
                # если структура кэша неожиданно битая — логируем и идём дальше без кэша
                logger.exception("Failed to read cached site HTML, ignore cache")

        # ---- грузим с нуля
        raw_html = await self._fetch_single_page(str(params.url))
        cleaned = clean_html_minimal(raw_html)

        page = FetchedPage(url=str(params.url), html=cleaned, truncated=False)
        data = FetchSiteData(pages=[page], partial=False)

        # CacheRepo сам выставит created_at / expires_at и TTL
        await self.cache.save_site(hash_key, params, data.dict())

        return cleaned

    # ---------- СТАРЫЙ МЕТОД /api/v1/fetch-site (MVP ТЗ) ----------

    async def fetch_site(self, req: FetchSiteRequest) -> FetchSiteData:
        """
        Реализация ТЗ: главная + до N внутренних страниц.
        Возвращает уже ОЧИЩЕННЫЙ HTML (clean_html).
        """
        params = req

        # ---- кэш
        hash_key = self.cache.site_request_hash(params)
        cached = await self.cache.get_site(hash_key)
        if cached is not None:
            try:
                return FetchSiteData(**cached.response_data)
            except Exception:
                logger.exception("Failed to read cached fetch-site data, ignore cache")

        # 1. Загружаем главную страницу (сырой HTML)
        root_html_raw = await self._fetch_single_page(str(params.url))
        root_html = clean_html(root_html_raw)
        root_page = FetchedPage(url=str(params.url), html=root_html, truncated=False)

        # 2. Внутренние ссылки
        #    Здесь предполагается реализация extract_inner_links(...) в BrightDataClient
        #    или другом helper-е. Логику оставляем, как была в твоём коде.
        inner_urls = await self.client.extract_inner_links(
            str(params.url),
            root_html_raw,
            max_links=params.max_pages - 1,
        )

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

        # сохраняем в кэш целиком
        await self.cache.save_site(hash_key, params, data.dict())

        return data

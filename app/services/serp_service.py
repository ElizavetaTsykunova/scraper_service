from typing import List
import urllib.parse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.brightdata_client import BrightDataClient
from app.clients.yandex_client import YandexClient
from app.config import settings
from app.errors import ScraperError
from app.models.serp import (
    SerpQueryRequest,
    SerpData,
    SerpQueryResult,
    SerpPage,
)
from app.repositories.cache_repo import CacheRepo
from app.parsing.google_serp_parser import GoogleSerpParser
from app.parsing.yandex_serp_parser import YandexSerpParser


class SerpService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = CacheRepo(db)
        self.http_client = httpx.AsyncClient()
        self.brightdata = BrightDataClient(self.http_client)
        self.yandex_client = YandexClient()
        self.google_parser = GoogleSerpParser()
        self.yandex_parser = YandexSerpParser()

    async def close(self) -> None:
        await self.http_client.aclose()

    # --------- GOOGLE ---------

    def _build_google_search_url(
        self,
        query: str,
        page: int,
        locale: str | None,
        geo: str | None,
    ) -> str:
        """
        Строим URL для выдачи Google.

        page=1 -> start=0
        page=2 -> start=10
        ...
        locale: ru-RU -> hl=ru
        geo: ru -> gl=ru
        """
        start = (page - 1) * 10
        hl = (locale or "ru-RU").split("-")[0]
        gl = geo or "ru"
        q = urllib.parse.quote_plus(query)
        return f"https://www.google.com/search?q={q}&hl={hl}&gl={gl}&start={start}"

    async def fetch_google_serp(self, req: SerpQueryRequest) -> SerpData:
        params = req.dict()
        hash_key = self.cache.serp_request_hash("google", params)
        cached = await self.cache.get_serp("google", hash_key)
        if cached:
            return SerpData(**cached.response_data)

        queries_results: List[SerpQueryResult] = []
        partial = False

        max_pages = min(req.max_pages_per_query, settings.max_pages_per_query)

        for q in req.queries:
            pages: List[SerpPage] = []
            pages_scanned = 0
            local_error: str | None = None

            for page_num in range(1, max_pages + 1):
                try:
                    url = self._build_google_search_url(
                        query=q,
                        page=page_num,
                        locale=req.locale,
                        geo=req.geo,
                    )
                    html = await self.brightdata.fetch_page_html(url)

                    # ВРЕМЕННЫЙ DEBUG: сохраняем первую страницу первой выборки
                    if page_num == 1 and not queries_results:
                        from pathlib import Path
                        debug_path = Path("/opt/scraper_service/debug_google_page1.html")
                        debug_path.write_text(html, encoding="utf-8")


                    serp_page = self.google_parser.parse(html, page_number=page_num)
                    pages.append(serp_page)
                    pages_scanned += 1
                except ScraperError as e:
                    code = getattr(e, "error_code", None)
                    local_error = getattr(code, "value", code)
                    partial = True
                    break

            queries_results.append(
                SerpQueryResult(
                    query=q,
                    requested_pages=max_pages,
                    pages_scanned=pages_scanned,
                    error_code=local_error,
                    pages=pages,
                )
            )

        data = SerpData(
            engine="google",
            partial=partial,
            queries=queries_results,
        )

        await self.cache.save_serp("google", hash_key, params, data.dict())
        return data

    # --------- YANDEX ---------

    async def fetch_yandex_serp(self, req: SerpQueryRequest) -> SerpData:
        params = req.dict()
        hash_key = self.cache.serp_request_hash("yandex", params)
        cached = await self.cache.get_serp("yandex", hash_key)
        if cached:
            return SerpData(**cached.response_data)

        queries_results: List[SerpQueryResult] = []
        partial = False

        max_pages = min(req.max_pages_per_query, settings.max_pages_per_query)
        region = req.region or "213"

        for q in req.queries:
            pages: List[SerpPage] = []
            pages_scanned = 0
            local_error: str | None = None

            for page_num in range(1, max_pages + 1):
                try:
                    html = await self.yandex_client.fetch_serp_html(
                        query=q,
                        page=page_num,
                        locale=req.locale or "ru-RU",
                        region=region,
                    )
                    serp_page = self.yandex_parser.parse(html, page_number=page_num)
                    pages.append(serp_page)
                    pages_scanned += 1
                except ScraperError as e:
                    code = getattr(e, "error_code", None)
                    local_error = getattr(code, "value", code)
                    partial = True
                    break

            queries_results.append(
                SerpQueryResult(
                    query=q,
                    requested_pages=max_pages,
                    pages_scanned=pages_scanned,
                    error_code=local_error,
                    pages=pages,
                )
            )

        data = SerpData(
            engine="yandex",
            partial=partial,
            queries=queries_results,
        )

        await self.cache.save_serp("yandex", hash_key, params, data.dict())
        return data

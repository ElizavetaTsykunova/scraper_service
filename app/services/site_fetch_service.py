from typing import List
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from bs4 import BeautifulSoup

from app.clients.brightdata_client import BrightDataClient
from app.config import settings
from app.models.fetch_site import FetchSiteRequest, FetchSiteData, FetchedPage
from app.repositories.cache_repo import CacheRepo
from app.parsing.html_utils import clean_html_keep_head_and_body


class SiteFetchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = CacheRepo(db)
        self.http_client = httpx.AsyncClient()
        self.brightdata = BrightDataClient(self.http_client)

    async def close(self) -> None:
        await self.http_client.aclose()

    def _same_domain(self, base_url: str, candidate_url: str) -> bool:
        try:
            base = urlparse(base_url)
            cand = urlparse(candidate_url)
            return base.netloc == cand.netloc
        except Exception:
            return False

    def _extract_internal_links(self, base_url: str, html: str, limit: int) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        base = urlparse(base_url)

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#"):
                continue
            if href.startswith("mailto:") or href.startswith("tel:"):
                continue

            # абсолютные / относительные
            if href.startswith("http://") or href.startswith("https://"):
                full_url = href
            else:
                # относительный
                full_url = f"{base.scheme}://{base.netloc}{href if href.startswith('/') else '/' + href}"

            if not self._same_domain(base_url, full_url):
                continue

            if full_url not in links:
                links.append(full_url)
            if len(links) >= limit:
                break

        return links

    async def fetch_site(self, req: FetchSiteRequest) -> FetchSiteData:
        max_pages = min(req.max_pages, settings.max_site_pages)
        params = req.dict()
        hash_key = self.cache.site_request_hash(params)

        cached = await self.cache.get_site(hash_key)
        if cached:
            return FetchSiteData(**cached.response_data)

        pages: List[FetchedPage] = []
        partial = False

        # главная
        root_html_raw = await self.brightdata.fetch_page_html(str(req.url))
        root_html_clean, root_truncated = clean_html_keep_head_and_body(root_html_raw)
        pages.append(
            FetchedPage(
                url=str(req.url),
                html=root_html_clean,
                truncated=root_truncated,
            )
        )

        # внутренние ссылки
        internal_links = self._extract_internal_links(str(req.url), root_html_raw, limit=max_pages - 1)

        for link in internal_links:
            try:
                raw = await self.brightdata.fetch_page_html(link)
                clean_html, truncated = clean_html_keep_head_and_body(raw)
                pages.append(
                    FetchedPage(
                        url=link,
                        html=clean_html,
                        truncated=truncated,
                    )
                )
            except Exception:
                partial = True
                # просто пропускаем эту страницу, продолжаем дальше

        data = FetchSiteData(
            pages=pages,
            partial=partial,
        )

        await self.cache.save_site(hash_key, params, data.dict())

        return data

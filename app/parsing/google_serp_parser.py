from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import logging

from app.config import settings
from app.models.serp import (
    SerpPage,
    SerpResultBase,
    SerpAdResult,
)

logger = logging.getLogger(__name__)

class GoogleSerpParser:
    """
    Парсер HTML выдачи Google в структурированный SerpPage.

    Это "разумный" парсер по основным CSS-классам.
    Он не претендует на 100% стабильность (Google часто меняет верстку),
    но покрывает типичные кейсы:
    - блоки .g с результатами,
    - заголовки в h3,
    - сниппеты в .VwiC3b / .aCOpRe,
    - рекламные блоки по ряду характерных селекторов.
    """

    def __init__(self) -> None:
        self.max_title = settings.max_title_chars
        self.max_snippet = settings.max_snippet_chars

    @staticmethod
    def _normalize_url(raw_url: str) -> str:
        # Google часто отдаёт /url?q=...&sa=... — можно попытаться декодировать,
        # но на первых порах отдадим как есть, если это уже нормальный https://...
        return raw_url

    @staticmethod
    def _extract_domain(url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc or ""
        if host.startswith("www."):
            host = host[4:]
        return host

    def _truncate(self, text: str, limit: int) -> tuple[str, bool]:
        if text is None:
            return "", False
        if len(text) <= limit:
            return text, False
        return text[:limit], True

    def _parse_organic(self, soup: BeautifulSoup) -> List[SerpResultBase]:
        results: List[SerpResultBase] = []
        position = 1

        # Пробуем несколько вариантов контейнеров
        blocks_g = soup.select("div.g")
        blocks_mjj = soup.select("div.MjjYud")  # частый контейнер результата сейчас
        blocks_njo = soup.select("div.NJo7tc.Z26q7c.uUuwM")  # другой вариант контейнера

        # если классический div.g пустой — используем альтернативы
        blocks = blocks_g or blocks_mjj or blocks_njo

        logger.info(
            "google_serp_parser organic blocks",
            extra={
                "organic_blocks_g": len(blocks_g),
                "organic_blocks_MjjYud": len(blocks_mjj),
                "organic_blocks_NJo7tc": len(blocks_njo),
            },
        )

        for block in blocks:
            # как и было
            link = block.select_one("div.yuRUbf a[href]") or block.select_one("a[href]")
            if not link:
                continue

            url = link.get("href", "").strip()
            if not url:
                continue

            url = self._normalize_url(url)
            domain = self._extract_domain(url)

            title_tag = link.select_one("h3") or block.select_one("h3")
            title = title_tag.get_text(" ", strip=True) if title_tag else url

            snippet_tag = block.select_one(".VwiC3b") or block.select_one(".aCOpRe")
            snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else None

            title, title_trunc = self._truncate(title, self.max_title)
            if snippet is not None:
                snippet, snippet_trunc = self._truncate(snippet, self.max_snippet)
            else:
                snippet_trunc = False

            results.append(
                SerpResultBase(
                    position=position,
                    url=url,
                    domain=domain,
                    title=title,
                    snippet=snippet,
                    truncated=title_trunc or snippet_trunc,
                )
            )
            position += 1

        return results

    def _parse_ads(self, soup: BeautifulSoup) -> List[SerpAdResult]:
        ads: List[SerpAdResult] = []
        position = 1

        # Рекламные блоки Google довольно плавающие,
        # типичные современные варианты:
        # - div.uEierd (ад-блок)
        # - div[data-text-ad]
        ad_blocks = soup.select("div.uEierd") or soup.select("div[data-text-ad]")

        for block in ad_blocks:
            link = block.select_one("a[href]")
            if not link:
                continue

            url = link.get("href", "").strip()
            if not url:
                continue

            url = self._normalize_url(url)
            domain = self._extract_domain(url)

            title_tag = block.select_one("span[role='heading']") or block.select_one("a h3") or block.select_one("h3")
            title = title_tag.get_text(" ", strip=True) if title_tag else url
            title, title_trunc = self._truncate(title, self.max_title)

            # Для MVP не делим рекламу по блокам top/bottom/side — ставим "top"
            ads.append(
                SerpAdResult(
                    position=position,
                    block="top",
                    url=url,
                    domain=domain,
                    title=title,
                    truncated=title_trunc,
                )
            )
            position += 1

        return ads

    def parse(self, html: str, page_number: int) -> SerpPage:
        soup = BeautifulSoup(html, "lxml")

        organic = self._parse_organic(soup)
        ads = self._parse_ads(soup)

        return SerpPage(
            page=page_number,
            organic_results=organic,
            ads=ads,
        )

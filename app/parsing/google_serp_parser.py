from typing import List
from bs4 import BeautifulSoup

from app.config import settings
from app.models.serp import SerpPage, SerpResultBase, SerpAdResult


class GoogleSerpParser:
    """
    ВНИМАНИЕ: селекторы нужно будет подогнать под фактический HTML от Bright Data.
    Здесь skeleton: разделение органики и ads, обрезка title/snippet.
    """

    def parse(self, html: str, page_number: int) -> SerpPage:
        soup = BeautifulSoup(html, "lxml")

        organic_results = self._parse_organic(soup)
        ads = self._parse_ads(soup)

        # расставляем позиции
        for i, r in enumerate(organic_results, start=1):
            r.position = i
        for i, ad in enumerate(ads, start=1):
            ad.position = i

        return SerpPage(
            page=page_number,
            organic_results=organic_results,
            ads=ads,
        )

    def _truncate(self, text: str, max_len: int) -> tuple[str, bool]:
        if len(text) > max_len:
            return text[:max_len], True
        return text, False

    def _parse_organic(self, soup) -> List[SerpResultBase]:
        results: List[SerpResultBase] = []

        # TODO: заменить селектор на реальный (примерно: div[role="heading"] и т.д.)
        for block in soup.select("div.g"):
            a = block.select_one("a")
            if not a or not a.get("href"):
                continue

            title_el = block.select_one("h3")
            snippet_el = block.select_one("span, div[role='text']")

            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            title, title_tr = self._truncate(title, settings.max_title_chars)
            snippet, sn_tr = self._truncate(snippet, settings.max_snippet_chars)

            truncated = title_tr or sn_tr

            url = a.get("href")
            domain = url.split("/")[2] if "://" in url else url

            results.append(
                SerpResultBase(
                    position=0,
                    url=url,
                    domain=domain,
                    title=title,
                    snippet=snippet,
                    truncated=truncated,
                )
            )
        return results

    def _parse_ads(self, soup) -> List[SerpAdResult]:
        ads: List[SerpAdResult] = []

        # TODO: заменить на реальные селекторы рекламных блоков
        for ad_block in soup.select("div[data-text-ad]"):
            a = ad_block.select_one("a")
            if not a or not a.get("href"):
                continue

            title_el = ad_block.select_one("h3") or ad_block.select_one("div")
            title = title_el.get_text(strip=True) if title_el else ""
            title, title_tr = self._truncate(title, settings.max_title_chars)

            url = a.get("href")
            domain = url.split("/")[2] if "://" in url else url

            # Пока определяем блок грубо как "top" — потом можно улучшить по позиции в DOM
            ads.append(
                SerpAdResult(
                    position=0,
                    block="top",
                    url=url,
                    domain=domain,
                    title=title,
                    truncated=title_tr,
                )
            )

        return ads

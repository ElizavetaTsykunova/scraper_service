from typing import List
from bs4 import BeautifulSoup

from app.config import settings
from app.models.serp import SerpPage, SerpResultBase, SerpAdResult


class YandexSerpParser:
    """
    Аналогично: селекторы нужно подогнать под реальную верстку Яндекса.
    """

    def parse(self, html: str, page_number: int) -> SerpPage:
        soup = BeautifulSoup(html, "lxml")

        organic_results = self._parse_organic(soup)
        ads = self._parse_ads(soup)

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

        # TODO: реальный селектор органики Яндекса
        for block in soup.select("li.serp-item"):
            link = block.select_one("a.Link")
            if not link or not link.get("href"):
                continue

            title_el = block.select_one("h2")
            snippet_el = block.select_one(".text-container")

            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            title, title_tr = self._truncate(title, settings.max_title_chars)
            snippet, sn_tr = self._truncate(snippet, settings.max_snippet_chars)

            truncated = title_tr or sn_tr

            url = link.get("href")
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

        # TODO: селекторы рекламных блоков Яндекса
        for ad_block in soup.select(".organic .advertising"):

            link = ad_block.select_one("a")
            if not link or not link.get("href"):
                continue

            title_el = ad_block.select_one(".organic__url-text") or ad_block.select_one("a")
            title = title_el.get_text(strip=True) if title_el else ""
            title, title_tr = self._truncate(title, settings.max_title_chars)

            url = link.get("href")
            domain = url.split("/")[2] if "://" in url else url

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

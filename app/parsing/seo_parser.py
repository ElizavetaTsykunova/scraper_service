# app/parsing/seo_parser.py

from __future__ import annotations

from bs4 import BeautifulSoup
from typing import Dict, List, Optional


def _get_text(tag) -> Optional[str]:
    if not tag:
        return None
    text = tag.get_text(strip=True)
    return text or None


def extract_meta(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    meta: Dict[str, Optional[str]] = {}

    title_tag = soup.find("title")
    meta["title"] = _get_text(title_tag)

    desc = soup.find("meta", attrs={"name": "description"})
    meta["description"] = desc.get("content").strip() if desc and desc.get("content") else None

    kws = soup.find("meta", attrs={"name": "keywords"})
    meta["keywords"] = kws.get("content").strip() if kws and kws.get("content") else None

    canonical = soup.find("link", rel="canonical")
    meta["canonical"] = canonical.get("href").strip() if canonical and canonical.get("href") else None

    # hreflang
    hreflangs = []
    for link in soup.find_all("link", rel="alternate"):
        hreflang = link.get("hreflang")
        href = link.get("href")
        if hreflang and href:
            hreflangs.append({"hreflang": hreflang, "href": href})
    meta["hreflang"] = hreflangs or None

    return meta


def extract_open_graph(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    og: Dict[str, Optional[str]] = {}
    for prop in ["og:title", "og:description", "og:image", "og:type", "og:url", "og:site_name"]:
        tag = soup.find("meta", property=prop)
        og[prop] = tag.get("content").strip() if tag and tag.get("content") else None
    return og


def extract_headings(soup: BeautifulSoup) -> Dict[str, List[str]]:
    headings: Dict[str, List[str]] = {}
    for level in range(1, 7):
        tag_name = f"h{level}"
        items: List[str] = []
        for h in soup.find_all(tag_name):
            text = _get_text(h)
            if text:
                items.append(text)
        headings[tag_name] = items
    return headings


def extract_json_ld(soup: BeautifulSoup) -> List[str]:
    data: List[str] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        if tag.string:
            data.append(tag.string.strip())
    return data


def parse_seo(html: str) -> Dict:
    """
    Главная функция: получает HTML → возвращает SEO-структуру.
    """
    soup = BeautifulSoup(html, "lxml")
    return {
        "meta": extract_meta(soup),
        "open_graph": extract_open_graph(soup),
        "headings": extract_headings(soup),
        "json_ld": extract_json_ld(soup),
    }

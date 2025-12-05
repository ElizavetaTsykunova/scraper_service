# app/parsing/seo_parser.py

from __future__ import annotations

from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from app.parsing.html_cleaner import build_clean_soup


def _get_text(tag) -> Optional[str]:
    if not tag:
        return None
    text = tag.get_text(strip=True)
    return text or None


def extract_meta(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    meta: Dict[str, Optional[str]] = {}

    # title
    title_tag = soup.find("title")
    meta["title"] = _get_text(title_tag)

    # description
    desc = soup.find("meta", attrs={"name": "description"})
    meta["description"] = desc.get("content").strip() if desc and desc.get("content") else None

    # keywords
    kws = soup.find("meta", attrs={"name": "keywords"})
    meta["keywords"] = kws.get("content").strip() if kws and kws.get("content") else None

    # canonical
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

    # robots
    robots = soup.find("meta", attrs={"name": "robots"})
    meta["robots"] = robots.get("content").strip() if robots and robots.get("content") else None

    # viewport
    viewport = soup.find("meta", attrs={"name": "viewport"})
    meta["viewport"] = viewport.get("content").strip() if viewport and viewport.get("content") else None

    # charset
    charset_value: Optional[str] = None
    charset_tag = soup.find("meta", attrs={"charset": True})
    if charset_tag and charset_tag.get("charset"):
        charset_value = charset_tag.get("charset").strip()
    else:
        # резервный вариант: Content-Type
        ct = soup.find("meta", attrs={"http-equiv": "Content-Type"})
        if ct and ct.get("content"):
            charset_value = ct.get("content").strip()
    meta["charset"] = charset_value

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
        # после html_cleaner JSON-LD скрипты сохраняются
        if tag.string:
            data.append(tag.string.strip())
    return data


def extract_lang(soup: BeautifulSoup) -> Optional[str]:
    """
    Определяем язык документа по атрибуту <html lang="...">.
    Это не бизнес-логика, а просто снятие флага из DOM.
    """
    html_tag = soup.find("html")
    if not html_tag:
        return None

    lang = html_tag.get("lang") or html_tag.get("xml:lang")
    if not lang:
        return None

    lang = lang.strip()
    return lang or None


def parse_seo(html: str) -> Dict:
    """
    Главная функция: получает ОЧИЩЕННЫЙ HTML → возвращает SEO-структуру.

    Вход: HTML, прошедший через html_cleaner.clean_html_minimal / build_clean_soup.
    Никакой бизнес-логики: только снятие SEO-сигналов.
    """
    # Используем единый канонический DOM-слой
    soup = build_clean_soup(html)

    return {
        "meta": extract_meta(soup),
        "open_graph": extract_open_graph(soup),
        "headings": extract_headings(soup),
        "json_ld": extract_json_ld(soup),
        "lang": extract_lang(soup),
    }

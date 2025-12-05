# app/parsing/html_cleaner.py

from __future__ import annotations

from bs4 import BeautifulSoup
from typing import Iterable


# Теги, которые полностью вырезаем
STRIP_TAGS: tuple[str, ...] = (
    "script",
    "style",
    "noscript",
    "iframe",
    "canvas",
    "svg",
    "object",
    "embed",
    "picture",
    "source",
)

# Атрибуты, которые удаляем
STRIP_ATTRS: tuple[str, ...] = (
    "style",
    "onclick",
    "onmouseover",
    "onmouseout",
    "onload",
    "onerror",
)


def _drop_hidden(soup: BeautifulSoup) -> None:
    """Убираем заведомо скрытые элементы: display:none, hidden и т.п."""

    # по атрибуту hidden
    for el in soup.select("[hidden]"):
        el.decompose()

    # по inline-style
    for el in soup.select("[style]"):
        style = el.get("style", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            el.decompose()


def _strip_attrs(soup: BeautifulSoup, attrs: Iterable[str]) -> None:
    for el in soup.find_all(True):
        for attr in attrs:
            if attr in el.attrs:
                del el[attr]


def _strip_tags(soup: BeautifulSoup, tags: Iterable[str]) -> None:
    for tag in tags:
        for el in soup.find_all(tag):
            el.decompose()


def clean_html(html: str) -> str:
    """
    Более «строгая» очистка:
    - убираем script/style/iframe/svg и т.п.;
    - убираем скрытые элементы;
    - убираем стили и on*-атрибуты.
    Используем для /api/v1/fetch-site и внутренних анализов.
    """
    soup = BeautifulSoup(html, "lxml")

    _strip_tags(soup, STRIP_TAGS)
    _drop_hidden(soup)
    _strip_attrs(soup, STRIP_ATTRS)

    return str(soup)


def clean_html_minimal(html: str) -> str:
    """
    Минимальная очистка:
    - только убираем script/style/iframe/svg и т.п.;
    - остальное оставляем, чтобы структура была максимально сохранена.
    Используем для HTML-эндпоинта.
    """
    soup = BeautifulSoup(html, "lxml")

    _strip_tags(soup, STRIP_TAGS)

    return str(soup)

# app/parsing/html_cleaner.py

from __future__ import annotations

from typing import Iterable, Set

from bs4 import BeautifulSoup, Comment


# Теги, которые полностью вырезаем из HTML
STRIP_TAGS: tuple[str, ...] = (
    "script",
    "style",
    "noscript",
    "iframe",
    "canvas",
    "svg",
    "object",
    "embed",
)

# Разрешённые атрибуты (всё остальное вычищаем)
ALLOWED_ATTRS: Set[str] = {
    "id",
    "class",
    "href",
    "src",
    "alt",
    "title",
    "rel",
    "name",
    "content",
    "type",
    "aria-label",
}


def _strip_tags(soup: BeautifulSoup, tags: Iterable[str]) -> None:
    """
    Полностью вырезаем указанные теги (script/style/iframe/... и т.п.).

    ВАЖНО: script[type="application/ld+json"] не удаляем,
    чтобы SEO-парсер мог читать JSON-LD разметку.
    """
    for tag in tags:
        if tag == "script":
            # Удаляем все <script>, КРОМЕ JSON-LD
            for el in soup.find_all("script"):
                script_type = (el.get("type") or "").lower()
                if script_type == "application/ld+json":
                    continue
                el.decompose()
        else:
            for el in soup.find_all(tag):
                el.decompose()


def _clean_attributes(soup: BeautifulSoup) -> None:
    """
    Очищаем атрибуты:
    - убираем все on* (onclick, onload и т.п.);
    - оставляем только ALLOWED_ATTRS и data-*;
    - всё остальное (style, bgcolor, width/height и т.п.) выкидываем.
    """
    for tag in soup.find_all(True):
        attrs = dict(tag.attrs)
        new_attrs = {}

        for attr_name, value in attrs.items():
            attr_lower = attr_name.lower()

            # любые on* (onclick, onmouseover и т.п.) выкидываем
            if attr_lower.startswith("on"):
                continue

            # белый список атрибутов
            if attr_name in ALLOWED_ATTRS:
                new_attrs[attr_name] = value
                continue

            # data-* оставляем на всякий случай (может пригодиться в анализе)
            if attr_lower.startswith("data-"):
                new_attrs[attr_name] = value
                continue

            # всё остальное (style, width/height и т.п.) — выкидываем
            continue

        tag.attrs = new_attrs


def _strip_comments(soup: BeautifulSoup) -> None:
    """Удаляем HTML-комментарии, чтобы не плодить мусор в анализе."""
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


def build_clean_soup(raw_html: str) -> BeautifulSoup:
    """
    ЕДИНСТВЕННАЯ точка «канонической» очистки HTML.

    Сырой HTML от Bright Data → нормализованный BeautifulSoup:
    - парсим через lxml;
    - вырезаем технические теги (script/style/iframe/svg/...),
      но сохраняем script[type="application/ld+json"];
    - чистим атрибуты (style, on* и т.п.);
    - удаляем комментарии;
    - сохраняем всю структурную и контентную разметку
      (head/meta/title/nav/header/footer/section/div/a/img/button/...).
    """
    soup = BeautifulSoup(raw_html, "lxml")

    # 1. вырезаем технические теги
    _strip_tags(soup, STRIP_TAGS)

    # 2. чистим атрибуты
    _clean_attributes(soup)

    # 3. убираем комментарии
    _strip_comments(soup)

    return soup


def clean_html(html: str) -> str:
    """
    Историческая функция для строгой очистки.
    Теперь: просто обёртка над build_clean_soup.
    Используется там, где раньше ожидался «очищенный HTML для анализа».
    """
    soup = build_clean_soup(html)
    return str(soup)


def clean_html_minimal(html: str) -> str:
    """
    Минимальная очистка для /site/html.

    Сейчас поведение такое же, как у clean_html:
    - один проход build_clean_soup;
    - никаких дополнительных «строгих» чисток;
    - один и тот же канонический HTML идёт и в /site/html, и в /site/seo, и в /site/content.
    """
    soup = build_clean_soup(html)
    return str(soup)

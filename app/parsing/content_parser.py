# app/parsing/content_parser.py

from __future__ import annotations

from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import re


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_cta(soup: BeautifulSoup) -> List[Dict]:
    """
    Ищем CTA-кнопки: <a> и <button> с текстом типа
    'Оставить заявку', 'Заказать', 'Купить' и т.п.
    """
    cta_keywords = [
        "заказать",
        "купить",
        "оформить заказ",
        "оставить заявку",
        "связаться",
        "записаться",
        "оставить контакт",
        "получить консультацию",
    ]

    results: List[Dict] = []

    for tag in soup.find_all(["a", "button"]):
        text = _clean_text(tag.get_text())
        if not text:
            continue

        lower = text.lower()
        if any(word in lower for word in cta_keywords):
            results.append(
                {
                    "text": text,
                    "tag": tag.name,
                    "href": tag.get("href"),
                    "classes": tag.get("class") or [],
                }
            )

    return results


def extract_main_sections(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """
    Выделяем ключевые блоки: header, nav, main, footer (по тегам и по ролям/классам).
    Текст внутри — сильно ужимаем.
    """

    def grab(selector: str) -> Optional[str]:
        el = soup.select_one(selector)
        if not el:
            return None
        text = _clean_text(el.get_text())
        return text or None

    sections = {
        "header": grab("header, [role=banner]"),
        "navigation": grab("nav, [role=navigation]"),
        "main": grab("main, [role=main]"),
        "footer": grab("footer, [role=contentinfo]"),
    }

    return sections


def extract_content_blocks(soup: BeautifulSoup) -> List[Dict]:
    """
    Грубое разбиение на блоки по крупным контейнерам: section, article, div.t-block и т.п.
    Для каждого блока сохраняем:
    - тип;
    - первые 200 символов текста.
    """

    blocks: List[Dict] = []

    candidates = soup.find_all(["section", "article", "div"])
    for el in candidates:
        classes = " ".join(el.get("class", []))
        # слегка фильтруем заведомый мусор
        if "cookie" in classes.lower():
            continue

        text = _clean_text(el.get_text())
        if not text:
            continue

        blocks.append(
            {
                "tag": el.name,
                "classes": el.get("class") or [],
                "text_preview": text[:200],
            }
        )

        if len(blocks) >= 100:
            break

    return blocks


def parse_content(html: str) -> Dict:
    """
    Главная функция контент-анализа.
    На вход — уже очищенный HTML (clean_html_minimal или clean_html).
    """
    soup = BeautifulSoup(html, "lxml")
    return {
        "cta_buttons": extract_cta(soup),
        "key_sections": extract_main_sections(soup),
        "content_blocks": extract_content_blocks(soup),
    }

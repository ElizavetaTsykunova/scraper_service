# app/parsing/content_parser.py

from __future__ import annotations

from typing import Dict, List, Optional
import re

from bs4 import BeautifulSoup

from app.parsing.html_cleaner import build_clean_soup


def _clean_text(text: str) -> str:
    """
    Унифицированная чистка текста:
    - схлопываем подряд идущие пробелы/переносы;
    - обрезаем по краям.
    """
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_cta(soup: BeautifulSoup) -> List[Dict]:
    """
    Ищем CTA-кнопки: <a> и <button> с текстом типа
    'Оставить заявку', 'Заказать', 'Купить' и т.п.

    ВАЖНО: здесь только фиксация сырья (текст, href, tag, classes),
    никакой оценки качества/количества CTA.
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
    Текст внутри — ужимаем до компактного вида (без разметки).
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


def _get_first_heading(el) -> Optional[str]:
    """
    Ищем первый заголовок h1–h3 внутри блока.
    Это не бизнес-логика, а просто фиксация структуры:
    что этот блок "подписан" таким-то заголовком.
    """
    for level in range(1, 4):
        tag_name = f"h{level}"
        h = el.find(tag_name)
        if h:
            text = _clean_text(h.get_text())
            if text:
                return text
    return None


def _build_dom_path(el) -> str:
    """
    Строим простой путь в DOM: body>main>section>div.
    Без индексов, чтобы не раздувать размер.
    """
    parts: List[str] = []
    current = el
    while current and current.name not in (None, "[document]"):
        parts.append(current.name)
        if current.name == "body":
            break
        current = current.parent
    parts.reverse()
    # гарантируем, что путь начинается с body, если он был найден
    return ">".join(parts)


def extract_content_blocks(soup: BeautifulSoup) -> List[Dict]:
    """
    Разбиение на содержательные блоки по крупным контейнерам:
    section, article, div.

    Для каждого блока сохраняем:
    - tag           — тип контейнера;
    - classes       — CSS-классы;
    - text_preview  — первые 200 символов текста;
    - heading       — первый h1–h3 внутри блока (если есть);
    - image_count   — сколько <img> внутри;
    - link_count    — сколько <a> внутри;
    - button_count  — сколько <button> внутри;
    - dom_path      — упрощённый путь в DOM (body>main>section>div).

    Никакой классификации "это УТП/клиенты/кейсы" здесь нет —
    только структурированное сырьё для дальнейшего анализа в SCG.
    """

    blocks: List[Dict] = []

    candidates = soup.find_all(["section", "article", "div"])
    for el in candidates:
        classes_list = el.get("class", [])
        classes_str = " ".join(classes_list).lower()

        # слегка фильтруем заведомый мусор (cookie-баннеры и т.п.)
        if "cookie" in classes_str:
            continue

        text = _clean_text(el.get_text())
        if not text:
            # блок без текста (но, возможно, только из картинок) для текстового анализа не интересен
            # логика по чисто графическим блокам (галереи) может быть добавлена в будущем отдельно
            continue

        heading = _get_first_heading(el)
        image_count = len(el.find_all("img"))
        link_count = len(el.find_all("a"))
        button_count = len(el.find_all("button"))
        dom_path = _build_dom_path(el)

        blocks.append(
            {
                "tag": el.name,
                "classes": classes_list,
                "text_preview": text[:200],
                "heading": heading,
                "image_count": image_count,
                "link_count": link_count,
                "button_count": button_count,
                "dom_path": dom_path,
            }
        )

        # жёсткий лимит, чтобы не раздувать ответ для очень длинных страниц
        if len(blocks) >= 100:
            break

    return blocks


def parse_content(html: str) -> Dict:
    """
    Главная функция контент-парсинга.

    Вход: HTML, прошедший через html_cleaner (clean_html_minimal / clean_html).
    Задача: вернуть структурированное сырьё для контент-анализа,
    без бизнес-логики (никаких решений "это УТП/клиенты/кейсы").
    """
    # Используем единый канонический DOM-слой.
    # Если html уже очищен — build_clean_soup отработает идемпотентно.
    soup = build_clean_soup(html)

    return {
        "cta_buttons": extract_cta(soup),
        "key_sections": extract_main_sections(soup),
        "content_blocks": extract_content_blocks(soup),
    }

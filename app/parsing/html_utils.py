from typing import Tuple
from bs4 import BeautifulSoup
from app.config import settings


def clean_html_keep_head_and_body(html: str, max_chars: int | None = None) -> Tuple[str, bool]:
    """
    Убираем <script>, <style>, комментарии.
    Оставляем head и body, body обрезаем по max_chars.
    """
    if max_chars is None:
        max_chars = settings.max_html_chars_per_page

    soup = BeautifulSoup(html, "lxml")

    # remove scripts and styles
    for tag in soup(["script", "style"]):
        tag.decompose()

    # remove comments
    for comment in soup.find_all(string=lambda t: isinstance(t, type(soup.comment))):
        comment.extract()

    html_tag = soup.html
    if not html_tag:
        # fallback — просто обрезаем по длине
        truncated = False
        if len(html) > max_chars:
            html = html[:max_chars]
            truncated = True
        return html, truncated

    head = html_tag.head
    body = html_tag.body

    truncated = False
    body_str = ""
    if body:
        body_str = str(body)
        max_body_chars = max_chars
        if len(body_str) > max_body_chars:
            body_str = body_str[:max_body_chars]
            truncated = True
    head_str = str(head) if head else ""

    final_html = f"<!doctype html><html>{head_str}{body_str}</html>"
    return final_html, truncated

from app.models.serp import SerpPage


class GoogleSerpParser:
    """
    Временный безопасный парсер.
    Просто возвращает пустые результаты, чтобы проверить,
    что Bright Data и общий пайплайн работают.
    """

    def parse(self, html: str, page_number: int) -> SerpPage:
        # На будущее сюда добавим реальный разбор HTML выдачи Google.
        return SerpPage(
            page=page_number,
            organic_results=[],
            ads=[],
        )

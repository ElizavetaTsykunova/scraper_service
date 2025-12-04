from typing import List, Optional
from pydantic import BaseModel, Field, conint, validator


class SerpQueryRequest(BaseModel):
    queries: List[str] = Field(..., min_items=1, max_items=5)
    max_pages_per_query: conint(ge=1, le=5) = 3
    results_per_page: conint(ge=1, le=50) = 10
    locale: Optional[str] = "ru-RU"
    geo: Optional[str] = "ru"  # для Google
    region: Optional[str] = None  # для Yandex

    @validator("queries")
    def strip_queries(cls, v):
        cleaned = [q.strip() for q in v if q.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty query is required")
        return cleaned


class SerpResultBase(BaseModel):
    position: int
    url: str
    domain: str
    title: str
    snippet: Optional[str] = None
    truncated: Optional[bool] = False


class SerpAdResult(BaseModel):
    position: int
    block: str  # top|bottom|side|other
    url: str
    domain: str
    title: str
    truncated: Optional[bool] = False


class SerpPage(BaseModel):
    page: int
    organic_results: List[SerpResultBase]
    ads: List[SerpAdResult]


class SerpQueryResult(BaseModel):
    query: str
    requested_pages: int
    pages_scanned: int
    error_code: Optional[str] = None
    pages: List[SerpPage]


class SerpData(BaseModel):
    engine: str  # "google" | "yandex"
    partial: bool = False
    queries: List[SerpQueryResult]

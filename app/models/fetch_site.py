from typing import List
from pydantic import BaseModel, HttpUrl, conint


class FetchSiteRequest(BaseModel):
    url: HttpUrl
    max_pages: conint(ge=1, le=10) = 4


class FetchedPage(BaseModel):
    url: str
    html: str
    truncated: bool = False


class FetchSiteData(BaseModel):
    pages: List[FetchedPage]
    partial: bool = False

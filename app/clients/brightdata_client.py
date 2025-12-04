from typing import Any, Dict
import httpx

from app.config import settings
from app.errors import (
    BrightDataSourceUnavailable,
    BrightDataTimeoutError,
    BrightDataInternalError,
)


class BrightDataClient:
    def __init__(self, http_client: httpx.AsyncClient):
        self._client = http_client
        self._serp_endpoint = settings.brightdata_serp_endpoint_url
        self._site_endpoint = settings.brightdata_site_endpoint_url
        self._api_key = settings.brightdata_api_key
        self._timeout = settings.brightdata_timeout_sec

    async def fetch_google_serp(
        self,
        query: str,
        page: int,
        locale: str,
        geo: str,
        results_per_page: int,
    ) -> Dict[str, Any]:
        # TODO: подстроить под конкретный формат Bright Data SERP API
        payload = {
            "query": query,
            "page": page,
            "locale": locale,
            "geo": geo,
            "results_per_page": results_per_page,
        }
        try:
            resp = await self._client.post(
                self._serp_endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
        except httpx.TimeoutException as e:
            raise BrightDataTimeoutError from e
        except httpx.HTTPError as e:
            raise BrightDataSourceUnavailable from e

        if 500 <= resp.status_code < 600:
            raise BrightDataSourceUnavailable(f"Bright Data 5xx: {resp.status_code}")
        if resp.status_code >= 400:
            raise BrightDataInternalError(f"Bright Data 4xx: {resp.text}")

        try:
            data = resp.json()
        except ValueError as e:
            raise BrightDataInternalError("Invalid JSON from Bright Data") from e

        return data

    async def fetch_page_html(self, url: str) -> str:
        # TODO: подстроить под конкретный формат Crawl / Browser API
        payload = {
            "url": url,
            "render_js": True,
        }
        try:
            resp = await self._client.post(
                self._site_endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
        except httpx.TimeoutException as e:
            raise BrightDataTimeoutError from e
        except httpx.HTTPError as e:
            raise BrightDataSourceUnavailable from e

        if 500 <= resp.status_code < 600:
            raise BrightDataSourceUnavailable(f"Bright Data 5xx: {resp.status_code}")
        if resp.status_code >= 400:
            raise BrightDataInternalError(f"Bright Data 4xx: {resp.text}")

        try:
            data = resp.json()
        except ValueError as e:
            raise BrightDataInternalError("Invalid JSON from Bright Data") from e

        # предполагаем, что вернётся поле "html"
        html = data.get("html")
        if not isinstance(html, str):
            raise BrightDataInternalError("Missing 'html' in Bright Data response")
        return html

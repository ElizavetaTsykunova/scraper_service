from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    scraper_api_token: str
    scraper_api_host: str = "0.0.0.0"
    scraper_api_port: int = 8080
    scraper_version: str = "0.1.0"

    database_url: AnyUrl

    request_timeout_sec: int = 60

    cache_ttl_sec: int = 86400  # 24h
    max_queries: int = 5
    max_pages_per_query: int = 5
    max_site_pages: int = 4
    max_html_chars_per_page: int = 800_000
    max_title_chars: int = 512
    max_snippet_chars: int = 1024

    # Bright Data
    brightdata_api_key: str
    brightdata_serp_endpoint_url: str
    brightdata_site_endpoint_url: str
    brightdata_timeout_sec: int = 15
    brightdata_max_concurrency: int = 5

    # Yandex / Proxy
    yandex_proxy_host: str
    yandex_proxy_port: int
    yandex_proxy_login: str
    yandex_proxy_password: str
    yandex_request_timeout_sec: int = 15000
    yandex_max_concurrency: int = 3


settings = Settings()

import logging
from typing import Any, Optional

from fastapi import FastAPI, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db, engine, Base
from app.errors import ScraperError, ErrorCode
from app.logging_config import setup_logging
from app.models.common import BaseResponse
from app.models.serp import SerpQueryRequest, SerpData
from app.models.fetch_site import FetchSiteRequest, FetchSiteData
from app.services.serp_service import SerpService
from app.services.site_fetch_service import SiteFetchService
from app.parsing.seo_parser import parse_seo
from app.parsing.content_parser import parse_content

logger = logging.getLogger(__name__)

setup_logging()
app = FastAPI(title="scraper-service", version=settings.scraper_version)


# ------------- AUTH -------------


async def auth_dependency(authorization: str = Header(...)) -> None:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )
    token = authorization.split(" ", 1)[1]
    if token != settings.scraper_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )


# ------------- EVENTS -------------


@app.on_event("startup")
async def on_startup() -> None:
    # Создаём таблицы, если их ещё нет
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ------------- HEALTH -------------


@app.get("/health", response_model=dict)
async def health() -> dict:
    return {"status": "ok", "version": settings.scraper_version}


# ------------- SERP: GOOGLE -------------


@app.post(
    "/api/v1/serp/google",
    response_model=BaseResponse,
    dependencies=[Depends(auth_dependency)],
)
async def google_serp(
    req: SerpQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SerpService(db)
    try:
        data: SerpData = await service.fetch_google(req)
        return BaseResponse(status="success", error_code=None, data=data.dict())
    except ScraperError as e:
        logger.exception("Google SERP error")
        code = getattr(e, "error_code", ErrorCode.internal_error)
        return BaseResponse(status="failed", error_code=code, data=None)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected Google SERP error")
        return BaseResponse(status="failed", error_code=ErrorCode.internal_error, data=None)


# ------------- SERP: YANDEX (MVP-заготовка) -------------


@app.post(
    "/api/v1/serp/yandex",
    response_model=BaseResponse,
    dependencies=[Depends(auth_dependency)],
)
async def yandex_serp(
    req: SerpQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SerpService(db)
    try:
        data: SerpData = await service.fetch_yandex(req)
        return BaseResponse(status="success", error_code=None, data=data.dict())
    except ScraperError as e:
        logger.exception("Yandex SERP error")
        code = getattr(e, "error_code", ErrorCode.internal_error)
        return BaseResponse(status="failed", error_code=code, data=None)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected Yandex SERP error")
        return BaseResponse(status="failed", error_code=ErrorCode.internal_error, data=None)


# ------------- СТАРЫЙ /api/v1/fetch-site (MVP из ТЗ) -------------


@app.post(
    "/api/v1/fetch-site",
    response_model=BaseResponse,
    dependencies=[Depends(auth_dependency)],
)
async def fetch_site(
    req: FetchSiteRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SiteFetchService(db)
    try:
        data: FetchSiteData = await service.fetch_site(req)
        return BaseResponse(status="success", error_code=None, data=data.dict())
    except ScraperError as e:
        logger.exception("Fetch site error")
        code = getattr(e, "error_code", ErrorCode.internal_error)
        return BaseResponse(status="failed", error_code=code, data=None)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected fetch site error")
        return BaseResponse(status="failed", error_code=ErrorCode.internal_error, data=None)
    finally:
        await service.close()


# ------------- НОВЫЕ ЭНДПОИНТЫ: HTML / SEO / CONTENT -------------


@app.post(
    "/api/v1/site/html",
    response_model=BaseResponse,
    dependencies=[Depends(auth_dependency)],
)
async def fetch_site_html(
    req: FetchSiteRequest,  # используем только url, max_pages игнорируем
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SiteFetchService(db)
    try:
        html = await service.fetch_html_cleaned(str(req.url))
        data: dict[str, Any] = {"url": str(req.url), "html": html}
        return BaseResponse(status="success", error_code=None, data=data)
    except ScraperError as e:
        logger.exception("Fetch site HTML error")
        code = getattr(e, "error_code", ErrorCode.internal_error)
        return BaseResponse(status="failed", error_code=code, data=None)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected fetch site HTML error")
        return BaseResponse(status="failed", error_code=ErrorCode.internal_error, data=None)
    finally:
        await service.close()


@app.post(
    "/api/v1/site/seo",
    response_model=BaseResponse,
    dependencies=[Depends(auth_dependency)],
)
async def fetch_site_seo(
    req: FetchSiteRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SiteFetchService(db)
    try:
        html = await service.fetch_html_cleaned(str(req.url))
        seo_data = parse_seo(html)
        data: dict[str, Any] = {"url": str(req.url), "seo": seo_data}
        return BaseResponse(status="success", error_code=None, data=data)
    except ScraperError as e:
        logger.exception("SEO parse error")
        code = getattr(e, "error_code", ErrorCode.internal_error)
        return BaseResponse(status="failed", error_code=code, data=None)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected SEO parse error")
        return BaseResponse(status="failed", error_code=ErrorCode.internal_error, data=None)
    finally:
        await service.close()


@app.post(
    "/api/v1/site/content",
    response_model=BaseResponse,
    dependencies=[Depends(auth_dependency)],
)
async def fetch_site_content(
    req: FetchSiteRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SiteFetchService(db)
    try:
        html = await service.fetch_html_cleaned(str(req.url))
        content_data = parse_content(html)
        data: dict[str, Any] = {"url": str(req.url), "content": content_data}
        return BaseResponse(status="success", error_code=None, data=data)
    except ScraperError as e:
        logger.exception("Content parse error")
        code = getattr(e, "error_code", ErrorCode.internal_error)
        return BaseResponse(status="failed", error_code=code, data=None)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected content parse error")
        return BaseResponse(status="failed", error_code=ErrorCode.internal_error, data=None)
    finally:
        await service.close()

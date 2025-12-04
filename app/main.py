import logging

import httpx
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

logger = logging.getLogger(__name__)

setup_logging()
app = FastAPI(title="scraper-service", version=settings.scraper_version)


async def auth_dependency(authorization: str = Header(...)) -> None:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != settings.scraper_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.on_event("startup")
async def on_startup() -> None:
    # Можно сразу же создать таблицы (для MVP), дальше лучше использовать Alembic
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    # Здесь можно закрыть общие клиенты, если будут глобальные
    pass


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": settings.scraper_version}


@app.post("/api/v1/serp/google", dependencies=[Depends(auth_dependency)], response_model=BaseResponse)
async def serp_google(
    req: SerpQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SerpService(db)
    try:
        data: SerpData = await service.fetch_google_serp(req)
        return BaseResponse(status="success", error_code=None, data=data.dict())
    except ScraperError as e:
        logger.error("Google SERP error", extra={"extra": {"error_code": e.error_code.value}})
        return BaseResponse(status="failed", error_code=e.error_code, data=None)
    except Exception as e:
        logger.exception("Google SERP internal error")
        return BaseResponse(status="failed", error_code=ErrorCode.internal_error, data=None)
    finally:
        await service.close()


@app.post("/api/v1/serp/yandex", dependencies=[Depends(auth_dependency)], response_model=BaseResponse)
async def serp_yandex(
    req: SerpQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SerpService(db)
    try:
        data: SerpData = await service.fetch_yandex_serp(req)
        return BaseResponse(status="success", error_code=None, data=data.dict())
    except ScraperError as e:
        logger.error("Yandex SERP error", extra={"extra": {"error_code": e.error_code.value}})
        return BaseResponse(status="failed", error_code=e.error_code, data=None)
    except Exception:
        logger.exception("Yandex SERP internal error")
        return BaseResponse(status="failed", error_code=ErrorCode.internal_error, data=None)
    finally:
        await service.close()


@app.post("/api/v1/fetch-site", dependencies=[Depends(auth_dependency)], response_model=BaseResponse)
async def fetch_site(
    req: FetchSiteRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse:
    service = SiteFetchService(db)
    try:
        data: FetchSiteData = await service.fetch_site(req)
        return BaseResponse(status="success", error_code=None, data=data.dict())
    except Exception:
        logger.exception("Fetch site error")
        return BaseResponse(status="failed", error_code=ErrorCode.source_unavailable, data=None)
    finally:
        await service.close()

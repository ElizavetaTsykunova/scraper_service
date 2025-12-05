import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import Column, BigInteger, String, JSON, DateTime, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db import Base
from app.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SerpCache(Base):
    __tablename__ = "serp_cache"

    id = Column(BigInteger, primary_key=True)
    engine = Column(String(16), nullable=False)
    request_hash = Column(String(64), nullable=False, unique=False)
    request_params = Column(JSON, nullable=False)
    response_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class SiteCache(Base):
    __tablename__ = "site_cache"

    id = Column(BigInteger, primary_key=True)
    request_hash = Column(String(64), nullable=False, unique=True)
    request_params = Column(JSON, nullable=False)
    response_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class CacheRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _make_hash(payload: Any) -> str:
        """
        Превращает произвольный payload (в том числе pydantic-модели)
        в стабильную JSON-строку и считает по ней sha256.

        Важно: pydantic-модели сначала приводим к json-совместимому dict,
        чтобы HttpUrl, datetime и т.п. стали строками.
        """
        # Если прилетела pydantic-модель — приводим к json dict
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(mode="json")

        # На всякий случай даём default=str для редких типов
        dumped = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    def serp_request_hash(self, engine: str, params: dict) -> str:
        return self._make_hash({"engine": engine, **params})

    def site_request_hash(self, params: dict) -> str:
        return self._make_hash(params)

    async def get_serp(self, engine: str, request_hash: str) -> Optional[SerpCache]:
        now = _now()
        query = (
            select(SerpCache)
            .where(
                SerpCache.engine == engine,
                SerpCache.request_hash == request_hash,
                SerpCache.expires_at > now,
            )
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def save_serp(self, engine: str, request_hash: str, request_params: dict, response_data: dict) -> None:
        ttl = settings.cache_ttl_sec
        expires_at = _now() + timedelta(seconds=ttl)
        row = SerpCache(
            engine=engine,
            request_hash=request_hash,
            request_params=request_params,
            response_data=response_data,
            created_at=_now(),
            expires_at=expires_at,
        )
        self.db.add(row)
        await self.db.commit()

    async def get_site(self, request_hash: str) -> Optional[SiteCache]:
        now = _now()
        query = (
            select(SiteCache)
            .where(
                SiteCache.request_hash == request_hash,
                SiteCache.expires_at > now,
            )
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def save_site(self, request_hash: str, request_params: dict, response_data: dict) -> None:
        ttl = settings.cache_ttl_sec
        expires_at = _now() + timedelta(seconds=ttl)
        row = SiteCache(
            request_hash=request_hash,
            request_params=request_params,
            response_data=response_data,
            created_at=_now(),
            expires_at=expires_at,
        )
        self.db.add(row)
        await self.db.commit()

    async def cleanup_expired(self) -> None:
        now = _now()
        await self.db.execute(delete(SerpCache).where(SerpCache.expires_at <= now))
        await self.db.execute(delete(SiteCache).where(SiteCache.expires_at <= now))
        await self.db.commit()

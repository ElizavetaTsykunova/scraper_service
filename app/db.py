from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

Base = declarative_base()


def get_engine() -> AsyncEngine:
    return create_async_engine(
        str(settings.database_url),
        echo=False,
        future=True,
    )


engine = get_engine()

AsyncSessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

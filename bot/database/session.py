import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from bot.config import settings
from bot.utils.logging import logger


def get_engine() -> AsyncEngine:
    db_url = settings.DATABASE_URL
    # Ensure directory exists if using local sqlite file
    if "sqlite" in db_url:
        path = db_url.split("///")[-1]
        dirname = os.path.dirname(path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        return create_async_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False}
        )
    else:
        return create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )


engine: AsyncEngine = get_engine()
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency / context helper to yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

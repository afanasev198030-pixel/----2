from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker as create_async_sessionmaker,
)
from typing import AsyncGenerator

from app.config import settings
from app.models.base import Base


# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL query logging in development
    future=True,
)

# Create async session factory
async_sessionmaker = create_async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with async_sessionmaker() as session:
        try:
            yield session
        finally:
            await session.close()

"""FastAPI dependency providers."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, settings
from src.db.session import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with async_session() as session:
        yield session


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings

import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

# asyncpg doesn't accept ?sslmode= in the URL — strip it and pass ssl via connect_args
_url = settings.database_url.split("?")[0]
_ssl_ctx = ssl.create_default_context()
engine = create_async_engine(_url, echo=False, connect_args={"ssl": _ssl_ctx})
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

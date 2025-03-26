from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from config.dependencies import get_settings


settings = get_settings()

POSTGRES_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
    f"{settings.POSTGRES_HOST}:{settings.POSTGRES_DB_PORT}/{settings.POSTGRES_DB}"
)

postgres_engine = create_async_engine(POSTGRES_DATABASE_URL, echo=False)

postgres_async_session = async_sessionmaker(
    bind=postgres_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_postgres_db() -> AsyncSession:
    async with postgres_async_session() as session:
        yield session

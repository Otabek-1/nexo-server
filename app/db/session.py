from collections.abc import AsyncGenerator
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()
db_url = make_url(settings.async_database_url)
query = dict(db_url.query)
engine_kwargs = {"pool_pre_ping": True, "future": True}

# Supabase transaction pooler (6543 / pgbouncer transaction mode) needs special handling.
if db_url.port == 6543:
    engine_kwargs["poolclass"] = NullPool
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,
    }
    query["prepared_statement_cache_size"] = "0"
    db_url = db_url.set(query=query)
    engine = create_async_engine(str(db_url), **engine_kwargs)
else:
    engine_kwargs["connect_args"] = {"statement_cache_size": 0}
    db_url = db_url.set(query=query)
    engine = create_async_engine(str(db_url), **engine_kwargs)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

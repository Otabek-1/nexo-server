import asyncio
from logging.config import fileConfig
from uuid import uuid4

from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from app.db.migration_bootstrap import LEGACY_BASELINE_REVISION, has_unversioned_legacy_schema
from app.models import *

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
async_url = make_url(settings.async_database_url)
query = dict(async_url.query)
sslmode = query.pop("sslmode", None)
if sslmode and "ssl" not in query:
    query["ssl"] = sslmode
is_supabase_pooler = bool(async_url.host and "pooler.supabase.com" in async_url.host)
migration_connect_args = {"statement_cache_size": 0}
if async_url.port == 6543 and is_supabase_pooler:
    query["prepared_statement_cache_size"] = "0"
    migration_connect_args["prepared_statement_name_func"] = (
        lambda: f"__asyncpg_migration_{uuid4().hex}__"
    )
elif is_supabase_pooler:
    migration_connect_args["ssl"] = "require"
async_url = async_url.set(query=query)

config.set_main_option("sqlalchemy.url", async_url.render_as_string(hide_password=False))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        migration_context = context.get_context()
        if (
            migration_context.get_current_revision() is None
            and has_unversioned_legacy_schema(connection)
        ):
            migration_context.stamp(
                ScriptDirectory.from_config(config),
                LEGACY_BASELINE_REVISION,
            )
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=NullPool,
        connect_args=migration_connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

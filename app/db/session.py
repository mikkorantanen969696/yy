"""
Database engine and session factory.

Using async SQLAlchemy to support both SQLite and Postgres.
"""
from __future__ import annotations

import os
import ssl

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings

engine_kwargs: dict = {
    "echo": False,
    # Reconnect if DB closed idle connection.
    "pool_pre_ping": True,
}
connect_args: dict = {}

is_postgres_asyncpg = settings.database_url.startswith("postgresql+asyncpg")
if is_postgres_asyncpg:
    # Avoid stale prepared statement cache issues after schema/type changes.
    connect_args["statement_cache_size"] = 0

# Optional SSL config for asyncpg (production Postgres).
ssl_mode = (settings.db_ssl_mode or "").strip().lower()
if ssl_mode in {"require", "verify-ca", "verify-full"}:
    cafile = (settings.db_ssl_root_cert or "").strip() or None
    if cafile:
        cafile = os.path.expanduser(cafile)
        if not os.path.exists(cafile):
            raise RuntimeError(f"DB_SSL_ROOT_CERT file not found: {cafile}")
    ssl_ctx = ssl.create_default_context(cafile=cafile)
    if ssl_mode == "require":
        ssl_ctx.check_hostname = False
    else:
        ssl_ctx.check_hostname = ssl_mode == "verify-full"
    connect_args["ssl"] = ssl_ctx

if connect_args:
    engine_kwargs["connect_args"] = connect_args

# Create async engine based on DATABASE_URL.
engine: AsyncEngine = create_async_engine(settings.database_url, **engine_kwargs)

# Async session factory used in services and handlers.
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

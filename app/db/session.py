"""
Database engine and session factory.

Using async SQLAlchemy to support both SQLite and Postgres.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings

# Create async engine based on DATABASE_URL.
engine: AsyncEngine = create_async_engine(settings.database_url, echo=False)

# Async session factory used in services and handlers.
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

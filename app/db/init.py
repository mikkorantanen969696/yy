"""
Database initialization helpers.

Stage 1 uses create_all for SQLite. In stage 2 you can replace
this with Alembic migrations without changing call sites.
"""
from __future__ import annotations

from app.db.session import engine
from app.models.base import Base


async def init_db() -> None:
    """Create tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

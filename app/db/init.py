"""
Database initialization helpers.

Stage 1 uses create_all for SQLite. In stage 2 you can replace
this with Alembic migrations without changing call sites.
"""
from __future__ import annotations

from sqlalchemy import text

from app.db.session import engine
from app.models.base import Base


async def _ensure_postgres_bigint_ids(conn) -> None:
    """
    Ensure Telegram ID columns are BIGINT in Postgres.

    `create_all` does not alter existing columns, so legacy deployments can
    stay on INTEGER and fail for large Telegram IDs.
    """
    await conn.execute(
        text(
            """
            DO $$
            BEGIN
                -- Drop old FKs if they exist.
                IF EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'orders_manager_id_fkey'
                ) THEN
                    ALTER TABLE orders DROP CONSTRAINT orders_manager_id_fkey;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'orders_master_id_fkey'
                ) THEN
                    ALTER TABLE orders DROP CONSTRAINT orders_master_id_fkey;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'responses_master_id_fkey'
                ) THEN
                    ALTER TABLE responses DROP CONSTRAINT responses_master_id_fkey;
                END IF;

                -- Convert Telegram ID columns to BIGINT.
                ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT;
                ALTER TABLE orders ALTER COLUMN manager_id TYPE BIGINT;
                ALTER TABLE orders ALTER COLUMN master_id TYPE BIGINT;
                ALTER TABLE responses ALTER COLUMN master_id TYPE BIGINT;

                -- Recreate FKs to users.telegram_id.
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'orders_manager_id_fkey'
                ) THEN
                    ALTER TABLE orders
                        ADD CONSTRAINT orders_manager_id_fkey
                        FOREIGN KEY (manager_id) REFERENCES users(telegram_id);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'orders_master_id_fkey'
                ) THEN
                    ALTER TABLE orders
                        ADD CONSTRAINT orders_master_id_fkey
                        FOREIGN KEY (master_id) REFERENCES users(telegram_id);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'responses_master_id_fkey'
                ) THEN
                    ALTER TABLE responses
                        ADD CONSTRAINT responses_master_id_fkey
                        FOREIGN KEY (master_id) REFERENCES users(telegram_id);
                END IF;
            END $$;
            """
        )
    )


async def init_db() -> None:
    """Create tables if they do not exist and patch legacy Postgres schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await _ensure_postgres_bigint_ids(conn)

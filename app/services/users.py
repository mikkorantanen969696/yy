"""
User service functions: role checks and lookups.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.constants import ROLES


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Fetch a user by Telegram ID."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def ensure_user(session: AsyncSession, telegram_id: int, role: str = "") -> User:
    """Ensure user exists. Optionally set role if provided."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        if role and user.role != role:
            user.role = role
            await session.commit()
        return user

    user = User(telegram_id=telegram_id, role=role or "", city="")
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
        return user
    except IntegrityError:
        # Concurrent update can insert the same telegram_id first.
        await session.rollback()
        existing = await get_user_by_telegram_id(session, telegram_id)
        if existing:
            if role and existing.role != role:
                existing.role = role
                await session.commit()
                await session.refresh(existing)
            return existing
        raise


async def set_role(session: AsyncSession, telegram_id: int, role: str) -> User:
    """Set role for a user and create user if needed."""
    if role not in ROLES.values():
        raise ValueError("Unknown role")
    user = await ensure_user(session, telegram_id)
    user.role = role
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_active(session: AsyncSession, telegram_id: int, is_active: bool) -> User:
    """Enable or disable user account."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        raise ValueError("User not found")

    user.is_active = is_active
    await session.commit()
    await session.refresh(user)
    return user


async def list_users(
    session: AsyncSession,
    role: str | None = None,
    active: bool | None = None,
    limit: int = 100,
) -> list[User]:
    """List users with optional role and activity filters."""
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if active is not None:
        stmt = stmt.where(User.is_active == active)

    stmt = stmt.order_by(User.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_users(session: AsyncSession) -> int:
    """Total users count."""
    result = await session.execute(select(func.count(User.id)))
    return int(result.scalar() or 0)


async def count_users_by_role(session: AsyncSession) -> dict[str, int]:
    """Count users grouped by role."""
    result = await session.execute(select(User.role, func.count(User.id)).group_by(User.role))
    return {(role or ""): int(count) for role, count in result.all()}


def is_admin(telegram_id: int, admin_ids: list[int]) -> bool:
    """Check if user is in admin list."""
    return telegram_id in admin_ids


def has_role(user: User, role: str) -> bool:
    """Check if user has expected role."""
    return user.role == role


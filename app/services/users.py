"""
User service functions: role checks and lookups.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, bindparam, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.constants import ROLES


def normalize_username(raw: str) -> str:
    """Normalize Telegram username for lookup/storage."""
    value = (raw or "").strip()
    if value.startswith("@"):
        value = value[1:]
    return value.lower()


def username_with_at(username: str | None) -> str:
    """Format normalized username for UI."""
    value = normalize_username(username or "")
    return f"@{value}" if value else "-"


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Fetch a user by Telegram ID."""
    stmt = select(User).where(
        User.telegram_id == bindparam("telegram_id", type_=BigInteger)
    )
    result = await session.execute(stmt, {"telegram_id": int(telegram_id)})
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Fetch a user by Telegram username."""
    normalized = normalize_username(username)
    if not normalized:
        return None
    result = await session.execute(select(User).where(User.username == normalized))
    return result.scalar_one_or_none()


async def get_username_by_telegram_id(session: AsyncSession, telegram_id: int | None) -> str:
    """Return @username for telegram id or fallback to '-'."""
    if not telegram_id:
        return "-"
    user = await get_user_by_telegram_id(session, telegram_id)
    return username_with_at(user.username if user else "")


async def get_usernames_map_by_telegram_ids(
    session: AsyncSession,
    telegram_ids: list[int],
) -> dict[int, str]:
    """Bulk load usernames by Telegram IDs."""
    ids = sorted({int(i) for i in telegram_ids if i})
    if not ids:
        return {}
    result = await session.execute(select(User.telegram_id, User.username).where(User.telegram_id.in_(ids)))
    return {int(tid): username_with_at(uname) for tid, uname in result.all()}


async def resolve_user_selector(
    session: AsyncSession,
    selector: str,
) -> tuple[int | None, str]:
    """
    Resolve selector (telegram id or @username) to telegram id.

    Returns: (telegram_id_or_none, normalized_username_or_empty).
    """
    raw = (selector or "").strip()
    if not raw:
        return None, ""
    if raw.startswith("@"):
        normalized = normalize_username(raw)
        if not normalized:
            return None, ""
        user = await get_user_by_username(session, normalized)
        if not user:
            return None, normalized
        return int(user.telegram_id), normalized
    try:
        return int(raw), ""
    except ValueError:
        return None, ""


async def ensure_user(
    session: AsyncSession,
    telegram_id: int,
    role: str = "",
    username: str = "",
) -> User:
    """Ensure user exists. Optionally set role if provided."""
    normalized_username = normalize_username(username)
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        changed = False
        if role and user.role != role:
            user.role = role
            changed = True
        if normalized_username and user.username != normalized_username:
            user.username = normalized_username
            changed = True
        if changed:
            await session.commit()
        return user

    user = User(telegram_id=telegram_id, username=normalized_username, role=role or "", city="")
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
            changed = False
            if role and existing.role != role:
                existing.role = role
                changed = True
            if normalized_username and existing.username != normalized_username:
                existing.username = normalized_username
                changed = True
            if changed:
                await session.commit()
            await session.refresh(existing)
            return existing
        raise


async def set_role(session: AsyncSession, telegram_id: int, role: str, username: str = "") -> User:
    """Set role for a user and create user if needed."""
    if role not in ROLES.values():
        raise ValueError("Unknown role")
    user = await ensure_user(session, telegram_id, username=username)
    user.role = role
    user.is_active = True
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


def is_admin(
    telegram_id: int,
    admin_ids: list[int],
    username: str = "",
    admin_usernames: list[str] | None = None,
) -> bool:
    """Check admin by username (preferred) or by legacy id whitelist."""
    normalized_username = normalize_username(username)
    allowed_usernames = {normalize_username(item) for item in (admin_usernames or []) if item}
    if normalized_username and normalized_username in allowed_usernames:
        return True
    return telegram_id in admin_ids


def has_role(user: User, role: str) -> bool:
    """Check if user has expected role and is active."""
    return bool(user.is_active) and user.role == role


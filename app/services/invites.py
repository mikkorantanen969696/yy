"""
Secret-word role invites service.
"""
from __future__ import annotations

from datetime import datetime
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role_invite import RoleInvite
from app.utils.constants import ROLES


def normalize_username(raw: str) -> str:
    """Normalize Telegram username for comparison/storage."""
    value = (raw or "").strip()
    if value.startswith("@"):
        value = value[1:]
    return value.lower()


def generate_secret_word(length: int = 10) -> str:
    """Generate random URL-safe secret word."""
    token = secrets.token_urlsafe(length)
    return token[: max(8, min(32, length + 2))]


async def create_role_invite(
    session: AsyncSession,
    role: str,
    target_username: str,
    created_by: int,
) -> RoleInvite:
    """Create one-time invite for a username/role."""
    if role not in (ROLES["admin"], ROLES["manager"]):
        raise ValueError("Unsupported role")

    username = normalize_username(target_username)
    if not username:
        raise ValueError("Username is required")

    # Retry small number of times to avoid rare secret collisions.
    for _ in range(5):
        secret_word = generate_secret_word(12)
        existing = await session.execute(select(RoleInvite).where(RoleInvite.secret_word == secret_word))
        if existing.scalar_one_or_none() is None:
            invite = RoleInvite(
                role=role,
                target_username=username,
                secret_word=secret_word,
                created_by=created_by,
            )
            session.add(invite)
            await session.commit()
            await session.refresh(invite)
            return invite

    raise RuntimeError("Failed to generate unique secret word")


async def consume_role_invite(
    session: AsyncSession,
    secret_word: str,
    actor_telegram_id: int,
    actor_username: str,
) -> RoleInvite | None:
    """Consume invite if secret and username match."""
    normalized_username = normalize_username(actor_username)
    if not normalized_username:
        return None

    result = await session.execute(
        select(RoleInvite).where(
            RoleInvite.secret_word == (secret_word or "").strip(),
            RoleInvite.target_username == normalized_username,
            RoleInvite.is_used.is_(False),
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        return None

    invite.is_used = True
    invite.used_by = actor_telegram_id
    invite.used_at = datetime.utcnow()
    await session.commit()
    await session.refresh(invite)
    return invite


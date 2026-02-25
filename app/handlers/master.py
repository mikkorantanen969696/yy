"""
Master panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.users import ensure_user, has_role
from app.utils.constants import ROLES

router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: Message, db) -> None:
    """Placeholder for master profile."""
    user = await ensure_user(db, message.from_user.id)
    if not has_role(user, ROLES["master"]):
        await message.answer("Нет доступа. Роль мастера не назначена.")
        return
    await message.answer("Профиль мастера: в разработке.")

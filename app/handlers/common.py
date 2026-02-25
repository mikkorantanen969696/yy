"""
Basic commands available to all roles.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from app.config.settings import settings
from app.services.users import ensure_user, is_admin
from app.utils.constants import ROLES

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, db) -> None:
    """Welcome message and short instructions."""
    if is_admin(message.from_user.id, settings.get_admin_ids()):
        await ensure_user(db, message.from_user.id, role=ROLES["admin"])
        await message.answer("Привет! Доступ администратора подтвержден. Используй /admin.")
        return

    await ensure_user(db, message.from_user.id)
    await message.answer(
        "Привет! Используй /manager или /profile в зависимости от роли."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Basic help placeholder."""
    await message.answer(
        "Справка будет расширена в следующей итерации."
    )

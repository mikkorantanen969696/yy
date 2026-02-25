"""
Manager panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config.settings import settings
from app.services.users import ensure_user, has_role, is_admin
from app.utils.constants import ROLES

router = Router()


@router.message(Command("manager"))
async def cmd_manager(message: Message, db) -> None:
    """Manager panel placeholder."""
    user = await ensure_user(db, message.from_user.id)
    if not (has_role(user, ROLES["manager"]) or is_admin(message.from_user.id, settings.get_admin_ids())):
        await message.answer("Нет доступа. Роль менеджера не назначена.")
        return
    await message.answer("Панель менеджера: /new_order для создания заявки.")

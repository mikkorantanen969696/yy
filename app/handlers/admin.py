"""
Admin panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config.settings import settings
from app.services.users import is_admin, set_role
from app.utils.constants import ROLES

router = Router()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Admin panel placeholder."""
    if not is_admin(message.from_user.id, settings.get_admin_ids()):
        await message.answer("Нет доступа.")
        return
    await message.answer(
        "Админ-панель: в разработке.\n"
        "Команда назначения ролей: /set_role <telegram_id> <admin|manager|master>"
    )


@router.message(Command("set_role"))
async def cmd_set_role(message: Message, db) -> None:
    """Assign role to a user by telegram id."""
    if not is_admin(message.from_user.id, settings.get_admin_ids()):
        await message.answer("Нет доступа.")
        return

    parts = message.text.strip().split()
    if len(parts) != 3:
        await message.answer("Формат: /set_role <telegram_id> <admin|manager|master>")
        return

    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("telegram_id должен быть числом.")
        return

    role = parts[2].lower()
    if role not in ROLES.values():
        await message.answer("Роль должна быть admin, manager или master.")
        return

    await set_role(db, telegram_id, role)
    await message.answer(f"Роль {role} назначена пользователю {telegram_id}.")

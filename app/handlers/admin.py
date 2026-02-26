"""
Admin panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types.input_file import BufferedInputFile

from app.config.settings import settings
from app.services.analytics import count_orders, count_by_status, top_managers, top_masters
from app.services.exports import export_basic, export_full
from app.services.users import ensure_user, has_role, is_admin, set_role
from app.utils.constants import ROLES

router = Router()


def _format_stats(total: int, by_status: dict[str, int]) -> str:
    """Build a short stats message."""
    return (
        f"Всего заявок: {total}\n"
        f"Создана: {by_status.get('created', 0)}\n"
        f"Опубликована: {by_status.get('published', 0)}\n"
        f"Назначена: {by_status.get('assigned', 0)}\n"
        f"В процессе: {by_status.get('in_progress', 0)}\n"
        f"Завершена: {by_status.get('completed', 0)}\n"
        f"Отменена: {by_status.get('cancelled', 0)}\n"
    )


async def _can_use_admin(message: Message, db) -> bool:
    """Allow admin access by env whitelist or DB role."""
    if is_admin(message.from_user.id, settings.get_admin_ids()):
        return True
    user = await ensure_user(db, message.from_user.id)
    return has_role(user, ROLES["admin"])


@router.message(Command("admin"))
async def cmd_admin(message: Message, db) -> None:
    """Admin panel placeholder."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return
    await message.answer(
        "Админ-панель:\n"
        "/stats - аналитика\n"
        "/export_basic - экспорт CSV (основной)\n"
        "/export_full - экспорт CSV (полный)\n"
        "/set_role [telegram_id] [admin|manager|master]"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, db) -> None:
    """Show basic analytics."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    total = await count_orders(db)
    by_status = await count_by_status(db)
    managers = await top_managers(db)
    masters = await top_masters(db)

    stats_text = _format_stats(total, by_status)

    if managers:
        stats_text += "\nТоп менеджеров:\n"
        for mid, cnt in managers:
            stats_text += f"- {mid}: {cnt}\n"

    if masters:
        stats_text += "\nТоп мастеров:\n"
        for mid, cnt in masters:
            stats_text += f"- {mid}: {cnt}\n"

    await message.answer(stats_text)


@router.message(Command("export_basic"))
async def cmd_export_basic(message: Message, db) -> None:
    """Send basic CSV export."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    data = await export_basic(db)
    file = BufferedInputFile(data, filename="orders_basic.csv")
    await message.answer_document(file)


@router.message(Command("export_full"))
async def cmd_export_full(message: Message, db) -> None:
    """Send full CSV export."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    data = await export_full(db)
    file = BufferedInputFile(data, filename="orders_full.csv")
    await message.answer_document(file)


@router.message(Command("set_role"))
async def cmd_set_role(message: Message, db) -> None:
    """Assign role to a user by telegram id."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = message.text.strip().split()
    if len(parts) != 3:
        await message.answer("Формат: /set_role [telegram_id] [admin|manager|master]")
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

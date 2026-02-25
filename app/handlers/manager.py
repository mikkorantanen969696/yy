"""
Manager panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config.settings import settings
from app.services.orders import list_orders_by_manager
from app.services.users import ensure_user, has_role, is_admin
from app.utils.constants import ROLES

router = Router()


def _format_orders(orders) -> str:
    """Format orders list for message."""
    if not orders:
        return "Заявок нет."

    lines = ["Мои заявки:"]
    for order in orders[-20:]:
        lines.append(
            f"#{order.id} | {order.city} | {order.date} {order.time} | {order.status}"
        )
    return "\n".join(lines)


@router.message(Command("manager"))
async def cmd_manager(message: Message, db) -> None:
    """Manager panel placeholder."""
    user = await ensure_user(db, message.from_user.id)
    if not (has_role(user, ROLES["manager"]) or is_admin(message.from_user.id, settings.get_admin_ids())):
        await message.answer("Нет доступа. Роль менеджера не назначена.")
        return
    await message.answer(
        "Панель менеджера:\n"
        "/new_order - создать заявку\n"
        "/my_orders - мои заявки\n"
        "/my_stats - моя статистика"
    )


@router.message(Command("my_orders"))
async def cmd_my_orders(message: Message, db) -> None:
    """List manager orders."""
    user = await ensure_user(db, message.from_user.id)
    if not (has_role(user, ROLES["manager"]) or is_admin(message.from_user.id, settings.get_admin_ids())):
        await message.answer("Нет доступа. Роль менеджера не назначена.")
        return

    orders = await list_orders_by_manager(db, user.telegram_id)
    await message.answer(_format_orders(orders))


@router.message(Command("my_stats"))
async def cmd_my_stats(message: Message, db) -> None:
    """Basic manager stats."""
    user = await ensure_user(db, message.from_user.id)
    if not (has_role(user, ROLES["manager"]) or is_admin(message.from_user.id, settings.get_admin_ids())):
        await message.answer("Нет доступа. Роль менеджера не назначена.")
        return

    orders = await list_orders_by_manager(db, user.telegram_id)
    total = len(orders)
    completed = len([o for o in orders if o.status == "completed"])
    await message.answer(
        f"Моя статистика:\n"
        f"Всего заявок: {total}\n"
        f"Завершено: {completed}"
    )

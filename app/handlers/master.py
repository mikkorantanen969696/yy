"""
Master panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.orders import list_orders_by_master
from app.services.users import ensure_user, has_role
from app.utils.constants import ROLES
from app.utils.text import format_user_link

router = Router()


def _format_orders(orders) -> str:
    """Format orders list for message."""
    if not orders:
        return "📭 У вас пока нет заказов."

    lines = ["🧰 Ваши последние заказы:"]
    for order in orders[-20:]:
        manager_link = format_user_link(order.manager_id, "менеджер")
        lines.append(
            f"#{order.id} | {order.city} | {order.date} {order.time} | {order.status} | {manager_link}"
        )
    return "\n".join(lines)


@router.message(Command("profile"))
async def cmd_profile(message: Message, db) -> None:
    """Master profile."""
    user = await ensure_user(db, message.from_user.id)
    if not has_role(user, ROLES["master"]):
        await message.answer("⛔ Нет доступа. Роль мастера не назначена.")
        return
    await message.answer(
        "👷 Профиль мастера\n"
        "/my_jobs - мои заказы\n"
        "/my_stats - моя статистика\n\n"
        "ℹ️ Подробная инструкция: /help"
    )


@router.message(Command("my_jobs"))
async def cmd_my_jobs(message: Message, db) -> None:
    """List master orders."""
    user = await ensure_user(db, message.from_user.id)
    if not has_role(user, ROLES["master"]):
        await message.answer("⛔ Нет доступа. Роль мастера не назначена.")
        return

    orders = await list_orders_by_master(db, user.telegram_id)
    await message.answer(_format_orders(orders))


@router.message(Command("my_stats"))
async def cmd_my_stats(message: Message, db) -> None:
    """Basic master stats."""
    user = await ensure_user(db, message.from_user.id)
    if not has_role(user, ROLES["master"]):
        await message.answer("⛔ Нет доступа. Роль мастера не назначена.")
        return

    orders = await list_orders_by_master(db, user.telegram_id)
    total = len(orders)
    completed = len([o for o in orders if o.status == "completed"])
    await message.answer(
        f"📊 Моя статистика:\n"
        f"Всего заказов: {total}\n"
        f"Завершено: {completed}"
    )

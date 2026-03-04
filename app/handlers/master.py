"""
Master panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.services.orders import list_orders_by_master
from app.services.users import ensure_user, get_usernames_map_by_telegram_ids, has_role, username_with_at
from app.utils.constants import ROLES
from app.utils.keyboards import build_master_panel_keyboard

router = Router()


async def _format_orders(db, orders) -> str:
    """Format orders list for message."""
    if not orders:
        return "👷 Роль собеседника: мастер\n📭 У вас пока нет заказов."

    ids = [int(order.manager_id) for order in orders if order.manager_id]
    usernames = await get_usernames_map_by_telegram_ids(db, ids)

    lines = ["👷 Роль собеседника: мастер", "🧰 Ваши последние заказы:"]
    for order in orders[-20:]:
        manager_name = usernames.get(int(order.manager_id), "-") if order.manager_id else "-"
        lines.append(
            f"#{order.id} | {order.city} | {order.date} {order.time} | {order.status} | менеджер: {manager_name}"
        )
    return "\n".join(lines)


@router.message(Command("profile"))
async def cmd_profile(message: Message, db) -> None:
    """Master profile."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    if not has_role(user, ROLES["master"]):
        await message.answer("⛔ Нет доступа. Роль мастера не назначена.")
        return
    await message.answer(
        "👷 Профиль мастера\n"
        "Выберите действие кнопками ниже.\n"
        "💡 Подсказка: заказы приходят после отклика в группе.",
        reply_markup=build_master_panel_keyboard(),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("master:"))
async def master_panel_callback(callback: CallbackQuery, db) -> None:
    """Handle master quick actions."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    user = await ensure_user(db, callback.from_user.id, username=callback.from_user.username or "")
    if not has_role(user, ROLES["master"]):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]
    if action == "refresh":
        await callback.message.edit_text(
            "👷 Профиль мастера\nВыберите действие кнопками ниже.",
            reply_markup=build_master_panel_keyboard(),
        )
        await callback.answer("Обновлено.")
        return
    if action == "my_jobs":
        orders = await list_orders_by_master(db, user.telegram_id)
        await callback.message.answer(await _format_orders(db, orders))
        await callback.answer()
        return
    if action == "my_stats":
        orders = await list_orders_by_master(db, user.telegram_id)
        total = len(orders)
        completed = len([o for o in orders if o.status == "completed"])
        await callback.message.answer(
            f"👷 Роль собеседника: мастер\n"
            f"📊 Моя статистика:\n"
            f"Username: {username_with_at(user.username)}\n"
            f"Всего заказов: {total}\n"
            f"Завершено: {completed}"
        )
        await callback.answer()
        return

    await callback.answer("Неизвестное действие.")


@router.message(Command("my_jobs"))
async def cmd_my_jobs(message: Message, db) -> None:
    """List master orders."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    if not has_role(user, ROLES["master"]):
        await message.answer("⛔ Нет доступа. Роль мастера не назначена.")
        return

    orders = await list_orders_by_master(db, user.telegram_id)
    await message.answer(await _format_orders(db, orders))


@router.message(Command("my_stats"))
async def cmd_my_stats(message: Message, db) -> None:
    """Basic master stats."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    if not has_role(user, ROLES["master"]):
        await message.answer("⛔ Нет доступа. Роль мастера не назначена.")
        return

    orders = await list_orders_by_master(db, user.telegram_id)
    total = len(orders)
    completed = len([o for o in orders if o.status == "completed"])
    await message.answer(
        f"👷 Роль собеседника: мастер\n"
        f"📊 Моя статистика:\n"
        f"Username: {username_with_at(user.username)}\n"
        f"Всего заказов: {total}\n"
        f"Завершено: {completed}"
    )

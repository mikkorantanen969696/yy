"""
Manager panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types.input_file import BufferedInputFile

from app.config.settings import settings
from app.services.exports import export_basic_for_manager
from app.services.orders import list_orders_by_manager
from app.services.users import ensure_user, has_role, is_admin, username_with_at
from app.utils.constants import ROLES
from app.utils.keyboards import build_manager_panel_keyboard

router = Router()


def _format_orders(orders) -> str:
    """Format orders list for message."""
    if not orders:
        return "👨‍💼 Роль собеседника: менеджер\n📭 У вас пока нет заявок."

    lines = ["👨‍💼 Роль собеседника: менеджер", "📋 Ваши последние заявки:"]
    for order in orders[-20:]:
        lines.append(
            f"#{order.id} | {order.city} | {order.date} {order.time} | {order.status}"
        )
    return "\n".join(lines)


@router.message(Command("manager"))
async def cmd_manager(message: Message, db) -> None:
    """Manager panel."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    if not (
        has_role(user, ROLES["manager"])
        or is_admin(
            message.from_user.id,
            settings.get_admin_ids(),
            username=message.from_user.username or "",
            admin_usernames=settings.get_admin_usernames(),
        )
    ):
        await message.answer("⛔ Нет доступа. Роль менеджера не назначена.")
        return
    await message.answer(
        "👨‍💼 Панель менеджера\n"
        "Выберите действие кнопками ниже.\n"
        "💡 Подсказка: заявку можно создать здесь же кнопкой «Новая заявка».",
        reply_markup=build_manager_panel_keyboard(),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("manager:"))
async def manager_panel_callback(callback: CallbackQuery, state: FSMContext, db) -> None:
    """Handle manager quick actions."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    user = await ensure_user(db, callback.from_user.id, username=callback.from_user.username or "")
    allowed = has_role(user, ROLES["manager"]) or is_admin(
        callback.from_user.id,
        settings.get_admin_ids(),
        username=callback.from_user.username or "",
        admin_usernames=settings.get_admin_usernames(),
    )
    if not allowed:
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]
    if action == "refresh":
        await callback.message.edit_text(
            "👨‍💼 Панель менеджера\nВыберите действие кнопками ниже.",
            reply_markup=build_manager_panel_keyboard(),
        )
        await callback.answer("Обновлено.")
        return
    if action == "new_order":
        from app.handlers.order_flow import start_order_flow

        msg = callback.message
        if msg:
            await start_order_flow(msg, state, db)
        await callback.answer()
        return
    if action == "my_orders":
        orders = await list_orders_by_manager(db, user.telegram_id)
        await callback.message.answer(_format_orders(orders))
        await callback.answer()
        return
    if action == "my_stats":
        orders = await list_orders_by_manager(db, user.telegram_id)
        total = len(orders)
        completed = len([o for o in orders if o.status == "completed"])
        await callback.message.answer(
            f"👨‍💼 Роль собеседника: менеджер\n"
            f"📊 Моя статистика:\n"
            f"Username: {username_with_at(user.username)}\n"
            f"Всего заявок: {total}\n"
            f"Завершено: {completed}"
        )
        await callback.answer()
        return
    if action == "export_basic":
        data = await export_basic_for_manager(db, user.telegram_id)
        username = (user.username or "manager").strip() or "manager"
        file = BufferedInputFile(data, filename=f"orders_basic_manager_{username}.csv")
        await callback.message.answer_document(file)
        await callback.answer("Экспорт отправлен.")
        return

    await callback.answer("Неизвестное действие.")


@router.message(Command("my_orders"))
async def cmd_my_orders(message: Message, db) -> None:
    """List manager orders."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    if not (
        has_role(user, ROLES["manager"])
        or is_admin(
            message.from_user.id,
            settings.get_admin_ids(),
            username=message.from_user.username or "",
            admin_usernames=settings.get_admin_usernames(),
        )
    ):
        await message.answer("⛔ Нет доступа. Роль менеджера не назначена.")
        return

    orders = await list_orders_by_manager(db, user.telegram_id)
    await message.answer(_format_orders(orders))


@router.message(Command("my_stats"))
async def cmd_my_stats(message: Message, db) -> None:
    """Basic manager stats."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    if not (
        has_role(user, ROLES["manager"])
        or is_admin(
            message.from_user.id,
            settings.get_admin_ids(),
            username=message.from_user.username or "",
            admin_usernames=settings.get_admin_usernames(),
        )
    ):
        await message.answer("⛔ Нет доступа. Роль менеджера не назначена.")
        return

    orders = await list_orders_by_manager(db, user.telegram_id)
    total = len(orders)
    completed = len([o for o in orders if o.status == "completed"])
    await message.answer(
        f"👨‍💼 Роль собеседника: менеджер\n"
        f"📊 Моя статистика:\n"
        f"Username: {username_with_at(user.username)}\n"
        f"Всего заявок: {total}\n"
        f"Завершено: {completed}"
    )


@router.message(Command("my_export_basic"))
async def cmd_my_export_basic(message: Message, db) -> None:
    """Send manager-scoped basic CSV export."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    if not (
        has_role(user, ROLES["manager"])
        or is_admin(
            message.from_user.id,
            settings.get_admin_ids(),
            username=message.from_user.username or "",
            admin_usernames=settings.get_admin_usernames(),
        )
    ):
        await message.answer("⛔ Нет доступа. Роль менеджера не назначена.")
        return

    data = await export_basic_for_manager(db, user.telegram_id)
    username = (user.username or "manager").strip() or "manager"
    file = BufferedInputFile(data, filename=f"orders_basic_manager_{username}.csv")
    await message.answer_document(file)


@router.message(Command("my_export_full"))
async def cmd_my_export_full(message: Message, db) -> None:
    """Managers are restricted to basic export only."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    if not (
        has_role(user, ROLES["manager"])
        or is_admin(
            message.from_user.id,
            settings.get_admin_ids(),
            username=message.from_user.username or "",
            admin_usernames=settings.get_admin_usernames(),
        )
    ):
        await message.answer("⛔ Нет доступа. Роль менеджера не назначена.")
        return
    await message.answer("⛔ Менеджеру доступна только основная выгрузка: /my_export_basic")

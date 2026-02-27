"""
Admin panel entrypoints.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.types.input_file import BufferedInputFile

from app.config.settings import settings
from app.services.analytics import (
    count_orders,
    count_by_city,
    count_by_status,
    top_managers,
    top_masters,
)
from app.services.exports import export_basic, export_full
from app.services.orders import (
    assign_master,
    get_order,
    list_recent_orders,
    set_status,
    unassign_master,
)
from app.services.users import (
    count_users,
    count_users_by_role,
    ensure_user,
    has_role,
    is_admin,
    list_users,
    set_role,
    set_user_active,
)
from app.utils.constants import CITY_CHOICES, ORDER_STATUSES, ROLES
from app.utils.keyboards import (
    build_admin_orders_filter_keyboard,
    build_admin_panel_keyboard,
    build_admin_users_filter_keyboard,
)

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


def _city_label(city_key: str) -> str:
    """Map city key to human-readable label."""
    return CITY_CHOICES.get(city_key, city_key)


def _usage() -> str:
    """Admin command list."""
    return (
        "Админ-панель:\n"
        "/stats - общая аналитика\n"
        "/city_stats - статистика по городам\n"
        "/orders [status|all] [limit] - последние заявки\n"
        "/order [id] - детальная заявка\n"
        "/set_status [order_id] [status] - сменить статус\n"
        "/reassign [order_id] [master_tg_id|none] - назначить/снять мастера\n"
        "/users [role|all] [active|inactive|all] [limit] - пользователи\n"
        "/set_role [telegram_id] [admin|manager|master] - назначить роль\n"
        "/set_active [telegram_id] [on|off] - активировать/деактивировать\n"
        "/broadcast [role|all] [текст] - рассылка пользователям\n"
        "/export_basic - экспорт CSV (основной)\n"
        "/export_full - экспорт CSV (полный)"
    )


def _parse_limit(raw: str, default: int = 20, minimum: int = 1, maximum: int = 200) -> int:
    """Parse and clamp command limit argument."""
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _format_orders_list(orders: list, title: str) -> str:
    """Format compact order list for admin output."""
    if not orders:
        return "Заявки не найдены."

    lines = [title]
    for order in orders:
        lines.append(
            f"#{order.id} | {_city_label(order.city)} | {order.date} {order.time} | {order.status} | "
            f"mgr:{order.manager_id or '-'} | mst:{order.master_id or '-'}"
        )
    return "\n".join(lines)


def _format_users_list(users: list, total_users: int, by_role: dict[str, int], title: str) -> str:
    """Format compact users list for admin output."""
    if not users:
        return "Пользователи не найдены."

    lines = [
        title,
        f"Всего в системе: {total_users}",
        "По ролям: " + ", ".join(f"{k or 'без роли'}={v}" for k, v in by_role.items()),
    ]
    for user in users:
        lines.append(
            f"- tg:{user.telegram_id} | role:{user.role or '-'} | "
            f"active:{'yes' if user.is_active else 'no'} | city:{user.city or '-'}"
        )
    return "\n".join(lines)


async def _can_use_admin(message: Message, db) -> bool:
    """Allow admin access by env whitelist or DB role."""
    if is_admin(message.from_user.id, settings.get_admin_ids()):
        return True
    user = await ensure_user(db, message.from_user.id)
    return has_role(user, ROLES["admin"])


@router.message(Command("admin"))
async def cmd_admin(message: Message, db) -> None:
    """Admin panel help."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return
    await message.answer(_usage(), reply_markup=build_admin_panel_keyboard())


@router.callback_query(lambda c: c.data and c.data.startswith("admin:"))
async def admin_panel_callback(callback: CallbackQuery, db) -> None:
    """Handle admin panel button presses."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    if not await _can_use_admin(callback.message, db):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]

    if action == "refresh":
        await callback.message.edit_text(_usage(), reply_markup=build_admin_panel_keyboard())
        await callback.answer("Меню обновлено.")
        return

    if action == "stats":
        total = await count_orders(db)
        by_status = await count_by_status(db)
        by_city = await count_by_city(db)
        managers = await top_managers(db)
        masters = await top_masters(db)

        stats_text = _format_stats(total, by_status)
        if by_city:
            stats_text += "\nТоп городов:\n"
            for city, cnt in list(by_city.items())[:5]:
                stats_text += f"- {_city_label(city)}: {cnt}\n"
        if managers:
            stats_text += "\nТоп менеджеров:\n"
            for mid, cnt in managers:
                stats_text += f"- {mid}: {cnt}\n"
        if masters:
            stats_text += "\nТоп мастеров:\n"
            for mid, cnt in masters:
                stats_text += f"- {mid}: {cnt}\n"

        await callback.message.answer(stats_text)
        await callback.answer()
        return

    if action == "city_stats":
        by_city = await count_by_city(db)
        if not by_city:
            await callback.message.answer("По городам пока нет данных.")
        else:
            lines = ["Статистика по городам:"]
            for city, cnt in by_city.items():
                lines.append(f"- {_city_label(city)}: {cnt}")
            await callback.message.answer("\n".join(lines))
        await callback.answer()
        return

    if action == "orders":
        orders = await list_recent_orders(db, status=None, limit=20)
        await callback.message.answer(
            _format_orders_list(orders, "Последние заявки (до 20, фильтр: all):"),
            reply_markup=build_admin_orders_filter_keyboard(),
        )
        await callback.answer()
        return

    if action.startswith("orders_filter:"):
        _, status_token = action.split(":", 1)
        status = None if status_token == "all" else status_token
        orders = await list_recent_orders(db, status=status, limit=20)
        await callback.message.answer(
            _format_orders_list(
                orders,
                f"Последние заявки (до 20, фильтр: {status_token}):",
            ),
            reply_markup=build_admin_orders_filter_keyboard(),
        )
        await callback.answer("Фильтр применен.")
        return

    if action == "users":
        users = await list_users(db, role=None, active=None, limit=20)
        total_users = await count_users(db)
        by_role = await count_users_by_role(db)
        await callback.message.answer(
            _format_users_list(users, total_users, by_role, "Пользователи (до 20, фильтр: all/all)"),
            reply_markup=build_admin_users_filter_keyboard(),
        )
        await callback.answer()
        return

    if action.startswith("users_filter:"):
        parts = action.split(":")
        if len(parts) != 3:
            await callback.answer("Ошибка фильтра.", show_alert=True)
            return

        role_token = parts[1]
        active_token = parts[2]

        role = None if role_token == "all" else role_token
        if role and role not in ROLES.values():
            await callback.answer("Роль в фильтре неизвестна.", show_alert=True)
            return

        active = None
        if active_token == "active":
            active = True
        elif active_token == "inactive":
            active = False
        elif active_token != "all":
            await callback.answer("Статус активности в фильтре неизвестен.", show_alert=True)
            return

        users = await list_users(db, role=role, active=active, limit=20)
        total_users = await count_users(db)
        by_role = await count_users_by_role(db)
        await callback.message.answer(
            _format_users_list(
                users,
                total_users,
                by_role,
                f"Пользователи (до 20, фильтр: {role_token}/{active_token})",
            ),
            reply_markup=build_admin_users_filter_keyboard(),
        )
        await callback.answer("Фильтр применен.")
        return

    if action == "export_basic":
        data = await export_basic(db)
        file = BufferedInputFile(data, filename="orders_basic.csv")
        await callback.message.answer_document(file)
        await callback.answer("Экспорт отправлен.")
        return

    if action == "export_full":
        data = await export_full(db)
        file = BufferedInputFile(data, filename="orders_full.csv")
        await callback.message.answer_document(file)
        await callback.answer("Экспорт отправлен.")
        return

    await callback.answer("Неизвестное действие.")


@router.message(Command("stats"))
async def cmd_stats(message: Message, db) -> None:
    """Show extended analytics."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    total = await count_orders(db)
    by_status = await count_by_status(db)
    by_city = await count_by_city(db)
    managers = await top_managers(db)
    masters = await top_masters(db)

    stats_text = _format_stats(total, by_status)

    if by_city:
        stats_text += "\nТоп городов:\n"
        for city, cnt in list(by_city.items())[:5]:
            stats_text += f"- {_city_label(city)}: {cnt}\n"

    if managers:
        stats_text += "\nТоп менеджеров:\n"
        for mid, cnt in managers:
            stats_text += f"- {mid}: {cnt}\n"

    if masters:
        stats_text += "\nТоп мастеров:\n"
        for mid, cnt in masters:
            stats_text += f"- {mid}: {cnt}\n"

    await message.answer(stats_text)


@router.message(Command("city_stats"))
async def cmd_city_stats(message: Message, db) -> None:
    """Show city-level order distribution."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    by_city = await count_by_city(db)
    if not by_city:
        await message.answer("По городам пока нет данных.")
        return

    lines = ["Статистика по городам:"]
    for city, cnt in by_city.items():
        lines.append(f"- {_city_label(city)}: {cnt}")
    await message.answer("\n".join(lines))


@router.message(Command("orders"))
async def cmd_orders(message: Message, db) -> None:
    """List latest orders with optional status filter."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = (message.text or "").strip().split()
    status = None
    limit = 20

    if len(parts) >= 2:
        raw_status = parts[1].lower()
        if raw_status != "all":
            if raw_status not in ORDER_STATUSES.values():
                await message.answer(
                    "Статус неизвестен. Используйте: all, created, published, assigned, in_progress, completed, cancelled."
                )
                return
            status = raw_status

    if len(parts) >= 3:
        limit = _parse_limit(parts[2])

    orders = await list_recent_orders(db, status=status, limit=limit)
    if not orders:
        await message.answer("Заявки не найдены.")
        return

    lines = [f"Последние заявки (до {limit}):"]
    for order in orders:
        lines.append(
            f"#{order.id} | {_city_label(order.city)} | {order.date} {order.time} | {order.status} | "
            f"mgr:{order.manager_id or '-'} | mst:{order.master_id or '-'}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("order"))
async def cmd_order_detail(message: Message, db) -> None:
    """Show full details for one order."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: /order [id]")
        return

    try:
        order_id = int(parts[1])
    except ValueError:
        await message.answer("id должен быть числом.")
        return

    order = await get_order(db, order_id)
    if not order:
        await message.answer("Заявка не найдена.")
        return

    await message.answer(
        f"Заявка #{order.id}\n"
        f"Город: {_city_label(order.city)}\n"
        f"Адрес: {order.address}\n"
        f"Дата/время: {order.date} {order.time}\n"
        f"Тип: {order.type}\n"
        f"Оборудование: {order.equipment}\n"
        f"Условия: {order.conditions}\n"
        f"Комментарий: {order.comment or '-'}\n"
        f"Контакт клиента: {order.client_contact or '-'}\n"
        f"Контакт менеджера: {order.manager_contact or '-'}\n"
        f"Менеджер TG: {order.manager_id or '-'}\n"
        f"Мастер TG: {order.master_id or '-'}\n"
        f"Статус: {order.status}\n"
        f"Создана: {order.created_at.isoformat() if order.created_at else '-'}"
    )


@router.message(Command("set_status"))
async def cmd_set_status(message: Message, db) -> None:
    """Change order status."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = (message.text or "").strip().split()
    if len(parts) != 3:
        await message.answer(
            "Формат: /set_status [order_id] [created|published|assigned|in_progress|completed|cancelled]"
        )
        return

    try:
        order_id = int(parts[1])
    except ValueError:
        await message.answer("order_id должен быть числом.")
        return

    status = parts[2].lower()
    if status not in ORDER_STATUSES.values():
        await message.answer("Неизвестный статус.")
        return

    order = await get_order(db, order_id)
    if not order:
        await message.answer("Заявка не найдена.")
        return

    await set_status(db, order, status)
    await message.answer(f"Заявка #{order_id}: статус обновлен на {status}.")


@router.message(Command("reassign"))
async def cmd_reassign(message: Message, db) -> None:
    """Assign or unassign master for an order."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = (message.text or "").strip().split()
    if len(parts) != 3:
        await message.answer("Формат: /reassign [order_id] [master_tg_id|none]")
        return

    try:
        order_id = int(parts[1])
    except ValueError:
        await message.answer("order_id должен быть числом.")
        return

    order = await get_order(db, order_id)
    if not order:
        await message.answer("Заявка не найдена.")
        return

    raw_master = parts[2].lower()
    if raw_master == "none":
        await unassign_master(db, order)
        await message.answer(f"Заявка #{order_id}: мастер снят, статус -> published.")
        return

    try:
        master_telegram_id = int(raw_master)
    except ValueError:
        await message.answer("master_tg_id должен быть числом или none.")
        return

    await ensure_user(db, master_telegram_id, role=ROLES["master"])
    await assign_master(db, order, master_telegram_id)
    await message.answer(
        f"Заявка #{order_id}: назначен мастер {master_telegram_id}, статус -> assigned."
    )


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


@router.message(Command("users"))
async def cmd_users(message: Message, db) -> None:
    """List users with role and status filters."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = (message.text or "").strip().split()

    role = None
    if len(parts) >= 2:
        raw_role = parts[1].lower()
        if raw_role != "all":
            if raw_role not in ROLES.values():
                await message.answer("Роль должна быть: all, admin, manager или master.")
                return
            role = raw_role

    active = None
    if len(parts) >= 3:
        raw_active = parts[2].lower()
        if raw_active == "active":
            active = True
        elif raw_active == "inactive":
            active = False
        elif raw_active != "all":
            await message.answer("Активность должна быть: all, active или inactive.")
            return

    limit = 20
    if len(parts) >= 4:
        limit = _parse_limit(parts[3])

    users = await list_users(db, role=role, active=active, limit=limit)
    if not users:
        await message.answer("Пользователи не найдены.")
        return

    total_users = await count_users(db)
    by_role = await count_users_by_role(db)

    lines = [
        f"Пользователи (до {limit}) | всего в системе: {total_users}",
        "По ролям: " + ", ".join(f"{k or 'без роли'}={v}" for k, v in by_role.items()),
    ]
    for user in users:
        lines.append(
            f"- tg:{user.telegram_id} | role:{user.role or '-'} | "
            f"active:{'yes' if user.is_active else 'no'} | city:{user.city or '-'}"
        )

    await message.answer("\n".join(lines))


@router.message(Command("set_role"))
async def cmd_set_role(message: Message, db) -> None:
    """Assign role to a user by telegram id."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = (message.text or "").strip().split()
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


@router.message(Command("set_active"))
async def cmd_set_active(message: Message, db) -> None:
    """Enable or disable a user account."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = (message.text or "").strip().split()
    if len(parts) != 3:
        await message.answer("Формат: /set_active [telegram_id] [on|off]")
        return

    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("telegram_id должен быть числом.")
        return

    mode = parts[2].lower()
    if mode not in ("on", "off"):
        await message.answer("Используйте on или off.")
        return

    try:
        user = await set_user_active(db, telegram_id, is_active=(mode == "on"))
    except ValueError:
        await message.answer("Пользователь не найден.")
        return

    await message.answer(
        f"Пользователь {user.telegram_id}: active={'yes' if user.is_active else 'no'}."
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, db) -> None:
    """Send admin broadcast to users by role."""
    if not await _can_use_admin(message, db):
        await message.answer("Нет доступа.")
        return

    parts = (message.text or "").strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /broadcast [role|all] [текст]")
        return

    role = parts[1].lower()
    text = parts[2].strip()
    if not text:
        await message.answer("Текст рассылки не должен быть пустым.")
        return

    role_filter = None
    if role != "all":
        if role not in ROLES.values():
            await message.answer("Роль должна быть: all, admin, manager или master.")
            return
        role_filter = role

    recipients = await list_users(db, role=role_filter, active=True, limit=5000)
    if not recipients:
        await message.answer("Нет получателей для рассылки.")
        return

    sent = 0
    failed = 0
    for user in recipients:
        try:
            await message.bot.send_message(user.telegram_id, text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"Рассылка завершена. Успешно: {sent}, ошибок: {failed}, целевая роль: {role}."
    )


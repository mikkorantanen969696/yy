"""
Order creation and photo workflow handlers.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.config.settings import settings
from app.services.orders import (
    add_photo,
    assign_master,
    create_order,
    get_master_visible_fields,
    get_order,
    get_order_photo_counts,
    get_order_photo_type_count,
    register_response,
    set_master_visible_fields,
    set_status,
    unassign_master,
)
from app.services.telegram import send_to_city_topic
from app.services.users import ensure_user, has_role, is_admin
from app.utils.constants import (
    CITY_CHOICES,
    CLEANING_TYPES,
    CONDITION_OPTIONS,
    EQUIPMENT_OPTIONS,
    ORDER_STATUSES,
    ROLES,
)
from app.utils.keyboards import (
    MASTER_VISIBLE_FIELD_LABELS,
    build_form_city_keyboard,
    build_form_cleaning_type_keyboard,
    build_form_conditions_keyboard,
    build_form_date_keyboard,
    build_form_equipment_keyboard,
    build_master_accept_keyboard,
    build_order_menu_keyboard,
    build_photo_actions_keyboard,
    build_visibility_keyboard,
)
from app.utils.text import format_manager_contact, format_order_brief, format_user_link

router = Router()
logger = logging.getLogger(__name__)

DEFAULT_VISIBLE_FIELDS = {"date", "time", "address", "type", "equipment", "conditions", "comment"}
REQUIRED_ORDER_FIELDS = (
    "city",
    "date",
    "time",
    "address",
    "cleaning_type",
    "equipment",
    "conditions",
    "client_contact",
)
TEXT_INPUT_FIELDS = {"date", "time", "address", "comment", "client_contact"}
MIN_PHOTOS_PER_TYPE = 3
MAX_PHOTOS_PER_TYPE = 5


class OrderFlow(StatesGroup):
    """FSM states for one-message order constructor."""

    menu = State()
    input_text = State()
    visible_fields = State()


class PhotoFlow(StatesGroup):
    """FSM state for master photo uploads."""

    waiting_photo = State()


def _format_date(date_obj: datetime) -> str:
    """Format date as dd.mm.yyyy."""
    return date_obj.strftime("%d.%m.%Y")


def _role_label(is_admin_user: bool) -> str:
    """Role badge for order creation message."""
    return "администратор" if is_admin_user else "менеджер"


def _build_form_text(data: dict, prompt: str, role_label: str) -> str:
    """Render one persistent order constructor message."""
    city_key = data.get("city", "")
    city_value = CITY_CHOICES.get(city_key, city_key) or "-"
    date_value = data.get("date", "") or "-"
    time_value = data.get("time", "") or "-"
    address_value = data.get("address", "") or "-"
    type_value = data.get("cleaning_type", "") or "-"
    equipment_value = data.get("equipment", "") or "-"
    conditions_value = data.get("conditions", "") or "-"
    comment_value = data.get("comment", "") or "-"
    client_contact_value = data.get("client_contact", "") or "-"
    selected_fields = set(data.get("visible_fields", set()))
    visible_items = [
        MASTER_VISIBLE_FIELD_LABELS[key]
        for key in MASTER_VISIBLE_FIELD_LABELS
        if key in selected_fields
    ]
    visible_value = ", ".join(visible_items) if visible_items else "-"

    return (
        "📝 Конструктор заявки\n"
        f"Роль собеседника: {role_label}\n\n"
        f"🏙️ Город: {city_value}\n"
        f"📅 Дата: {date_value}\n"
        f"⏰ Время: {time_value}\n"
        f"📍 Адрес: {address_value}\n"
        f"🧹 Тип уборки: {type_value}\n"
        f"🧰 Оборудование: {equipment_value}\n"
        f"💸 Условия: {conditions_value}\n"
        f"💬 Комментарий: {comment_value}\n"
        f"📞 Контакт клиента: {client_contact_value}\n"
        f"👁️ Видно мастеру: {visible_value}\n\n"
        f"{prompt}"
    )


def _missing_fields(data: dict) -> list[str]:
    """Return required fields that are not filled yet."""
    labels = {
        "city": "Город",
        "date": "Дата",
        "time": "Время",
        "address": "Адрес",
        "cleaning_type": "Тип уборки",
        "equipment": "Оборудование",
        "conditions": "Условия",
        "client_contact": "Контакт клиента",
    }
    out: list[str] = []
    for key in REQUIRED_ORDER_FIELDS:
        if not data.get(key):
            out.append(labels[key])
    return out


def _build_master_text(order, visible_fields: set[str]) -> str:
    """Format order card for master based on selected visibility."""
    city_label = CITY_CHOICES.get(order.city, order.city)
    lines = ["Роль собеседника: мастер", f"Заявка #{order.id}", f"Город: {city_label}"]

    if "date" in visible_fields or "time" in visible_fields:
        date_part = order.date if "date" in visible_fields else ""
        time_part = order.time if "time" in visible_fields else ""
        lines.append(f"Дата: {date_part} {time_part}".strip())
    if "address" in visible_fields:
        lines.append(f"Адрес: {order.address}")
    if "type" in visible_fields:
        lines.append(f"Тип: {order.type}")
    if "equipment" in visible_fields:
        lines.append(f"Оборудование: {order.equipment}")
    if "conditions" in visible_fields:
        lines.append(f"Условия: {order.conditions}")
    if "comment" in visible_fields:
        lines.append(f"Комментарий: {order.comment or '-'}")
    if "client_contact" in visible_fields:
        lines.append(f"Контакт клиента: {order.client_contact or '-'}")

    return "\n".join(lines)


async def _edit_form_message(bot, chat_id: int, state: FSMContext, prompt: str, reply_markup=None) -> None:
    """Edit persistent constructor message."""
    data = await state.get_data()
    form_message_id = data.get("form_message_id")
    if not form_message_id:
        return

    text = _build_form_text(data, prompt, data.get("creator_role_label", "менеджер"))
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=form_message_id,
            text=text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        raise


async def _ensure_manager(message: Message, db) -> bool:
    """Managers and admins can create orders."""
    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    return has_role(user, ROLES["manager"]) or is_admin(message.from_user.id, settings.get_admin_ids())


async def _notify_manager(bot, manager_id: int | None, text: str) -> None:
    """Send manager notification and ignore delivery errors."""
    if not manager_id:
        return
    try:
        await bot.send_message(chat_id=manager_id, text=text)
    except Exception:
        logger.exception("Manager notification failed for %s", manager_id)


async def _show_main_menu(callback_or_message, state: FSMContext, prompt: str = "Выберите поле для заполнения:") -> None:
    """Render constructor main menu."""
    bot = callback_or_message.bot
    chat_id = callback_or_message.chat.id
    data = await state.get_data()
    await state.set_state(OrderFlow.menu)
    await _edit_form_message(
        bot,
        chat_id,
        state,
        prompt,
        build_order_menu_keyboard(data),
    )


@router.message(Command("new_order"))
async def start_order_flow(message: Message, state: FSMContext, db) -> None:
    """Start one-message order constructor."""
    if not await _ensure_manager(message, db):
        await message.answer("⛔ Нет доступа. Роль менеджера не назначена.")
        return

    creator_role_label = _role_label(is_admin(message.from_user.id, settings.get_admin_ids()))
    await state.clear()
    await state.set_state(OrderFlow.menu)
    form_message = await message.answer(
        _build_form_text(
            {"visible_fields": set(DEFAULT_VISIBLE_FIELDS)},
            "Выберите поле для заполнения:",
            creator_role_label,
        ),
        reply_markup=build_order_menu_keyboard({}),
    )
    await state.update_data(
        form_message_id=form_message.message_id,
        visible_fields=set(DEFAULT_VISIBLE_FIELDS),
        creator_role_label=creator_role_label,
    )


@router.callback_query(lambda c: c.data == "flow:cancel")
async def flow_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel constructor/photo flow."""
    await state.clear()
    if callback.message:
        await callback.message.edit_text("🛑 Сценарий отменен.")
    await callback.answer()


@router.callback_query(lambda c: c.data == "flow:back")
async def flow_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Back action inside constructor."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    await _show_main_menu(callback.message, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "form:menu")
async def form_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Explicit return to constructor main menu."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    await _show_main_menu(callback.message, state)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("form:edit:"))
async def form_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Open editor for selected field."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    field = callback.data.split(":", 2)[2]
    await state.update_data(input_field=field)

    if field == "city":
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Выберите город:", build_form_city_keyboard())
        await callback.answer()
        return
    if field == "date":
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Выберите дату:", build_form_date_keyboard())
        await callback.answer()
        return
    if field == "cleaning_type":
        await _edit_form_message(
            callback.bot,
            callback.message.chat.id,
            state,
            "Выберите тип уборки:",
            build_form_cleaning_type_keyboard(),
        )
        await callback.answer()
        return
    if field == "equipment":
        await _edit_form_message(
            callback.bot,
            callback.message.chat.id,
            state,
            "Выберите вариант оборудования:",
            build_form_equipment_keyboard(),
        )
        await callback.answer()
        return
    if field == "conditions":
        await _edit_form_message(
            callback.bot,
            callback.message.chat.id,
            state,
            "Выберите условия:",
            build_form_conditions_keyboard(),
        )
        await callback.answer()
        return
    if field == "visible":
        selected = set((await state.get_data()).get("visible_fields", set(DEFAULT_VISIBLE_FIELDS)))
        await state.set_state(OrderFlow.visible_fields)
        await _edit_form_message(
            callback.bot,
            callback.message.chat.id,
            state,
            "Отметьте поля, видимые мастеру:",
            build_visibility_keyboard(selected),
        )
        await callback.answer()
        return
    if field in TEXT_INPUT_FIELDS:
        await state.set_state(OrderFlow.input_text)
        prompts = {
            "date": "Введите дату в формате дд.мм.гггг:",
            "time": "Введите время (например 14:00):",
            "address": "Введите адрес:",
            "comment": "Введите комментарий (или '-' чтобы очистить):",
            "client_contact": "Введите контакт клиента:",
        }
        await _edit_form_message(callback.bot, callback.message.chat.id, state, prompts[field])
        await callback.answer()
        return

    await callback.answer("Поле не поддерживается.", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("formcity:"))
async def form_city_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Set city and return to menu."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    await state.update_data(city=callback.data.split(":", 1)[1])
    await _show_main_menu(callback.message, state, "Город сохранен. Выберите следующее поле:")
    await callback.answer("Город сохранен.")


@router.callback_query(lambda c: c.data and c.data.startswith("formdate:"))
async def form_date_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Set date quick value or switch to text input."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    value = callback.data.split(":", 1)[1]
    if value == "today":
        await state.update_data(date=_format_date(datetime.now()))
        await _show_main_menu(callback.message, state, "Дата сохранена. Выберите следующее поле:")
        await callback.answer("Дата сохранена.")
        return
    if value == "tomorrow":
        await state.update_data(date=_format_date(datetime.now() + timedelta(days=1)))
        await _show_main_menu(callback.message, state, "Дата сохранена. Выберите следующее поле:")
        await callback.answer("Дата сохранена.")
        return

    await state.update_data(input_field="date")
    await state.set_state(OrderFlow.input_text)
    await _edit_form_message(callback.bot, callback.message.chat.id, state, "Введите дату в формате дд.мм.гггг:")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("formtype:"))
async def form_type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Set cleaning type and return to menu."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    await state.update_data(cleaning_type=CLEANING_TYPES.get(key, key))
    await _show_main_menu(callback.message, state, "Тип уборки сохранен. Выберите следующее поле:")
    await callback.answer("Сохранено.")


@router.callback_query(lambda c: c.data and c.data.startswith("formequip:"))
async def form_equipment_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Set equipment and return to menu."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    await state.update_data(equipment=EQUIPMENT_OPTIONS.get(key, key))
    await _show_main_menu(callback.message, state, "Оборудование сохранено. Выберите следующее поле:")
    await callback.answer("Сохранено.")


@router.callback_query(lambda c: c.data and c.data.startswith("formcond:"))
async def form_conditions_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Set conditions and return to menu."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    await state.update_data(conditions=CONDITION_OPTIONS.get(key, key))
    await _show_main_menu(callback.message, state, "Условия сохранены. Выберите следующее поле:")
    await callback.answer("Сохранено.")


@router.message(OrderFlow.input_text)
async def form_text_input(message: Message, state: FSMContext) -> None:
    """Persist manual text field and return to menu."""
    data = await state.get_data()
    field = data.get("input_field")
    if field not in TEXT_INPUT_FIELDS:
        await _show_main_menu(message, state)
        return

    value = (message.text or "").strip()
    if field == "comment" and value == "-":
        value = ""
    await state.update_data({field: value})
    await _show_main_menu(message, state, "Параметр сохранен. Выберите следующее поле:")


@router.callback_query(lambda c: c.data and c.data.startswith("vis:toggle:"))
async def visibility_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    """Toggle visible field for master."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    key = callback.data.split(":", 2)[2]
    if key not in MASTER_VISIBLE_FIELD_LABELS:
        await callback.answer("Неизвестное поле.", show_alert=True)
        return

    data = await state.get_data()
    selected = set(data.get("visible_fields", set(DEFAULT_VISIBLE_FIELDS)))
    if key in selected:
        selected.remove(key)
    else:
        selected.add(key)
    await state.update_data(visible_fields=selected)
    await _edit_form_message(
        callback.bot,
        callback.message.chat.id,
        state,
        "Отметьте поля, видимые мастеру:",
        build_visibility_keyboard(selected),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "vis:done")
async def visibility_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Finish visibility setup and return to main menu."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return
    data = await state.get_data()
    selected = set(data.get("visible_fields", set(DEFAULT_VISIBLE_FIELDS)))
    if not selected:
        await callback.answer("Выберите хотя бы одно поле.", show_alert=True)
        return

    await _show_main_menu(callback.message, state, "Видимость сохранена. Выберите следующее поле:")
    await callback.answer("Сохранено.")


@router.callback_query(lambda c: c.data == "form:submit")
async def form_submit(callback: CallbackQuery, state: FSMContext, db) -> None:
    """Validate, persist and publish order."""
    if not callback.message:
        await callback.answer("Сообщение недоступно.", show_alert=True)
        return

    data = await state.get_data()
    missing = _missing_fields(data)
    if missing:
        await callback.answer("Не все поля заполнены.", show_alert=True)
        await _show_main_menu(
            callback.message,
            state,
            "Заполните обязательные поля: " + ", ".join(missing),
        )
        return

    order_payload = {
        "city": data.get("city", ""),
        "address": data.get("address", ""),
        "date": data.get("date", ""),
        "time": data.get("time", ""),
        "type": data.get("cleaning_type", ""),
        "equipment": data.get("equipment", ""),
        "conditions": data.get("conditions", ""),
        "comment": data.get("comment", ""),
        "client_contact": data.get("client_contact", ""),
        "manager_id": callback.from_user.id,
        "status": ORDER_STATUSES["published"],
        "manager_contact": str(callback.from_user.id),
    }

    try:
        order = await create_order(db, order_payload)
        selected_fields = set(data.get("visible_fields", set(DEFAULT_VISIBLE_FIELDS)))
        await set_master_visible_fields(db, order.id, selected_fields)
    except Exception as exc:
        logger.exception("Order create failed")
        await callback.answer("Ошибка сохранения заявки", show_alert=True)
        await callback.message.edit_text(f"❌ Ошибка сохранения заявки: {exc}")
        return

    brief = format_order_brief({**order_payload, "id": order.id})
    try:
        message = await send_to_city_topic(callback.bot, order.city, brief, order.id)
    except TelegramBadRequest as exc:
        logger.exception("Telegram publish failed")
        await callback.answer("Заявка сохранена, но не опубликована", show_alert=True)
        await callback.message.edit_text(
            f"⚠️ Заявка #{order.id} создана, но не опубликована.\nПричина Telegram: {exc.message}"
        )
        await state.clear()
        return
    except Exception as exc:
        logger.exception("Unexpected publish error")
        await callback.answer("Заявка сохранена, но не опубликована", show_alert=True)
        await callback.message.edit_text(
            f"⚠️ Заявка #{order.id} создана, но не опубликована.\nПричина: {exc}"
        )
        await state.clear()
        return

    if message:
        await callback.message.edit_text(f"✅ Заявка #{order.id} опубликована.")
    else:
        await callback.message.edit_text(
            f"⚠️ Заявка #{order.id} создана, но не опубликована.\nПроверьте GROUP_CHAT_ID и CITY_TOPIC_* в .env."
        )
    await callback.answer()
    await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("resp:"))
async def master_respond(callback: CallbackQuery, db) -> None:
    """Master responds from group message."""
    user = await ensure_user(db, callback.from_user.id, username=callback.from_user.username or "")
    if not has_role(user, ROLES["master"]):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(db, order_id)
    if not order:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if order.status not in (ORDER_STATUSES["published"], ORDER_STATUSES["created"]):
        await callback.answer("Заявка уже занята.", show_alert=True)
        return

    await register_response(db, order_id, callback.from_user.id)
    await assign_master(db, order, callback.from_user.id)
    visible_fields = await get_master_visible_fields(db, order.id)
    full_text = _build_master_text(order, visible_fields)

    contact = format_manager_contact(order.manager_id)
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=f"✅ Вы откликнулись на заявку.\n\n{full_text}\n{contact}",
        reply_markup=build_master_accept_keyboard(order.id),
    )
    await _notify_manager(
        callback.bot,
        order.manager_id,
        f"🔔 Роль собеседника: мастер. По заявке #{order.id} есть отклик от {format_user_link(callback.from_user.id)}.",
    )
    await callback.answer("Отклик принят ✅")


@router.callback_query(lambda c: c.data and c.data.startswith("accept:"))
async def master_accept(callback: CallbackQuery, db) -> None:
    """Master confirms order."""
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(db, order_id)
    if not order or order.master_id != callback.from_user.id:
        await callback.answer("Заявка не найдена или недоступна.", show_alert=True)
        return

    await set_status(db, order, ORDER_STATUSES["in_progress"])
    await callback.message.edit_text(
        f"🧰 Заявка #{order.id} в работе.\n"
        f"Загрузите фото ДО и ПОСЛЕ: от {MIN_PHOTOS_PER_TYPE} до {MAX_PHOTOS_PER_TYPE} каждого типа.",
        reply_markup=build_photo_actions_keyboard(order.id),
    )
    await _notify_manager(
        callback.bot,
        order.manager_id,
        f"✅ Роль собеседника: мастер. {format_user_link(callback.from_user.id)} подтвердил заявку #{order.id}.",
    )


@router.callback_query(lambda c: c.data and c.data.startswith("decline:"))
async def master_decline(callback: CallbackQuery, db) -> None:
    """Master declines order."""
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(db, order_id)
    if not order or order.master_id != callback.from_user.id:
        await callback.answer("Заявка не найдена или недоступна.", show_alert=True)
        return

    await unassign_master(db, order)
    await callback.message.edit_text("↩️ Вы отказались от заявки. Она снова доступна.")
    await _notify_manager(
        callback.bot,
        order.manager_id,
        f"↩️ Роль собеседника: мастер. {format_user_link(callback.from_user.id)} отказался от заявки #{order.id}.",
    )


@router.callback_query(lambda c: c.data and c.data.startswith("photo_before:"))
async def photo_before(callback: CallbackQuery, state: FSMContext, db) -> None:
    """Request before photos."""
    order_id = int(callback.data.split(":", 1)[1])
    current = await get_order_photo_type_count(db, order_id, "before")
    await state.set_state(PhotoFlow.waiting_photo)
    await state.update_data(order_id=order_id, photo_type="before")
    await callback.message.answer(
        f"📸 Роль собеседника: мастер.\nФото ДО: {current}/{MAX_PHOTOS_PER_TYPE}. "
        f"Нужно минимум {MIN_PHOTOS_PER_TYPE}."
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("photo_after:"))
async def photo_after(callback: CallbackQuery, state: FSMContext, db) -> None:
    """Request after photos."""
    order_id = int(callback.data.split(":", 1)[1])
    current = await get_order_photo_type_count(db, order_id, "after")
    await state.set_state(PhotoFlow.waiting_photo)
    await state.update_data(order_id=order_id, photo_type="after")
    await callback.message.answer(
        f"📸 Роль собеседника: мастер.\nФото ПОСЛЕ: {current}/{MAX_PHOTOS_PER_TYPE}. "
        f"Нужно минимум {MIN_PHOTOS_PER_TYPE}."
    )
    await callback.answer()


@router.message(PhotoFlow.waiting_photo)
async def receive_photo(message: Message, state: FSMContext, db) -> None:
    """Store photo file_id in DB with per-type limits."""
    if not message.photo:
        await message.answer("⚠️ Нужно отправить фото.")
        return

    data = await state.get_data()
    order_id = int(data.get("order_id"))
    photo_type = str(data.get("photo_type") or "")
    if photo_type not in {"before", "after"}:
        await message.answer("⚠️ Не выбран тип фото (ДО/ПОСЛЕ).")
        return

    order = await get_order(db, order_id)
    if not order or order.master_id != message.from_user.id:
        await message.answer("⛔ Нельзя прикрепить фото к этой заявке.")
        return

    current_count = await get_order_photo_type_count(db, order_id, photo_type)
    if current_count >= MAX_PHOTOS_PER_TYPE:
        await message.answer(
            f"⚠️ Для типа {'ДО' if photo_type == 'before' else 'ПОСЛЕ'} уже загружено {MAX_PHOTOS_PER_TYPE} фото."
        )
        return

    file_id = message.photo[-1].file_id
    await add_photo(db, order_id, file_id, photo_type)
    new_count = current_count + 1
    need_left = max(0, MIN_PHOTOS_PER_TYPE - new_count)
    if need_left > 0:
        await message.answer(
            f"✅ Фото сохранено ({new_count}/{MAX_PHOTOS_PER_TYPE}) для типа "
            f"{'ДО' if photo_type == 'before' else 'ПОСЛЕ'}. Еще минимум {need_left}."
        )
    else:
        await message.answer(
            f"✅ Фото сохранено ({new_count}/{MAX_PHOTOS_PER_TYPE}) для типа "
            f"{'ДО' if photo_type == 'before' else 'ПОСЛЕ'}. Минимум выполнен."
        )


@router.callback_query(lambda c: c.data and c.data.startswith("finish:"))
async def finish_order(callback: CallbackQuery, db) -> None:
    """Finalize order only with 3-5 before and after photos."""
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(db, order_id)
    if not order or order.master_id != callback.from_user.id:
        await callback.answer("Заявка не найдена или недоступна.", show_alert=True)
        return

    photo_counts = await get_order_photo_counts(db, order.id)
    before_count = photo_counts["before"]
    after_count = photo_counts["after"]
    if before_count < MIN_PHOTOS_PER_TYPE or after_count < MIN_PHOTOS_PER_TYPE:
        await callback.answer(
            f"Нужно минимум {MIN_PHOTOS_PER_TYPE} фото ДО и {MIN_PHOTOS_PER_TYPE} ПОСЛЕ.",
            show_alert=True,
        )
        return

    await set_status(db, order, ORDER_STATUSES["completed"])
    await callback.message.edit_text(
        f"✅ Заявка #{order.id} завершена.\nФото ДО: {before_count}, ПОСЛЕ: {after_count}."
    )
    await _notify_manager(
        callback.bot,
        order.manager_id,
        (
            f"🏁 Роль собеседника: мастер. Заявка #{order.id} завершена "
            f"{format_user_link(callback.from_user.id)}.\nФото: ДО={before_count}, ПОСЛЕ={after_count}."
        ),
    )
    await callback.answer()

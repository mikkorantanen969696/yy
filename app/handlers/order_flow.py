"""
Order creation and state machine implementation.
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
    create_order,
    get_order,
    assign_master,
    unassign_master,
    set_status,
    register_response,
    add_photo,
)
from app.services.telegram import send_to_city_topic
from app.services.users import ensure_user, has_role, is_admin
from app.utils.constants import (
    ROLES,
    ORDER_STATUSES,
    CITY_CHOICES,
    CLEANING_TYPES,
    EQUIPMENT_OPTIONS,
    CONDITION_OPTIONS,
)
from app.utils.keyboards import (
    build_city_keyboard,
    build_date_keyboard,
    build_cleaning_type_keyboard,
    build_equipment_keyboard,
    build_conditions_keyboard,
    build_confirm_keyboard,
    build_skip_keyboard,
    build_master_accept_keyboard,
    build_photo_actions_keyboard,
)
from app.utils.text import format_order_brief, format_order_full, format_manager_contact

router = Router()
logger = logging.getLogger(__name__)


class OrderFlow(StatesGroup):
    """FSM states for manager order creation."""

    city = State()
    date = State()
    time = State()
    address = State()
    cleaning_type = State()
    equipment = State()
    conditions = State()
    comment = State()
    client_contact = State()
    confirm = State()


class PhotoFlow(StatesGroup):
    """FSM for photo upload by master."""

    waiting_photo = State()


def _format_date(date_obj: datetime) -> str:
    """Format date as dd.mm.yyyy string."""
    return date_obj.strftime("%d.%m.%Y")


def _build_form_text(data: dict, prompt: str) -> str:
    """Build a single editable order form message with current values."""
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

    return (
        "Создание заявки\n\n"
        f"Город: {city_value}\n"
        f"Дата: {date_value}\n"
        f"Время: {time_value}\n"
        f"Адрес: {address_value}\n"
        f"Тип уборки: {type_value}\n"
        f"Оборудование: {equipment_value}\n"
        f"Условия: {conditions_value}\n"
        f"Комментарий: {comment_value}\n"
        f"Контакт клиента: {client_contact_value}\n\n"
        f"{prompt}"
    )


async def _edit_form_message(
    bot,
    chat_id: int,
    state: FSMContext,
    prompt: str,
    reply_markup=None,
) -> None:
    """Edit one persistent message used for the whole order flow."""
    data = await state.get_data()
    form_message_id = data.get("form_message_id")
    if not form_message_id:
        return

    text = _build_form_text(data, prompt)
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
    """Verify manager role or admin."""
    user = await ensure_user(db, message.from_user.id)
    return has_role(user, ROLES["manager"]) or is_admin(message.from_user.id, settings.get_admin_ids())


@router.message(Command("new_order"))
async def start_order_flow(message: Message, state: FSMContext, db) -> None:
    """Begin order creation flow for managers."""
    if not await _ensure_manager(message, db):
        await message.answer("Нет доступа. Роль менеджера не назначена.")
        return
    await state.clear()
    await state.set_state(OrderFlow.city)
    form_message = await message.answer(
        _build_form_text({}, "Выберите город:"),
        reply_markup=build_city_keyboard(),
    )
    await state.update_data(form_message_id=form_message.message_id)


@router.callback_query(lambda c: c.data == "flow:cancel")
async def flow_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel any active flow."""
    await state.clear()
    await callback.message.edit_text("Сценарий отменен.")


@router.callback_query(lambda c: c.data == "flow:back")
async def flow_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle back navigation by inspecting current state."""
    current = await state.get_state()

    if current == OrderFlow.date.state:
        await state.set_state(OrderFlow.city)
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Выберите город:", build_city_keyboard())
        return
    if current == OrderFlow.time.state:
        await state.set_state(OrderFlow.date)
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Выберите дату:", build_date_keyboard())
        return
    if current == OrderFlow.address.state:
        await state.set_state(OrderFlow.time)
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Введите время (например 14:00):")
        return
    if current == OrderFlow.cleaning_type.state:
        await state.set_state(OrderFlow.address)
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Введите адрес:")
        return
    if current == OrderFlow.equipment.state:
        await state.set_state(OrderFlow.cleaning_type)
        await _edit_form_message(
            callback.bot,
            callback.message.chat.id,
            state,
            "Выберите тип уборки:",
            build_cleaning_type_keyboard(),
        )
        return
    if current == OrderFlow.conditions.state:
        await state.set_state(OrderFlow.equipment)
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Оборудование:", build_equipment_keyboard())
        return
    if current == OrderFlow.comment.state:
        await state.set_state(OrderFlow.conditions)
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Условия:", build_conditions_keyboard())
        return
    if current == OrderFlow.client_contact.state:
        await state.set_state(OrderFlow.comment)
        await _edit_form_message(
            callback.bot,
            callback.message.chat.id,
            state,
            "Комментарий (можно пропустить):",
            build_skip_keyboard(),
        )
        return
    if current == OrderFlow.confirm.state:
        await state.set_state(OrderFlow.client_contact)
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Контакт клиента (только для менеджера/владельца):")
        return

    await _edit_form_message(callback.bot, callback.message.chat.id, state, "Нечего откатывать.")


@router.callback_query(lambda c: c.data.startswith("city:"))
async def city_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Store city and move to date selection."""
    city_key = callback.data.split(":", 1)[1]
    await state.update_data(city=city_key)
    await state.set_state(OrderFlow.date)
    await _edit_form_message(callback.bot, callback.message.chat.id, state, "Выберите дату:", build_date_keyboard())


@router.callback_query(lambda c: c.data.startswith("date:"))
async def date_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle quick date selection."""
    data = callback.data.split(":", 1)[1]

    if data == "today":
        date_value = _format_date(datetime.now())
    elif data == "tomorrow":
        date_value = _format_date(datetime.now() + timedelta(days=1))
    else:
        await _edit_form_message(callback.bot, callback.message.chat.id, state, "Введите дату (дд.мм.гггг):")
        await state.set_state(OrderFlow.date)
        await state.update_data(date_manual=True)
        return

    await state.update_data(date=date_value)
    await state.set_state(OrderFlow.time)
    await _edit_form_message(callback.bot, callback.message.chat.id, state, "Введите время (например 14:00):")


@router.message(OrderFlow.date)
async def date_manual(message: Message, state: FSMContext) -> None:
    """Manual date entry."""
    text = message.text.strip()
    await state.update_data(date=text)
    await state.set_state(OrderFlow.time)
    await _edit_form_message(message.bot, message.chat.id, state, "Введите время (например 14:00):")


@router.message(OrderFlow.time)
async def time_entered(message: Message, state: FSMContext) -> None:
    """Store time and ask for address."""
    await state.update_data(time=message.text.strip())
    await state.set_state(OrderFlow.address)
    await _edit_form_message(message.bot, message.chat.id, state, "Введите адрес:")


@router.message(OrderFlow.address)
async def address_entered(message: Message, state: FSMContext) -> None:
    """Store address and ask for cleaning type."""
    await state.update_data(address=message.text.strip())
    await state.set_state(OrderFlow.cleaning_type)
    await _edit_form_message(
        message.bot,
        message.chat.id,
        state,
        "Выберите тип уборки:",
        build_cleaning_type_keyboard(),
    )


@router.callback_query(lambda c: c.data.startswith("type:"))
async def type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Store cleaning type and ask for equipment."""
    type_key = callback.data.split(":", 1)[1]
    await state.update_data(cleaning_type=CLEANING_TYPES.get(type_key, type_key))
    await state.set_state(OrderFlow.equipment)
    await _edit_form_message(callback.bot, callback.message.chat.id, state, "Оборудование:", build_equipment_keyboard())


@router.callback_query(lambda c: c.data.startswith("equip:"))
async def equipment_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Store equipment choice and ask for conditions."""
    equip_key = callback.data.split(":", 1)[1]
    await state.update_data(equipment=EQUIPMENT_OPTIONS.get(equip_key, equip_key))
    await state.set_state(OrderFlow.conditions)
    await _edit_form_message(callback.bot, callback.message.chat.id, state, "Условия:", build_conditions_keyboard())


@router.callback_query(lambda c: c.data.startswith("cond:"))
async def conditions_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Store conditions and ask for comment."""
    cond_key = callback.data.split(":", 1)[1]
    await state.update_data(conditions=CONDITION_OPTIONS.get(cond_key, cond_key))
    await state.set_state(OrderFlow.comment)
    await _edit_form_message(
        callback.bot,
        callback.message.chat.id,
        state,
        "Комментарий (можно пропустить):",
        build_skip_keyboard(),
    )


@router.callback_query(lambda c: c.data == "flow:skip")
async def comment_skipped(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip optional comment."""
    await state.update_data(comment="")
    await state.set_state(OrderFlow.client_contact)
    await _edit_form_message(callback.bot, callback.message.chat.id, state, "Контакт клиента (только для менеджера/владельца):")


@router.message(OrderFlow.comment)
async def comment_entered(message: Message, state: FSMContext) -> None:
    """Store comment and ask for client contact."""
    await state.update_data(comment=message.text.strip())
    await state.set_state(OrderFlow.client_contact)
    await _edit_form_message(message.bot, message.chat.id, state, "Контакт клиента (только для менеджера/владельца):")


@router.message(OrderFlow.client_contact)
async def client_contact_entered(message: Message, state: FSMContext) -> None:
    """Store client contact and show confirm summary."""
    await state.update_data(client_contact=message.text.strip())
    await state.set_state(OrderFlow.confirm)
    await _edit_form_message(message.bot, message.chat.id, state, "Проверьте заявку и нажмите «Подтвердить».", build_confirm_keyboard())


@router.callback_query(lambda c: c.data == "flow:confirm")
async def confirm_order(callback: CallbackQuery, state: FSMContext, db) -> None:
    """Persist order and publish to Telegram group topic."""
    data = await state.get_data()
    manager_id = callback.from_user.id

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
        "manager_id": manager_id,
        "status": ORDER_STATUSES["published"],
        "manager_contact": str(manager_id),
    }

    try:
        order = await create_order(db, order_payload)
    except Exception as exc:
        logger.exception("Order create failed")
        await callback.answer("Ошибка сохранения заявки", show_alert=True)
        await callback.message.edit_text(f"Ошибка сохранения заявки: {exc}")
        return

    brief = format_order_brief({**order_payload, "id": order.id})
    try:
        message = await send_to_city_topic(callback.bot, order.city, brief, order.id)
    except TelegramBadRequest as exc:
        logger.exception("Telegram publish failed")
        await callback.answer("Заявка сохранена, но не опубликована", show_alert=True)
        await callback.message.edit_text(
            f"Заявка #{order.id} создана, но не опубликована.\n"
            f"Причина Telegram: {exc.message}"
        )
        await state.clear()
        return
    except Exception as exc:
        logger.exception("Unexpected publish error")
        await callback.answer("Заявка сохранена, но не опубликована", show_alert=True)
        await callback.message.edit_text(
            f"Заявка #{order.id} создана, но не опубликована.\n"
            f"Причина: {exc}"
        )
        await state.clear()
        return

    if message:
        await callback.message.edit_text(f"Заявка #{order.id} опубликована.")
    else:
        await callback.message.edit_text(
            f"Заявка #{order.id} создана, но не опубликована.\n"
            "Проверьте GROUP_CHAT_ID и CITY_TOPIC_* в .env."
        )

    await state.clear()


@router.callback_query(lambda c: c.data.startswith("resp:"))
async def master_respond(callback: CallbackQuery, db) -> None:
    """Master responds from group message."""
    user = await ensure_user(db, callback.from_user.id)
    if not has_role(user, ROLES["master"]):
        await callback.answer("Нет доступа.", show_alert=True)
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

    full_text = format_order_full(
        {
            "id": order.id,
            "city": order.city,
            "date": order.date,
            "time": order.time,
            "address": order.address,
            "type": order.type,
            "equipment": order.equipment,
            "conditions": order.conditions,
            "comment": order.comment,
        }
    )

    contact = format_manager_contact(order.manager_id)
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=f"Вы откликнулись.\n\n{full_text}\n{contact}",
        reply_markup=build_master_accept_keyboard(order.id),
    )

    await callback.answer("Отклик принят.")


@router.callback_query(lambda c: c.data.startswith("accept:"))
async def master_accept(callback: CallbackQuery, db) -> None:
    """Master confirms order."""
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(db, order_id)
    if not order or order.master_id != callback.from_user.id:
        await callback.answer("Заявка не найдена или недоступна.", show_alert=True)
        return

    await set_status(db, order, ORDER_STATUSES["in_progress"])
    await callback.message.edit_text(
        f"Заявка #{order.id} в работе.\n"
        "Загрузите фото ДО и ПОСЛЕ.",
        reply_markup=build_photo_actions_keyboard(order.id),
    )


@router.callback_query(lambda c: c.data.startswith("decline:"))
async def master_decline(callback: CallbackQuery, db) -> None:
    """Master declines order."""
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(db, order_id)
    if not order or order.master_id != callback.from_user.id:
        await callback.answer("Заявка не найдена или недоступна.", show_alert=True)
        return

    await unassign_master(db, order)
    await callback.message.edit_text("Вы отказались от заявки. Она снова доступна.")


@router.callback_query(lambda c: c.data.startswith("photo_before:"))
async def photo_before(callback: CallbackQuery, state: FSMContext) -> None:
    """Request before photos."""
    order_id = int(callback.data.split(":", 1)[1])
    await state.set_state(PhotoFlow.waiting_photo)
    await state.update_data(order_id=order_id, photo_type="before")
    await callback.message.answer("Отправьте фото ДО (минимум 1).")


@router.callback_query(lambda c: c.data.startswith("photo_after:"))
async def photo_after(callback: CallbackQuery, state: FSMContext) -> None:
    """Request after photos."""
    order_id = int(callback.data.split(":", 1)[1])
    await state.set_state(PhotoFlow.waiting_photo)
    await state.update_data(order_id=order_id, photo_type="after")
    await callback.message.answer("Отправьте фото ПОСЛЕ (минимум 1).")


@router.message(PhotoFlow.waiting_photo)
async def receive_photo(message: Message, state: FSMContext, db) -> None:
    """Store photo file_id in DB."""
    if not message.photo:
        await message.answer("Нужно отправить фото.")
        return

    data = await state.get_data()
    order_id = int(data.get("order_id"))
    photo_type = data.get("photo_type")
    file_id = message.photo[-1].file_id

    await add_photo(db, order_id, file_id, photo_type)
    await message.answer("Фото сохранено.")


@router.callback_query(lambda c: c.data.startswith("finish:"))
async def finish_order(callback: CallbackQuery, db) -> None:
    """Finalize order after photos."""
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(db, order_id)
    if not order or order.master_id != callback.from_user.id:
        await callback.answer("Заявка не найдена или недоступна.", show_alert=True)
        return

    await set_status(db, order, ORDER_STATUSES["completed"])
    await callback.message.edit_text(f"Заявка #{order.id} завершена.")

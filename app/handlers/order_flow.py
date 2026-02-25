"""
Order creation and state machine implementation.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Router
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
    await message.answer("Выберите город:", reply_markup=build_city_keyboard())


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
        await callback.message.edit_text("Выберите город:", reply_markup=build_city_keyboard())
        return
    if current == OrderFlow.time.state:
        await state.set_state(OrderFlow.date)
        await callback.message.edit_text("Выберите дату:", reply_markup=build_date_keyboard())
        return
    if current == OrderFlow.address.state:
        await state.set_state(OrderFlow.time)
        await callback.message.edit_text("Введите время (например 14:00):")
        return
    if current == OrderFlow.cleaning_type.state:
        await state.set_state(OrderFlow.address)
        await callback.message.edit_text("Введите адрес:")
        return
    if current == OrderFlow.equipment.state:
        await state.set_state(OrderFlow.cleaning_type)
        await callback.message.edit_text("Выберите тип уборки:", reply_markup=build_cleaning_type_keyboard())
        return
    if current == OrderFlow.conditions.state:
        await state.set_state(OrderFlow.equipment)
        await callback.message.edit_text("Оборудование:", reply_markup=build_equipment_keyboard())
        return
    if current == OrderFlow.comment.state:
        await state.set_state(OrderFlow.conditions)
        await callback.message.edit_text("Условия:", reply_markup=build_conditions_keyboard())
        return
    if current == OrderFlow.client_contact.state:
        await state.set_state(OrderFlow.comment)
        await callback.message.edit_text("Комментарий (можно пропустить):", reply_markup=build_skip_keyboard())
        return
    if current == OrderFlow.confirm.state:
        await state.set_state(OrderFlow.client_contact)
        await callback.message.edit_text("Контакт клиента (только для менеджера/владельца):")
        return

    await callback.message.edit_text("Нечего откатывать.")


@router.callback_query(lambda c: c.data.startswith("city:"))
async def city_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Store city and move to date selection."""
    city_key = callback.data.split(":", 1)[1]
    await state.update_data(city=city_key)
    await state.set_state(OrderFlow.date)
    await callback.message.edit_text("Выберите дату:", reply_markup=build_date_keyboard())


@router.callback_query(lambda c: c.data.startswith("date:"))
async def date_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle quick date selection."""
    data = callback.data.split(":", 1)[1]

    if data == "today":
        date_value = _format_date(datetime.now())
    elif data == "tomorrow":
        date_value = _format_date(datetime.now() + timedelta(days=1))
    else:
        await callback.message.edit_text("Введите дату (дд.мм.гггг):")
        await state.set_state(OrderFlow.date)
        await state.update_data(date_manual=True)
        return

    await state.update_data(date=date_value)
    await state.set_state(OrderFlow.time)
    await callback.message.edit_text("Введите время (например 14:00):")


@router.message(OrderFlow.date)
async def date_manual(message: Message, state: FSMContext) -> None:
    """Manual date entry."""
    text = message.text.strip()
    await state.update_data(date=text)
    await state.set_state(OrderFlow.time)
    await message.answer("Введите время (например 14:00):")


@router.message(OrderFlow.time)
async def time_entered(message: Message, state: FSMContext) -> None:
    """Store time and ask for address."""
    await state.update_data(time=message.text.strip())
    await state.set_state(OrderFlow.address)
    await message.answer("Введите адрес:")


@router.message(OrderFlow.address)
async def address_entered(message: Message, state: FSMContext) -> None:
    """Store address and ask for cleaning type."""
    await state.update_data(address=message.text.strip())
    await state.set_state(OrderFlow.cleaning_type)
    await message.answer("Выберите тип уборки:", reply_markup=build_cleaning_type_keyboard())


@router.callback_query(lambda c: c.data.startswith("type:"))
async def type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Store cleaning type and ask for equipment."""
    type_key = callback.data.split(":", 1)[1]
    await state.update_data(cleaning_type=CLEANING_TYPES.get(type_key, type_key))
    await state.set_state(OrderFlow.equipment)
    await callback.message.edit_text("Оборудование:", reply_markup=build_equipment_keyboard())


@router.callback_query(lambda c: c.data.startswith("equip:"))
async def equipment_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Store equipment choice and ask for conditions."""
    equip_key = callback.data.split(":", 1)[1]
    await state.update_data(equipment=EQUIPMENT_OPTIONS.get(equip_key, equip_key))
    await state.set_state(OrderFlow.conditions)
    await callback.message.edit_text("Условия:", reply_markup=build_conditions_keyboard())


@router.callback_query(lambda c: c.data.startswith("cond:"))
async def conditions_selected(callback: CallbackQuery, state: FSMContext) -> None:
    """Store conditions and ask for comment."""
    cond_key = callback.data.split(":", 1)[1]
    await state.update_data(conditions=CONDITION_OPTIONS.get(cond_key, cond_key))
    await state.set_state(OrderFlow.comment)
    await callback.message.edit_text("Комментарий (можно пропустить):", reply_markup=build_skip_keyboard())


@router.callback_query(lambda c: c.data == "flow:skip")
async def comment_skipped(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip optional comment."""
    await state.update_data(comment="")
    await state.set_state(OrderFlow.client_contact)
    await callback.message.edit_text("Контакт клиента (только для менеджера/владельца):")


@router.message(OrderFlow.comment)
async def comment_entered(message: Message, state: FSMContext) -> None:
    """Store comment and ask for client contact."""
    await state.update_data(comment=message.text.strip())
    await state.set_state(OrderFlow.client_contact)
    await message.answer("Контакт клиента (только для менеджера/владельца):")


@router.message(OrderFlow.client_contact)
async def client_contact_entered(message: Message, state: FSMContext) -> None:
    """Store client contact and show confirm summary."""
    await state.update_data(client_contact=message.text.strip())
    data = await state.get_data()

    summary = (
        f"Проверьте заявку:\n"
        f"Город: {CITY_CHOICES.get(data.get('city', ''), data.get('city', ''))}\n"
        f"Дата: {data.get('date', '')} {data.get('time', '')}\n"
        f"Адрес: {data.get('address', '')}\n"
        f"Тип: {data.get('cleaning_type', '')}\n"
        f"Оборудование: {data.get('equipment', '')}\n"
        f"Условия: {data.get('conditions', '')}\n"
        f"Комментарий: {data.get('comment', '') or '-'}\n"
        f"Контакт клиента: {data.get('client_contact', '')}\n"
    )

    await state.set_state(OrderFlow.confirm)
    await message.answer(summary, reply_markup=build_confirm_keyboard())


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

    order = await create_order(db, order_payload)

    brief = format_order_brief({**order_payload, "id": order.id})
    message = await send_to_city_topic(callback.bot, order.city, brief, order.id)

    if message:
        await callback.message.edit_text(f"Заявка #{order.id} опубликована.")
    else:
        await callback.message.edit_text(f"Заявка #{order.id} создана, но не опубликована.")

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

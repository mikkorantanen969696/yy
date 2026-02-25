"""
Keyboard builders for inline interactions.

Keep all button layouts here to avoid duplication in handlers.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.constants import (
    CITY_CHOICES,
    CLEANING_TYPES,
    EQUIPMENT_OPTIONS,
    CONDITION_OPTIONS,
)


def build_city_keyboard() -> InlineKeyboardMarkup:
    """Choose city topic for order publishing."""
    builder = InlineKeyboardBuilder()
    for key, label in CITY_CHOICES.items():
        builder.add(InlineKeyboardButton(text=label, callback_data=f"city:{key}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="flow:cancel"))
    return builder.as_markup()


def build_date_keyboard() -> InlineKeyboardMarkup:
    """Quick date selection buttons."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Сегодня", callback_data="date:today"))
    builder.add(InlineKeyboardButton(text="Завтра", callback_data="date:tomorrow"))
    builder.add(InlineKeyboardButton(text="Ввести вручную", callback_data="date:manual"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Назад", callback_data="flow:back"))
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="flow:cancel"))
    return builder.as_markup()


def build_cleaning_type_keyboard() -> InlineKeyboardMarkup:
    """Select cleaning type."""
    builder = InlineKeyboardBuilder()
    for key, label in CLEANING_TYPES.items():
        builder.add(InlineKeyboardButton(text=label, callback_data=f"type:{key}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Назад", callback_data="flow:back"))
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="flow:cancel"))
    return builder.as_markup()


def build_equipment_keyboard() -> InlineKeyboardMarkup:
    """Select equipment availability."""
    builder = InlineKeyboardBuilder()
    for key, label in EQUIPMENT_OPTIONS.items():
        builder.add(InlineKeyboardButton(text=label, callback_data=f"equip:{key}"))
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="Назад", callback_data="flow:back"))
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="flow:cancel"))
    return builder.as_markup()


def build_conditions_keyboard() -> InlineKeyboardMarkup:
    """Select conditions for master payment."""
    builder = InlineKeyboardBuilder()
    for key, label in CONDITION_OPTIONS.items():
        builder.add(InlineKeyboardButton(text=label, callback_data=f"cond:{key}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Назад", callback_data="flow:back"))
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="flow:cancel"))
    return builder.as_markup()


def build_confirm_keyboard() -> InlineKeyboardMarkup:
    """Final confirm buttons."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Подтвердить", callback_data="flow:confirm"))
    builder.add(InlineKeyboardButton(text="Назад", callback_data="flow:back"))
    builder.add(InlineKeyboardButton(text="Отмена", callback_data="flow:cancel"))
    builder.adjust(2)
    return builder.as_markup()


def build_skip_keyboard() -> InlineKeyboardMarkup:
    """Skip optional field and go next."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Пропустить", callback_data="flow:skip"))
    builder.add(InlineKeyboardButton(text="Назад", callback_data="flow:back"))
    builder.add(InlineKeyboardButton(text="Отмена", callback_data="flow:cancel"))
    builder.adjust(2)
    return builder.as_markup()


def build_group_response_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Button for masters to respond in group."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Откликнуться", callback_data=f"resp:{order_id}"))
    return builder.as_markup()


def build_master_accept_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Buttons in master DM to accept or decline order."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Принять", callback_data=f"accept:{order_id}"))
    builder.add(InlineKeyboardButton(text="Отказаться", callback_data=f"decline:{order_id}"))
    builder.adjust(2)
    return builder.as_markup()


def build_photo_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Buttons for photo workflow in master DM."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Загрузить фото ДО", callback_data=f"photo_before:{order_id}"))
    builder.add(InlineKeyboardButton(text="Загрузить фото ПОСЛЕ", callback_data=f"photo_after:{order_id}"))
    builder.add(InlineKeyboardButton(text="Завершить заказ", callback_data=f"finish:{order_id}"))
    builder.adjust(1)
    return builder.as_markup()

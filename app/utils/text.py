"""
Text formatting utilities.
"""
from __future__ import annotations

from app.utils.constants import CITY_CHOICES
from app.services.users import normalize_username


def format_username(username: str | None) -> str:
    """Format username for UI."""
    normalized = normalize_username(username or "")
    return f"@{normalized}" if normalized else "-"


def format_user_link(telegram_id: int | None, label: str | None = None, username: str | None = None) -> str:
    """
    Build clickable user link in HTML parse mode.

    Preferred format is @username. Falls back to tg://user?id when only id exists.
    """
    normalized = normalize_username(username or "")
    if normalized:
        text = label or f"@{normalized}"
        return f'<a href="https://t.me/{normalized}">{text}</a>'
    if not telegram_id:
        return "-"
    text = label or "пользователь"
    return f'<a href="tg://user?id={int(telegram_id)}">{text}</a>'


def format_order_brief(data: dict) -> str:
    """Create a short order text for group publishing."""
    city_key = data.get("city", "")
    city_label = CITY_CHOICES.get(city_key, city_key)
    return (
        f"Заявка #{data.get('id', '')}\n"
        f"Город: {city_label}\n"
        f"Дата: {data.get('date', '')} {data.get('time', '')}\n"
        f"Тип: {data.get('type', '')}\n"
        f"Оборудование: {data.get('equipment', '')}\n"
        f"Комментарий: {data.get('comment', '') or '-'}\n"
    )


def format_order_full(data: dict) -> str:
    """Full order text for master DM."""
    city_key = data.get("city", "")
    city_label = CITY_CHOICES.get(city_key, city_key)
    return (
        f"Заявка #{data.get('id', '')}\n"
        f"Город: {city_label}\n"
        f"Дата: {data.get('date', '')} {data.get('time', '')}\n"
        f"Адрес: {data.get('address', '')}\n"
        f"Тип: {data.get('type', '')}\n"
        f"Оборудование: {data.get('equipment', '')}\n"
        f"Условия: {data.get('conditions', '')}\n"
        f"Комментарий: {data.get('comment', '') or '-'}\n"
    )


def format_manager_contact(manager_telegram_id: int | None, manager_username: str | None = None) -> str:
    """Basic manager contact string."""
    return f"Контакт менеджера: {format_user_link(manager_telegram_id, 'написать менеджеру', manager_username)}"

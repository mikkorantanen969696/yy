"""
Telegram-specific helpers for sending to group topics.
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message

from app.config.settings import settings
from app.utils.keyboards import build_group_response_keyboard


async def send_to_city_topic(bot: Bot, city_key: str, text: str, order_id: int) -> Message | None:
    """Send a message to the correct topic thread for the city."""
    thread_id = settings.city_topics().get(city_key)
    if not thread_id or not settings.group_chat_id:
        return None

    return await bot.send_message(
        chat_id=settings.group_chat_id,
        message_thread_id=thread_id,
        text=text,
        reply_markup=build_group_response_keyboard(order_id),
    )

"""
Main entrypoint for the bot.

Supports polling for local dev and webhook for production.
"""
from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.bot.dispatcher import create_dispatcher
from app.config.settings import settings
from app.db.init import init_db
from app.middlewares.db import DbSessionMiddleware


async def on_startup(bot: Bot) -> None:
    """Initialize DB and configure webhook if needed."""
    await init_db()

    if settings.run_mode == "webhook":
        webhook_url = settings.get_webhook_url()
        if not webhook_url:
            raise RuntimeError("WEBHOOK_URL is required in webhook mode")
        # Set webhook to point to your public server endpoint.
        await bot.set_webhook(webhook_url)


async def on_shutdown(bot: Bot) -> None:
    """Cleanup hook for webhook mode."""
    if settings.run_mode == "webhook":
        await bot.delete_webhook(drop_pending_updates=True)


async def run_polling() -> None:
    """Run the bot in long-polling mode (local development)."""
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher()

    # Middleware should be applied to all update types.
    dp.update.middleware(DbSessionMiddleware())

    await on_startup(bot)
    await dp.start_polling(bot)
    await on_shutdown(bot)


async def run_webhook() -> None:
    """Run the bot in webhook mode (production)."""
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher()
    dp.update.middleware(DbSessionMiddleware())

    await on_startup(bot)

    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    # Serve on configurable host/port.
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.app_host, settings.app_port)
    await site.start()

    # Keep the process alive.
    while True:
        await asyncio.sleep(3600)


def main() -> Any:
    """Entrypoint invoked by python -m app.main."""
    if settings.run_mode == "webhook":
        return asyncio.run(run_webhook())
    return asyncio.run(run_polling())


if __name__ == "__main__":
    main()

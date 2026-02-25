"""
Dispatcher factory and router registration.

Keep bot wiring here to avoid circular imports in handlers.
"""
from __future__ import annotations

from aiogram import Dispatcher

from app.handlers import admin, common, manager, master, order_flow


def create_dispatcher() -> Dispatcher:
    """Create and register routers for the bot."""
    dp = Dispatcher()

    # Register routers in a predictable order.
    dp.include_router(common.router)
    dp.include_router(manager.router)
    dp.include_router(master.router)
    dp.include_router(order_flow.router)
    dp.include_router(admin.router)

    return dp

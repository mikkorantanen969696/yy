"""
Basic commands available to all roles.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from app.config.settings import settings
from app.services.users import ensure_user, is_admin
from app.utils.constants import ROLES

router = Router()

HELP_TEXT = (
    "📘 Подробная инструкция по работе с ботом\n\n"
    "🚀 С чего начать\n"
    "1) Нажмите /start\n"
    "2) Убедитесь, что вам назначена роль (admin / manager / master)\n"
    "3) Откройте нужную панель:\n"
    "- /admin для администратора\n"
    "- /manager для менеджера\n"
    "- /profile для мастера\n\n"
    "👨‍💼 Менеджер: создание заявки\n"
    "1) Откройте /manager\n"
    "2) Нажмите /new_order\n"
    "3) Заполните шаги по очереди: город, дата, время, адрес, тип уборки, оборудование, условия, комментарий, контакт клиента\n"
    "4) На шаге проверки нажмите «Подтвердить»\n"
    "5) Бот сохранит и опубликует заявку в группу по городу\n\n"
    "Команды менеджера:\n"
    "- /new_order создать заявку\n"
    "- /my_orders список ваших заявок\n"
    "- /my_stats статистика по вашим заявкам\n\n"
    "🧰 Мастер: работа с заказами\n"
    "1) В группе нажмите «Откликнуться» под заявкой\n"
    "2) В личке подтвердите «Принять» или откажитесь\n"
    "3) При выполнении загрузите фото ДО и ПОСЛЕ\n"
    "4) Нажмите «Завершить заказ»\n\n"
    "Команды мастера:\n"
    "- /profile профиль мастера\n"
    "- /my_jobs ваши текущие/прошлые заказы\n"
    "- /my_stats ваша статистика\n\n"
    "🛠️ Администратор: контроль и аналитика\n"
    "1) Откройте /admin\n"
    "2) Используйте кнопки панели или команды\n"
    "3) Для фильтрации используйте кнопки в разделах заявок и пользователей\n\n"
    "Важные команды админа:\n"
    "- /stats и /city_stats аналитика\n"
    "- /orders, /order просмотр заявок\n"
    "- /set_status, /reassign управление заявками\n"
    "- /users, /set_role, /set_active управление пользователями\n"
    "- /broadcast рассылка\n"
    "- /export_basic, /export_full экспорт CSV\n\n"
    "❗ Если видите «Нет доступа», значит роль не назначена или аккаунт не в списке админов."
)


@router.message(CommandStart())
async def cmd_start(message: Message, db) -> None:
    """Welcome message and short instructions."""
    if is_admin(message.from_user.id, settings.get_admin_ids()):
        await ensure_user(db, message.from_user.id, role=ROLES["admin"])
        await message.answer(
            "👋 Доступ администратора подтвержден.\n"
            "Откройте /admin для панели управления или /help для полной инструкции."
        )
        return

    await ensure_user(db, message.from_user.id)
    await message.answer(
        "👋 Добро пожаловать!\n"
        "Откройте /manager или /profile в зависимости от вашей роли.\n"
        "Если роль еще не назначена, обратитесь к администратору.\n"
        "Для подробной инструкции используйте /help."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Detailed usage instructions."""
    await message.answer(HELP_TEXT)

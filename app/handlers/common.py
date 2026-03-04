"""
Basic commands available to all roles.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.config.settings import settings
from app.services.invites import consume_role_invite
from app.services.users import ensure_user, is_admin, set_role
from app.utils.constants import ROLES
from app.utils.keyboards import build_role_entry_keyboard

router = Router()

HELP_TEXT = (
    "📘 Подробная инструкция по работе с ботом\n\n"
    "Роли в системе:\n"
    "- admin: владелец/администратор\n"
    "- manager: менеджер заявок\n"
    "- master: мастер-клинер\n\n"
    "🚀 С чего начать\n"
    "1) Нажмите /start\n"
    "2) Убедитесь, что вам назначена роль (admin / manager / master)\n"
    "3) Откройте нужную панель:\n"
    "- /admin для администратора\n"
    "- /manager для менеджера\n"
    "- /profile для мастера\n\n"
    "Вход в роль по секретному слову:\n"
    "1) Нажмите кнопку «Войти в роль»\n"
    "2) Введите секретное слово, полученное от администратора\n"
    "3) Если username и слово совпали, роль активируется\n\n"
    "👨‍💼 Менеджер: создание заявки\n"
    "1) Откройте /manager\n"
    "2) Нажмите /new_order\n"
    "3) Бот пришлет одно сообщение-конструктор с инлайн-полями\n"
    "4) Нажимайте нужное поле, выбирайте/вводите значение и возвращайтесь в меню\n"
    "5) Нажмите «Опубликовать заявку»\n\n"
    "Команды менеджера:\n"
    "- /new_order создать заявку\n"
    "- /my_orders список ваших заявок\n"
    "- /my_stats статистика по вашим заявкам\n"
    "- /my_export_basic основная выгрузка только по вашим заявкам\n"
    "- /my_export_full недоступна менеджеру (только для админа)\n\n"
    "🧰 Мастер: работа с заказами\n"
    "1) В группе нажмите «Откликнуться» под заявкой\n"
    "2) В личке подтвердите «Принять» или откажитесь\n"
    "3) При выполнении загрузите 3-5 фото ДО и 3-5 фото ПОСЛЕ\n"
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
    "Полезно владельцу:\n"
    "- /owner_guide подробное руководство без технических терминов\n\n"
    "❗ Если видите «Нет доступа», значит роль не назначена или аккаунт не в списке админов."
)

OWNER_GUIDE_TEXT = (
    "📚 Подробная инструкция для владельца бота (без программирования)\n\n"
    "1) Что это за бот\n"
    "Бот помогает вести заявки на уборку: менеджер создает заявку, мастер откликается, "
    "отправляет фото ДО/ПОСЛЕ, админ контролирует статистику и выгрузки.\n\n"
    "2) Кто есть кто\n"
    "- admin: владелец и администраторы с полным доступом\n"
    "- manager: создают и ведут заявки\n"
    "- master: выполняют заказы и грузят фото\n\n"
    "3) Первичный вход владельца\n"
    "1. Откройте бота и нажмите /start\n"
    "2. Если ваш Telegram ID в ADMIN_IDS, бот выдаст роль admin автоматически\n"
    "3. Откройте /admin\n\n"
    "4) Как выдать роль новому сотруднику по секретному слову\n"
    "1. Войдите в /admin\n"
    "2. Нажмите кнопку «Хочу добавить роль»\n"
    "3. Выберите роль: Менеджер или Администратор\n"
    "4. Введите @username сотрудника (например: @ivanov)\n"
    "5. Бот создаст одноразовое секретное слово\n"
    "6. Передайте слово сотруднику любым безопасным способом\n"
    "7. Сотрудник нажимает «Войти в роль» и вводит слово\n"
    "8. Если username и слово совпали, роль активируется\n\n"
    "5) Важные правила по секретным словам\n"
    "- Секретное слово одноразовое\n"
    "- Слово привязано к конкретному @username\n"
    "- Если username у сотрудника другой, вход не пройдет\n"
    "- Если сотрудник без username, пусть сначала поставит его в Telegram настройках\n\n"
    "6) Работа менеджера\n"
    "1. /manager\n"
    "2. /new_order\n"
    "3. Заполнить карточку через одно сообщение с инлайн-кнопками\n"
    "4. Опубликовать заявку\n"
    "5. Следить за откликами мастеров\n"
    "6. При необходимости выгрузить свои данные: /my_export_basic\n\n"
    "7) Работа мастера\n"
    "1. Нажимает «Откликнуться» в группе\n"
    "2. Подтверждает заказ в ЛС\n"
    "3. Загружает 3-5 фото ДО и 3-5 фото ПОСЛЕ\n"
    "4. Завершает заявку\n\n"
    "8) Контроль владельца\n"
    "Основные команды:\n"
    "- /admin (панель)\n"
    "- /stats (общая аналитика)\n"
    "- /orders (последние заявки)\n"
    "- /users (пользователи)\n"
    "- /export_basic и /export_full (выгрузки)\n\n"
    "9) Безопасность\n"
    "- Никому не передавайте BOT_TOKEN\n"
    "- Если токен утек, перевыпустите в BotFather\n"
    "- Добавляйте только проверенных сотрудников\n"
    "- Регулярно проверяйте /users и отключайте лишних через /set_active\n\n"
    "10) Если что-то не работает\n"
    "1. Проверьте, что у пользователя правильная роль\n"
    "2. Проверьте, что сотрудник ввел верное слово и верный @username\n"
    "3. Проверьте GROUP_CHAT_ID и CITY_TOPIC_* в .env\n"
    "4. Проверьте, что бот имеет права в Telegram-группе\n"
    "5. Для проблем с базой проверьте DATABASE_URL и доступ к БД\n\n"
    "Команда с этой инструкцией: /owner_guide"
)


class LoginFlow(StatesGroup):
    """Role login by secret word."""

    waiting_secret = State()


@router.message(CommandStart())
async def cmd_start(message: Message, db) -> None:
    """Welcome message and short instructions."""
    if is_admin(message.from_user.id, settings.get_admin_ids()):
        await ensure_user(
            db,
            message.from_user.id,
            role=ROLES["admin"],
            username=message.from_user.username or "",
        )
        await message.answer(
            "👋 Доступ администратора подтвержден.\n"
            "Ваша роль: admin.\n"
            "Откройте /admin для панели управления или /help для полной инструкции."
        )
        return

    user = await ensure_user(db, message.from_user.id, username=message.from_user.username or "")
    role = user.role or "не назначена"
    await message.answer(
        "👋 Добро пожаловать!\n"
        f"Ваша роль: {role}.\n"
        "Откройте /manager или /profile в зависимости от вашей роли.\n"
        "Если роль еще не назначена, обратитесь к администратору.\n"
        "Для подробной инструкции используйте /help.\n"
        "Если у вас есть секретное слово, нажмите «Войти в роль».",
        reply_markup=build_role_entry_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Detailed usage instructions."""
    await message.answer(HELP_TEXT)


@router.message(Command("owner_guide"))
async def cmd_owner_guide(message: Message) -> None:
    """Very detailed owner manual."""
    await message.answer(OWNER_GUIDE_TEXT)


@router.callback_query(lambda c: c.data == "role_login:start")
async def role_login_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Ask user for secret word."""
    await state.set_state(LoginFlow.waiting_secret)
    await callback.message.answer(
        "🔐 Вход в роль\n"
        "Роль собеседника: гость\n"
        "Введите секретное слово одним сообщением."
    )
    await callback.answer()


@router.message(LoginFlow.waiting_secret)
async def role_login_secret(message: Message, state: FSMContext, db) -> None:
    """Consume secret word and assign role."""
    secret_word = (message.text or "").strip()
    username = message.from_user.username or ""
    if not username:
        await message.answer(
            "⛔ Нельзя войти в роль без @username.\n"
            "Сначала установите username в Telegram и повторите."
        )
        return

    invite = await consume_role_invite(db, secret_word, message.from_user.id, username)
    if not invite:
        await message.answer(
            "❌ Секретное слово не подошло.\n"
            "Проверьте слово, @username и попросите владельца выдать новое слово."
        )
        return

    user = await set_role(
        db,
        message.from_user.id,
        invite.role,
        username=message.from_user.username or "",
    )
    await state.clear()
    await message.answer(
        "✅ Роль активирована.\n"
        f"Роль собеседника: {user.role}.\n"
        "Теперь используйте нужную панель:\n"
        "- /admin для администратора\n"
        "- /manager для менеджера"
    )

"""
GLaDoS — PIN авторизация.
Запрашивает PIN при каждом /start, очищает историю чата.
"""

import time
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import CommandStart

log = logging.getLogger("GLaDoS.auth")
router = Router()

# Активные сессии: {user_id: timestamp}
_sessions: dict[int, float] = {}

PIN_CODE = None   # Загружается из config при старте


def init_pin(pin: str):
    """Инициализировать PIN из конфига."""
    global PIN_CODE
    PIN_CODE = str(pin)


def is_authorized(user_id: int) -> bool:
    return user_id in _sessions


def authorize(user_id: int):
    _sessions[user_id] = time.time()


def deauthorize(user_id: int):
    _sessions.pop(user_id, None)


class PinState(StatesGroup):
    waiting = State()


async def _clear_chat(message: Message):
    """Удалить последние 50 сообщений чата."""
    chat_id = message.chat.id
    msg_id = message.message_id
    deleted = 0
    for i in range(1, 51):
        try:
            await message.bot.delete_message(chat_id, msg_id - i)
            deleted += 1
        except:
            pass
    log.info(f"Cleared {deleted} messages for {message.from_user.id}")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start — деавторизация + запрос PIN."""
    from config import OWNER_ID
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Доступ запрещён.")
        return

    # Деавторизовать текущую сессию
    deauthorize(message.from_user.id)
    await state.clear()

    # Очистить историю чата
    await _clear_chat(message)

    # Удалить само сообщение /start
    try:
        await message.delete()
    except:
        pass

    await state.set_state(PinState.waiting)
    sent = await message.answer(
        "🔐 *GLaDoS CORE*\n\nВведите PIN-код:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    # Запомнить ID сообщения для удаления после ввода
    await state.update_data(pin_msg_id=sent.message_id)


@router.message(PinState.waiting)
async def check_pin(message: Message, state: FSMContext):
    """Проверка PIN-кода."""
    from config import OWNER_ID
    entered = message.text.strip() if message.text else ""

    # Сразу удалить сообщение с PIN для безопасности
    try:
        await message.delete()
    except:
        pass

    data = await state.get_data()
    pin_msg_id = data.get("pin_msg_id")

    if entered == PIN_CODE:
        authorize(message.from_user.id)
        await state.clear()

        # Удалить сообщение с запросом PIN
        try:
            await message.bot.delete_message(message.chat.id, pin_msg_id)
        except:
            pass

        log.info(f"User {message.from_user.id} authorized successfully")

        # Показать главное меню через общий handler
        from handlers.common import show_main_menu
        await show_main_menu(message)

    else:
        log.warning(f"Wrong PIN from user {message.from_user.id}: '{entered}'")
        await message.answer(
            "❌ Неверный PIN.\n\nПопробуйте ещё раз:",
            parse_mode="Markdown"
        )

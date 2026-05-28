"""
Обновлённое главное меню GLaDoS.
Замените функцию main_menu() в keyboards.py на эту версию.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    """Главное меню GLaDoS."""
    kb = InlineKeyboardBuilder()
    buttons = [
        ("🤖 Боты",          "bots:list"),
        ("🗺️ Карта серверов", "server_map:show"),
        ("📋 История событий","events:show"),
        ("📊 Отчёты",        "reports:list"),
        ("⚙️ Команды",       "commands:list"),
        ("🤖 AI-анализ",     "llm:show"),
        ("💳 Платежи",       "payments:list"),
        ("📦 Сервисы",       "services:list"),
        ("👤 Аккаунты",      "accounts:list"),
        ("📁 Файлы",         "files:list"),
    ]
    for text, cb in buttons:
        kb.button(text=text, callback_data=cb)
    kb.adjust(2)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="← Главное меню", callback_data="menu:main")
    return kb.as_markup()

# Установка патчей GLaDoS

## Что добавляется:
- 🔐 PIN-авторизация при каждом /start
- 🗺️ Карта всех серверов с CPU/RAM/Disk
- 📋 История событий (алерты, команды, статусы)
- 🤖 AI-анализ через Ollama
- 🏷️ Группировка ботов по тегам

---

## Шаг 1: Скопируйте файлы

```powershell
# Из папки glados_patches скопируйте в handlers\
Copy-Item "handlers_auth.py" "D:\GLaDoS CORE\GLaDoS_bot\handlers\auth.py"
Copy-Item "handlers_server_map.py" "D:\GLaDoS CORE\GLaDoS_bot\handlers\server_map.py"
Copy-Item "handlers_events.py" "D:\GLaDoS CORE\GLaDoS_bot\handlers\events.py"
Copy-Item "handlers_llm.py" "D:\GLaDoS CORE\GLaDoS_bot\handlers\llm.py"
```

---

## Шаг 2: Добавьте PIN в config.py

Откройте `D:\GLaDoS CORE\GLaDoS_bot\config.py` и добавьте:
```python
PIN_CODE = "1234"  # Поменяйте на свой PIN
```

---

## Шаг 3: Обновите handlers\__init__.py

```python
"""Сборка всех маршрутизаторов разделов."""

from .common import router as common_router, AuthMiddleware
from .payments import router as payments_router
from .subscriptions import router as subscriptions_router
from .accounts import router as accounts_router
from .files import router as files_router
from .bots import router as bots_router
from .services import router as services_router
from . import common, accounts, files, payments, subscriptions, services, bots, bot_reports

# Новые модули
from . import auth, server_map, events

try:
    from . import commands
    HAS_COMMANDS = True
except ImportError:
    HAS_COMMANDS = False

try:
    from . import llm
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

ALL_ROUTERS = [
    auth.router,          # ПЕРВЫМ — перехватывает /start и PIN
    common_router,
    payments_router,
    subscriptions_router,
    accounts_router,
    files_router,
    bots_router,
    bot_reports.router,
    services_router,
    server_map.router,
    events.router,
]

if HAS_COMMANDS:
    ALL_ROUTERS.append(commands.router)

if HAS_LLM:
    ALL_ROUTERS.append(llm.router)

__all__ = ["ALL_ROUTERS", "AuthMiddleware"]
```

---

## Шаг 4: Обновите keyboards.py

Замените функцию `main_menu()` содержимым из `keyboards_patch.py`.

---

## Шаг 5: Добавьте show_main_menu в handlers/common.py

В конец файла `handlers/common.py` добавьте:

```python
async def show_main_menu(message):
    """Показать главное меню после авторизации."""
    import keyboards as kb
    await message.answer(
        "✅ *GLaDoS CORE*\n\nДобро пожаловать! Выберите раздел:",
        reply_markup=kb.main_menu(),
        parse_mode="Markdown"
    )
```

---

## Шаг 6: Установите зависимости для LLM

```powershell
pip install aiohttp
```

---

## Шаг 7: Установите Ollama (для AI-анализа)

1. Скачайте с https://ollama.com/download
2. Установите и запустите:
```powershell
ollama serve
ollama pull llama3.2
```

---

## Шаг 8: Перезапустите GLaDoS

```powershell
Get-Process python | Stop-Process -Force
cd "D:\GLaDoS CORE\GLaDoS_bot"
.\START.bat
```

---

## Проверка:

1. Напишите `/start` боту
2. Бот должен очистить историю и спросить PIN
3. Введите PIN (по умолчанию: 1234)
4. Должно появиться главное меню с новыми кнопками

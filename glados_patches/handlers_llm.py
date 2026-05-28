"""
GLaDoS — Интеграция с Ollama LLM.
Анализ серверов через локальную языковую модель.
"""

import json
import logging
import aiohttp
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db

log = logging.getLogger("GLaDoS.llm")
router = Router()

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2"  # Меняйте на вашу модель: mistral, gemma2, qwen2.5, etc.


class LLMState(StatesGroup):
    waiting_question = State()


async def _get_ollama_models() -> list[str]:
    """Получить список доступных моделей Ollama."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_URL}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [m["name"] for m in data.get("models", [])]
    except:
        pass
    return []


async def _ask_ollama(question: str, context: str = "", model: str = OLLAMA_MODEL) -> str:
    """Отправить вопрос в Ollama и получить ответ."""
    system_prompt = """Ты — системный администратор GLaDoS, помощник по мониторингу серверов.
Отвечай кратко и по делу. Используй технический язык. Отвечай на русском языке.
Если есть данные о серверах, анализируй их и давай конкретные рекомендации."""

    if context:
        system_prompt += f"\n\nТекущие данные серверов:\n{context}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "stream": False
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("message", {}).get("content", "Нет ответа")
                else:
                    return f"Ошибка Ollama: HTTP {resp.status}"
    except aiohttp.ClientConnectorError:
        return "❌ Ollama недоступна. Убедитесь что сервис запущен:\n`ollama serve`"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


def _collect_server_context() -> str:
    """Собрать контекст о всех серверах для LLM."""
    bots = db.list_bots()
    if not bots:
        return "Нет зарегистрированных серверов."

    lines = []
    for bot in bots:
        status = bot.get("status", "unknown")
        lines.append(f"Сервер: {bot['name']} | Статус: {status}")

        latest = db.get_latest_report(bot["id"])
        if latest:
            try:
                details = latest.get("details", "{}")
                if isinstance(details, str):
                    details = json.loads(details)
                if details:
                    cpu = details.get("cpu_percent", "?")
                    ram = details.get("memory_percent", "?")
                    disk = details.get("disk_percent", "?")
                    lines.append(f"  CPU: {cpu}%, RAM: {ram}%, Disk: {disk}%")
            except:
                pass

    return "\n".join(lines)


def _build_llm_menu() -> object:
    kb = InlineKeyboardBuilder()
    quick = [
        ("📊 Анализ нагрузки", "Проанализируй текущую нагрузку всех серверов и дай рекомендации"),
        ("⚠️ Проблемы", "Какие проблемы есть на серверах прямо сейчас?"),
        ("🔮 Прогноз", "На основе текущих данных, какие проблемы могут возникнуть?"),
        ("💡 Оптимизация", "Как оптимизировать производительность серверов?"),
    ]
    for label, _ in quick:
        cb = f"llm:quick:{label}"
        kb.button(text=label, callback_data=cb)

    kb.button(text="✏️ Свой вопрос", callback_data="llm:custom")
    kb.button(text="🤖 Модели", callback_data="llm:models")
    kb.button(text="← Меню", callback_data="menu:main")
    kb.adjust(2, 2, 1, 2)
    return kb.as_markup()


@router.callback_query(F.data == "llm:show")
async def show_llm_menu(call: CallbackQuery):
    """Главное меню LLM."""
    models = await _get_ollama_models()
    if models:
        status = f"✅ Ollama работает | Модель: `{OLLAMA_MODEL}`"
    else:
        status = "⚠️ Ollama недоступна — запустите `ollama serve`"

    text = f"🤖 *AI-анализ серверов*\n\n{status}\n\nВыберите вопрос или задайте свой:"
    await call.message.edit_text(
        text,
        reply_markup=_build_llm_menu(),
        parse_mode="Markdown"
    )
    await call.answer()


@router.callback_query(F.data.startswith("llm:quick:"))
async def llm_quick_question(call: CallbackQuery):
    """Быстрый вопрос к LLM."""
    label = call.data.split(":", 2)[2]
    questions = {
        "📊 Анализ нагрузки": "Проанализируй текущую нагрузку всех серверов и дай рекомендации",
        "⚠️ Проблемы": "Какие проблемы есть на серверах прямо сейчас? Укажи конкретные сервера.",
        "🔮 Прогноз": "На основе текущих данных, какие проблемы могут возникнуть в ближайшее время?",
        "💡 Оптимизация": "Как оптимизировать производительность серверов на основе текущих данных?",
    }
    question = questions.get(label, label)

    await call.message.edit_text(
        f"🤖 *Анализирую...*\n\n_{question}_",
        parse_mode="Markdown"
    )
    await call.answer()

    context = _collect_server_context()
    answer = await _ask_ollama(question, context)

    kb = InlineKeyboardBuilder()
    kb.button(text="← Назад", callback_data="llm:show")
    kb.button(text="🔄 Снова", callback_data=call.data)
    kb.adjust(2)

    text = f"🤖 *AI-ответ*\n\n{answer}"
    if len(text) > 4000:
        text = text[:4000] + "..."

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "llm:custom")
async def llm_custom_question(call: CallbackQuery, state: FSMContext):
    """Запросить свой вопрос."""
    await state.set_state(LLMState.waiting_question)
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="llm:show")
    await call.message.edit_text(
        "🤖 *Задайте вопрос*\n\nНапример:\n"
        "• Почему nginx потребляет много памяти?\n"
        "• Стоит ли добавить RAM на сервер?\n"
        "• Что значит load average 5.2?",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )
    await call.answer()


@router.message(LLMState.waiting_question)
async def llm_process_question(message: Message, state: FSMContext):
    """Обработать пользовательский вопрос."""
    question = message.text.strip()
    await state.clear()

    try:
        await message.delete()
    except:
        pass

    thinking_msg = await message.answer(
        f"🤖 *Думаю...*\n\n_{question}_",
        parse_mode="Markdown"
    )

    context = _collect_server_context()
    answer = await _ask_ollama(question, context)

    kb = InlineKeyboardBuilder()
    kb.button(text="← Назад", callback_data="llm:show")
    kb.button(text="✏️ Новый вопрос", callback_data="llm:custom")
    kb.adjust(2)

    text = f"🤖 *AI-ответ*\n\n{answer}"
    if len(text) > 4000:
        text = text[:4000] + "..."

    await thinking_msg.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "llm:models")
async def show_models(call: CallbackQuery):
    """Показать доступные Ollama модели."""
    models = await _get_ollama_models()

    if not models:
        text = ("🤖 *Доступные модели*\n\n"
                "❌ Ollama недоступна\n\n"
                "Запустите: `ollama serve`\n"
                "Установите модель: `ollama pull llama3.2`")
    else:
        model_list = "\n".join(f"  • `{m}`" for m in models)
        text = (f"🤖 *Доступные модели Ollama*\n\n"
                f"{model_list}\n\n"
                f"Текущая: `{OLLAMA_MODEL}`\n"
                f"Изменить в `handlers_llm.py` → `OLLAMA_MODEL`")

    kb = InlineKeyboardBuilder()
    kb.button(text="← Назад", callback_data="llm:show")

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )
    await call.answer()

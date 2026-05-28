"""
GLaDoS — Карта серверов.
Показывает статус всех VPS одним экраном.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db

log = logging.getLogger("GLaDoS.server_map")
router = Router()


def _bar(percent: float, width: int = 10) -> str:
    """Текстовый прогресс-бар."""
    filled = int((percent / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    if percent >= 90:
        return f"🔴 {bar} {percent:.0f}%"
    elif percent >= 80:
        return f"🟡 {bar} {percent:.0f}%"
    else:
        return f"🟢 {bar} {percent:.0f}%"


def _status_icon(status: str) -> str:
    return {"online": "🟢", "offline": "🔴", "error": "⚠️"}.get(status, "⚪")


def _build_server_map_text() -> str:
    """Собрать текст карты всех серверов."""
    bots = db.list_bots()

    if not bots:
        return "🗺️ *Карта серверов*\n\nНет зарегистрированных серверов."

    lines = ["🗺️ *Карта серверов*\n"]

    for bot in bots:
        icon = _status_icon(bot["status"])
        tag = f" `[{bot.get('tag', '')}]`" if bot.get("tag") else ""
        lines.append(f"{icon} *{bot['name']}*{tag}")

        # Получить последний отчёт с метриками
        latest = db.get_latest_report(bot["id"])
        if latest and bot["status"] == "online":
            details = {}
            try:
                import json
                if latest.get("details"):
                    details = json.loads(latest["details"]) if isinstance(latest["details"], str) else latest["details"]
            except:
                pass

            cpu = details.get("cpu_percent", details.get("cpu", None))
            ram = details.get("memory_percent", details.get("ram", None))
            disk = details.get("disk_percent", details.get("disk", None))

            if cpu is not None:
                lines.append(f"  CPU  {_bar(float(cpu))}")
            if ram is not None:
                lines.append(f"  RAM  {_bar(float(ram))}")
            if disk is not None:
                lines.append(f"  Disk {_bar(float(disk))}")

            uptime = details.get("uptime", "")
            if uptime:
                lines.append(f"  ⏱ {uptime}")
        elif bot["status"] == "offline":
            lines.append("  📴 Офлайн")
        else:
            lines.append("  ⚪ Нет данных")

        lines.append("")

    # Статистика
    online = sum(1 for b in bots if b["status"] == "online")
    lines.append(f"━━━━━━━━━━━━━━━━━━")
    lines.append(f"Итого: *{online}/{len(bots)}* онлайн")

    return "\n".join(lines)


def _build_map_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="server_map:refresh")
    kb.button(text="🏷️ Фильтр по тегу", callback_data="server_map:filter")
    kb.button(text="← Меню", callback_data="menu:main")
    kb.adjust(2, 1)
    return kb.as_markup()


@router.callback_query(F.data == "server_map:show")
async def show_server_map(call: CallbackQuery):
    """Показать карту серверов."""
    text = _build_server_map_text()
    await call.message.edit_text(
        text,
        reply_markup=_build_map_keyboard(),
        parse_mode="Markdown"
    )
    await call.answer()


@router.callback_query(F.data == "server_map:refresh")
async def refresh_server_map(call: CallbackQuery):
    """Обновить карту серверов."""
    text = _build_server_map_text()
    try:
        await call.message.edit_text(
            text,
            reply_markup=_build_map_keyboard(),
            parse_mode="Markdown"
        )
    except:
        pass
    await call.answer("✅ Обновлено")


@router.callback_query(F.data == "server_map:filter")
async def filter_by_tag(call: CallbackQuery):
    """Показать фильтр по тегам."""
    bots = db.list_bots()
    tags = set()
    for bot in bots:
        if bot.get("tag"):
            tags.add(bot["tag"])

    if not tags:
        await call.answer("Нет тегов. Добавьте теги ботам.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for tag in sorted(tags):
        kb.button(text=f"🏷️ {tag}", callback_data=f"server_map:tag:{tag}")
    kb.button(text="🌐 Все серверы", callback_data="server_map:show")
    kb.button(text="← Назад", callback_data="server_map:show")
    kb.adjust(2)

    await call.message.edit_text(
        "🏷️ *Фильтр по тегу*\n\nВыберите группу:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )
    await call.answer()


@router.callback_query(F.data.startswith("server_map:tag:"))
async def filter_by_tag_value(call: CallbackQuery):
    """Показать серверы с конкретным тегом."""
    tag = call.data.split(":", 2)[2]
    bots = db.list_bots()
    filtered = [b for b in bots if b.get("tag") == tag]

    if not filtered:
        await call.answer(f"Нет серверов с тегом '{tag}'", show_alert=True)
        return

    lines = [f"🏷️ *Серверы: [{tag}]*\n"]
    for bot in filtered:
        icon = _status_icon(bot["status"])
        lines.append(f"{icon} *{bot['name']}*")

        latest = db.get_latest_report(bot["id"])
        if latest and bot["status"] == "online":
            try:
                import json
                details = json.loads(latest["details"]) if isinstance(latest.get("details"), str) else {}
                cpu = details.get("cpu_percent")
                ram = details.get("memory_percent")
                if cpu:
                    lines.append(f"  CPU  {_bar(float(cpu))}")
                if ram:
                    lines.append(f"  RAM  {_bar(float(ram))}")
            except:
                pass
        lines.append("")

    kb = InlineKeyboardBuilder()
    kb.button(text="← Все серверы", callback_data="server_map:show")
    kb.adjust(1)

    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )
    await call.answer()

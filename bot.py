import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
from config import CONFIG
from agent import SystemAgent
from utils import format_bytes, format_status_response

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MAIN_MENU, SERVICES_MENU, MANAGE_MENU = range(3)

class VPSBot:
    def __init__(self, token, admin_ids):
        self.token = token
        self.admin_ids = admin_ids
        self.services = ['ssh', 'nginx', 'mysql', 'postgresql', 'redis-server']

    def is_admin(self, user_id):
        return user_id in self.admin_ids

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - show main menu."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text('❌ Unauthorized')
            return ConversationHandler.END

        reply_keyboard = [
            ['📊 Статус VPS', '💾 Диски'],
            ['🔥 Топ процессов', '🧩 Сервисы'],
            ['🩺 Диагностика', '⚙️ Управление'],
        ]
        await update.message.reply_text(
            '🤖 *Меню мониторинга VPS*\n\nВыберите действие:',
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            parse_mode='Markdown'
        )
        return MAIN_MENU

    async def status_vps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show VPS status."""
        try:
            cpu = SystemAgent.get_cpu_status()
            memory = SystemAgent.get_memory_status()
            uptime = SystemAgent.get_uptime()
            load_avg = SystemAgent.get_load_average()

            response = f"""
📊 *Статус VPS*

*CPU:* {cpu['percent']}% ({cpu['count']} cores)
*Load Average:* {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}

*RAM:* {memory['percent']}%
├─ Used: {format_bytes(memory['used'])} / {format_bytes(memory['total'])}
└─ Available: {format_bytes(memory['available'])}

*Uptime:* {uptime}
"""
            await update.message.reply_text(response.strip(), parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def disks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show disk usage."""
        try:
            disks = SystemAgent.get_disk_status()
            response = "💾 *Диски*\n\n"

            for disk in disks:
                response += f"""
*{disk['device']}* ({disk['mountpoint']})
├─ Used: {format_bytes(disk['used'])} / {format_bytes(disk['total'])}
└─ Usage: {disk['percent']}%

"""
            await update.message.reply_text(response.strip(), parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def top_processes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show top CPU consuming processes."""
        try:
            processes = SystemAgent.get_top_processes(limit=5)
            response = "🔥 *Топ процессов (по CPU)*\n\n"

            for i, proc in enumerate(processes, 1):
                cpu = proc['cpu_percent'] or 0
                response += f"{i}. {proc['name'][:20]} - {cpu:.1f}%\n"

            await update.message.reply_text(response.strip(), parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def services_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show services menu."""
        try:
            services_status = SystemAgent.get_services_status(self.services)

            response = "🧩 *Состояние сервисов*\n\n"
            for service, status in services_status.items():
                emoji = '✅' if status == 'active' else '❌'
                response += f"{emoji} {service}: {status}\n"

            await update.message.reply_text(response.strip(), parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def diagnostics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run full diagnostics."""
        try:
            await update.message.reply_text('🔄 Running diagnostics...')

            failed = SystemAgent.get_failed_units()
            errors = SystemAgent.get_journalctl_errors(limit=5)
            ports = SystemAgent.get_listening_ports()

            response = "🩺 *Диагностика*\n\n"
            response += f"*Неисправные сервисы:*\n{failed[:500]}\n\n"
            response += f"*Последние ошибки:*\n{errors[:500]}\n\n"
            response += f"*Слушающие порты (первые 10):*\n"

            for conn in ports[:10]:
                if 'error' not in conn:
                    response += f"{conn['protocol']} {conn['address']}:{conn['port']}\n"

            await update.message.reply_text(response.strip(), parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def manage_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show management menu."""
        reply_keyboard = [
            ['🧨 Удалить бота с VPS'],
            ['◀️ Назад'],
        ]
        await update.message.reply_text(
            '⚙️ *Управление*\n\nВыберите действие:',
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            parse_mode='Markdown'
        )
        return MANAGE_MENU

    async def uninstall_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Uninstall bot from VPS."""
        reply_keyboard = [
            ['✅ Да, удалить', '❌ Отмена'],
        ]
        await update.message.reply_text(
            '⚠️ *Внимание!*\n\nЭто удалит бота с VPS и отключит все мониторинг. Вы уверены?',
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            parse_mode='Markdown'
        )
        return MANAGE_MENU

    async def confirm_uninstall(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm uninstallation."""
        if '✅' in update.message.text:
            try:
                import os
                import signal

                await update.message.reply_text('🧨 Удаление бота...\n\nДо встречи! 👋')

                os.system('systemctl stop mini-bot')
                os.system('systemctl disable mini-bot')

                os.kill(os.getpid(), signal.SIGTERM)
            except Exception as e:
                await update.message.reply_text(f'❌ Error during uninstall: {str(e)}')
        else:
            await update.message.reply_text('❌ Отмена.')

        return ConversationHandler.END

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button presses."""
        text = update.message.text

        if text == '📊 Статус VPS':
            return await self.status_vps(update, context)
        elif text == '💾 Диски':
            return await self.disks(update, context)
        elif text == '🔥 Топ процессов':
            return await self.top_processes(update, context)
        elif text == '🧩 Сервисы':
            return await self.services_menu(update, context)
        elif text == '🩺 Диагностика':
            return await self.diagnostics(update, context)
        elif text == '⚙️ Управление':
            return await self.manage_menu(update, context)
        elif text == '🧨 Удалить бота с VPS':
            return await self.uninstall_bot(update, context)
        elif text == '◀️ Назад':
            return await self.start(update, context)
        elif text == '✅ Да, удалить':
            return await self.confirm_uninstall(update, context)
        elif text == '❌ Отмена':
            return await self.start(update, context)

        return MAIN_MENU

    def run(self):
        """Run the bot."""
        app = Application.builder().token(self.token).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)],
                MANAGE_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)],
            },
            fallbacks=[CommandHandler('start', self.start)],
        )

        app.add_handler(conv_handler)

        logger.info('Bot started')
        app.run_polling()

if __name__ == '__main__':
    bot = VPSBot(CONFIG['telegram_token'], CONFIG['admin_chat_ids'])
    bot.run()

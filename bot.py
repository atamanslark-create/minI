import logging
import subprocess
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
from config import CONFIG
from agent import SystemAgent
from alerts import AlertManager
from utils import format_bytes, format_status_response

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MAIN_MENU, SERVICES_MENU, MANAGE_MENU, WG_MENU = range(4)

class VPSBot:
    def __init__(self, token, admin_ids):
        self.token = token
        self.admin_ids = admin_ids
        self.services = ['ssh', 'nginx', 'mysql', 'postgresql', 'redis-server']
        self.app = None
        self.alert_task = None

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
            ['📡 Пинг', '⚡ Спидтест'],
            ['🔐 WireGuard', '🩺 Диагностика'],
            ['⚙️ Управление'],
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

    async def ping_internet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check internet connectivity."""
        try:
            await update.message.reply_text('📡 Проверка связи...')
            ping_result = SystemAgent.ping_host()

            if ping_result['status'] == 'OK':
                response = f"✅ *Интернет доступен*\n\n{ping_result['message']}"
            else:
                response = f"❌ *Интернет недоступен*\n\n{ping_result['message']}"

            await update.message.reply_text(response.strip(), parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def speedtest_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run speedtest."""
        try:
            await update.message.reply_text('⚡ *Спидтест может занять 30-60 секунд...*\n\n⏳ Пожалуйста, ждите...', parse_mode='Markdown')

            result = subprocess.run(
                ['/bin/sh', '-c', 'speedtest-cli --simple 2>/dev/null || echo "Speedtest not installed"'],
                capture_output=True,
                text=True,
                timeout=120
            )

            if 'not installed' in result.stdout:
                response = "⚠️ *speedtest-cli не установлен*\n\nУстановите: `pip install speedtest-cli`"
                await update.message.reply_text(response, parse_mode='Markdown')
            else:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 3:
                    download, upload, ping = lines[0], lines[1], lines[2]
                    response = f"""⚡ *Результаты спидтеста*

📥 Download: {download} Mbps
📤 Upload: {upload} Mbps
📡 Ping: {ping} ms
"""
                    await update.message.reply_text(response.strip(), parse_mode='Markdown')
                else:
                    await update.message.reply_text('❌ Ошибка при выполнении спидтеста')

        except subprocess.TimeoutExpired:
            await update.message.reply_text('⏱️ Спидтест истёк по времени (> 120 сек)')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def wireguard_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show WireGuard menu."""
        reply_keyboard = [
            ['🔐 WG статус', '👥 Peers'],
            ['🩺 WG диагностика', '🔁 Рестарт WG'],
            ['◀️ Назад'],
        ]
        await update.message.reply_text(
            '🔐 *WireGuard*\n\nВыберите действие:',
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True),
            parse_mode='Markdown'
        )
        return WG_MENU

    async def wireguard_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show WireGuard status."""
        try:
            wg_status = SystemAgent.get_wireguard_status()

            if wg_status['active']:
                response = f"🔐 *WireGuard статус: АКТИВЕН*\n\n```\n{wg_status['output']}\n```"
            else:
                response = f"🔐 *WireGuard статус: НЕАКТИВЕН*\n\n{wg_status['output']}"

            await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return WG_MENU

    async def wireguard_peers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show WireGuard peers."""
        try:
            peers_data = SystemAgent.get_wireguard_peers()

            if peers_data['status'] == 'OK':
                if peers_data['peers']:
                    response = "👥 *WireGuard Peers*\n\n"
                    for peer in peers_data['peers']:
                        response += f"`{peer[:20]}...`\n"

                    if peers_data.get('handshakes'):
                        response += "\n*Последний handshake:*\n"
                        for peer_key, time_ago in list(peers_data['handshakes'].items())[:5]:
                            minutes_ago = time_ago // 60
                            response += f"{peer_key[:15]}...: {minutes_ago} мин назад\n"
                else:
                    response = "👥 *WireGuard Peers*\n\nNет активных peers"

                await update.message.reply_text(response, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ {peers_data.get('error', 'Unknown error')}")

        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return WG_MENU

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
        elif text == '📡 Пинг':
            return await self.ping_internet(update, context)
        elif text == '⚡ Спидтест':
            return await self.speedtest_menu(update, context)
        elif text == '🔐 WireGuard':
            return await self.wireguard_menu(update, context)
        elif text == '🔐 WG статус':
            return await self.wireguard_status(update, context)
        elif text == '👥 Peers':
            return await self.wireguard_peers(update, context)
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

    async def monitor_alerts(self):
        """Background task to monitor system and send alerts."""
        while True:
            try:
                alerts = AlertManager.check_alerts()

                for alert in alerts:
                    # Only send critical and warning alerts
                    if alert['severity'] in ['critical', 'warning', 'info']:
                        message = AlertManager.format_alert(alert)

                        for admin_id in self.admin_ids:
                            try:
                                await self.app.bot.send_message(
                                    chat_id=admin_id,
                                    text=message,
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                logger.error(f"Failed to send alert to {admin_id}: {str(e)}")

                # Check every 60 seconds
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Alert monitor error: {str(e)}")
                await asyncio.sleep(60)

    async def post_init(self, app):
        """Start background tasks after application initialization."""
        self.app = app
        self.alert_task = asyncio.create_task(self.monitor_alerts())
        logger.info('Alert monitor started')

    async def pre_shutdown(self, app):
        """Cleanup before shutdown."""
        if self.alert_task:
            self.alert_task.cancel()
            try:
                await self.alert_task
            except asyncio.CancelledError:
                pass

    def run(self):
        """Run the bot."""
        app = Application.builder().token(self.token).build()

        # Add callbacks for lifecycle events
        app.post_init = self.post_init
        app.pre_shutdown = self.pre_shutdown

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)],
                MANAGE_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)],
                WG_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)],
            },
            fallbacks=[CommandHandler('start', self.start)],
        )

        app.add_handler(conv_handler)

        logger.info('Bot started')
        app.run_polling()

if __name__ == '__main__':
    bot = VPSBot(CONFIG['telegram_token'], CONFIG['admin_chat_ids'])
    bot.run()

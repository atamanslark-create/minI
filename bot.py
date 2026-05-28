import logging
import subprocess
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
from config import CONFIG
from agent import SystemAgent
from alerts import AlertManager
from alerts_extended import SmartAlertManager
from metrics import MetricsCollector
from report import ReportBot
from utils import format_bytes, format_status_response
from glados_client import GLaDosClient

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MAIN_MENU, SERVICES_MENU, MANAGE_MENU, WG_MENU = range(4)

class VPSBot:
    def __init__(self, token, admin_ids, glados_token=None, glados_owner_id=None):
        self.token = token
        self.admin_ids = admin_ids
        # Service name variations to try
        self.service_aliases = {
            'ssh': ['ssh', 'sshd', 'openssh-server'],
            'nginx': ['nginx'],
            'mysql': ['mysql', 'mysqld', 'mariadb'],
            'postgresql': ['postgresql', 'postgres'],
            'redis': ['redis-server', 'redis'],
            'docker': ['docker', 'docker.service'],
        }
        self.services = self._get_available_services()
        self.app = None
        self.alert_task = None
        self.glados_report_task = None

        # GLaDoS integration
        self.glados_client = None
        if glados_token and glados_owner_id:
            try:
                self.glados_client = GLaDosClient(glados_token, glados_owner_id)
                logger.info("GLaDoS client initialized")
                self._register_glados_commands()
            except Exception as e:
                logger.warning(f"Failed to initialize GLaDoS client: {e}")

    def _register_glados_commands(self):
        """Register command handlers for GLaDoS."""
        if not self.glados_client:
            return

        async def handle_status(args):
            result = await self.glados_client.execute_command("status")
            return result['message']

        async def handle_restart(args):
            result = await self.glados_client.execute_command("restart", args)
            return result['message']

        async def handle_cleanup(args):
            result = await self.glados_client.execute_command("cleanup", args)
            return result['message']

        async def handle_processes(args):
            result = await self.glados_client.execute_command("processes")
            return result['message']

        self.glados_client.register_command("status", handle_status)
        self.glados_client.register_command("restart", handle_restart)
        self.glados_client.register_command("cleanup", handle_cleanup)
        self.glados_client.register_command("processes", handle_processes)

    def _get_available_services(self):
        """Get only services that exist on the system."""
        available = []

        # Try each service and its aliases (silently)
        for service_name, aliases in self.service_aliases.items():
            for alias in aliases:
                try:
                    if SystemAgent.service_exists(alias):
                        available.append(alias)
                        break
                except:
                    pass

        logger.info(f"Detected services: {available if available else 'none'}")
        return available

    def is_admin(self, user_id):
        return user_id in self.admin_ids

    async def clear_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear chat history by deleting recent messages."""
        try:
            chat_id = update.effective_chat.id
            message_id = update.message.message_id

            # Delete current message first
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except:
                pass

            # Delete last 30 messages in chat
            deleted_count = 0
            for i in range(1, 31):
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message_id - i)
                    deleted_count += 1
                except:
                    # Stop if we hit messages we can't delete
                    if deleted_count > 5:
                        break

            # Send confirmation
            await update.message.reply_text(f'🧹 История очищена ({deleted_count} сообщений удалено)')
        except Exception as e:
            logger.error(f"Clear history error: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - show main menu and clear chat history."""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text('❌ Unauthorized')
            return ConversationHandler.END

        # Clear chat history by deleting recent bot messages
        try:
            chat_id = update.effective_chat.id
            message_id = update.message.message_id

            # Delete last 20 messages in chat (clear history)
            for i in range(1, 21):
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message_id - i)
                except:
                    # Ignore errors for messages that don't exist or can't be deleted
                    pass
        except Exception as e:
            logger.warning(f"Could not clear history: {e}")

        reply_keyboard = [
            ['📊 Статус VPS', '💾 Диски'],
            ['🔥 Топ процессов', '🧩 Сервисы'],
            ['📡 Пинг', '🔌 Порты'],
            ['⚡ Спидтест', '📈 Статистика'],
            ['🔐 WireGuard', 'ℹ️ Инфо'],
            ['👥 SSH', '⚙️ Управление'],
            ['🧹 Очистить историю'],
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
            if not self.services:
                await update.message.reply_text(
                    '🧩 *Состояние сервисов*\n\n'
                    '⚠️ Не удалось найти доступные сервисы для мониторинга.\n\n'
                    'Возможно на сервере не установлены:\n'
                    '• SSH / SSHD\n'
                    '• Nginx\n'
                    '• MySQL\n'
                    '• PostgreSQL\n'
                    '• Redis\n'
                    '• Docker',
                    parse_mode='Markdown'
                )
                return MAIN_MENU

            services_status = SystemAgent.get_services_status(self.services)

            response = "🧩 *Состояние сервисов*\n\n"
            for service, status in services_status.items():
                if status == 'active':
                    emoji = '✅'
                elif status == 'inactive':
                    emoji = '⏹️'
                elif status == 'not-found':
                    emoji = '❌'
                else:
                    emoji = '⚠️'
                response += f"{emoji} {service}: {status}\n"

            response += "\n💡 *Для управления* нажмите на сервис:\n"
            buttons = []
            for service in self.services:
                buttons.append([f"🔄 {service}"])
            buttons.append(["◀️ Назад"])

            await update.message.reply_text(
                response.strip(),
                reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def manage_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show service management options."""
        text = update.message.text
        service_name = text.split()[-1] if '🔄' in text else None

        if not service_name:
            return MAIN_MENU

        context.user_data['selected_service'] = service_name

        buttons = [
            ['▶️ Запустить', '⏹️ Остановить'],
            ['🔄 Перезагрузить', '❌ Отмена'],
        ]

        await update.message.reply_text(
            f"🧩 *Управление сервисом: {service_name}*\n\nВыберите действие:",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
            parse_mode='Markdown'
        )

        return MAIN_MENU

    async def execute_service_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Execute service action."""
        text = update.message.text
        service = context.user_data.get('selected_service')

        if not service or '❌' in text:
            await update.message.reply_text('❌ Отмена')
            return MAIN_MENU

        action_map = {
            '▶️': 'start',
            '⏹️': 'stop',
            '🔄': 'restart',
        }

        action = None
        for emoji, act in action_map.items():
            if emoji in text:
                action = act
                break

        if not action:
            return MAIN_MENU

        try:
            result = SystemAgent.manage_service(service, action)

            if result['status'] == 'OK':
                response = f"✅ {result['message']}"
            else:
                response = f"❌ {result['message']}"

            await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def system_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show system information."""
        try:
            info = SystemAgent.get_system_info()
            uptime = SystemAgent.get_uptime()

            response = f"""ℹ️ *Информация о системе*

*Hostname:* {info.get('hostname', 'Unknown')}
*Kernel:* {info.get('kernel', 'Unknown')}
*Uptime:* {uptime}
"""
            await update.message.reply_text(response.strip(), parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def ssh_connections(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show active SSH connections."""
        try:
            connections = SystemAgent.get_ssh_connections()
            response = "👥 *Active SSH connections*\n\n"

            if connections and connections[0] != 'No SSH connections':
                for conn in connections:
                    if conn.strip():
                        response += f"`{conn[:60]}`\n"
            else:
                response += "No active SSH connections"

            await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show system statistics for the last 24 hours."""
        try:
            stats = MetricsCollector.get_stats(hours=24)

            if stats:
                response = f"""📈 *Статистика (последние 24 часа)*

*CPU:*
├─ Среднее: {stats['cpu_avg']}%
└─ Максимум: {stats['cpu_max']}%

*RAM:*
├─ Среднее: {stats['memory_avg']}%
└─ Максимум: {stats['memory_max']}%

*Диск:*
├─ Среднее: {stats['disk_avg']}%
└─ Максимум: {stats['disk_max']}%
"""
            else:
                response = "📈 *Статистика*\n\nЕще нет данных. Приходите позже."

            await update.message.reply_text(response, parse_mode='Markdown')
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

            # Use simple sync check
            ping_result = SystemAgent.ping_host_sync()
            response = ping_result['message']

            await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def check_ports_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check common service ports."""
        try:
            await update.message.reply_text('🔌 Проверка портов (это может занять 15 сек)...')

            # Common service ports
            ports_to_check = {
                22: 'SSH',
                80: 'HTTP',
                443: 'HTTPS',
                3306: 'MySQL',
                5432: 'PostgreSQL',
                6379: 'Redis',
            }

            response = "🔌 *Состояние портов*\n\n"

            # Check each port asynchronously in the background
            try:
                from network_checks import check_ports
                results = await asyncio.wait_for(
                    check_ports('localhost', list(ports_to_check.keys()), timeout=3.0),
                    timeout=20.0
                )

                for result in results:
                    if result.port in ports_to_check:
                        service = ports_to_check[result.port]
                        status = '✅ OPEN' if result.open else '❌ CLOSED'
                        latency = f" ({result.latency_ms}ms)" if result.latency_ms else ""
                        response += f"{status} - {result.port} ({service}){latency}\n"
            except asyncio.TimeoutError:
                response += "⏱️ Timeout при проверке портов"
            except Exception as e:
                # Fallback: use netstat
                response += f"⚠️ Не удалось проверить порты: {str(e)}"

            await update.message.reply_text(response.strip(), parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f'❌ Error: {str(e)}')

        return MAIN_MENU

    async def speedtest_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run speedtest."""
        try:
            await update.message.reply_text('⚡ *Спидтест может занять 30-60 секунд...*\n\n⏳ Пожалуйста, ждите...', parse_mode='Markdown')

            result = subprocess.run(
                ['/bin/sh', '-c', 'speedtest-cli --simple 2>/dev/null || speedtest-cli 2>/dev/null || echo "ERROR: not installed"'],
                capture_output=True,
                text=True,
                timeout=120
            )

            if 'ERROR: not installed' in result.stdout or 'not installed' in result.stderr:
                response = "⚠️ *speedtest-cli не установлен*\n\nУстановите в venv:\n`sudo /opt/mini-bot/venv/bin/pip install speedtest-cli`"
                await update.message.reply_text(response, parse_mode='Markdown')
            else:
                # Parse both formats: --simple (3 numbers) and regular output
                lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]

                download, upload, ping = None, None, None

                # Try to parse simple format (3 lines with numbers)
                if len(lines) >= 3:
                    try:
                        download = float(lines[0])
                        upload = float(lines[1])
                        ping = float(lines[2])
                    except ValueError:
                        # Try to parse labeled format
                        for line in lines:
                            if 'Ping:' in line or 'ping' in line.lower():
                                try:
                                    ping = float(line.split()[1])
                                except:
                                    pass
                            elif 'Download:' in line or 'download' in line.lower():
                                try:
                                    download = float(line.split()[1])
                                except:
                                    pass
                            elif 'Upload:' in line or 'upload' in line.lower():
                                try:
                                    upload = float(line.split()[1])
                                except:
                                    pass

                if download is not None and upload is not None and ping is not None:
                    response = f"""⚡ *Результаты спидтеста*

📥 Download: {download:.2f} Mbps
📤 Upload: {upload:.2f} Mbps
📡 Ping: {ping:.2f} ms
"""
                    await update.message.reply_text(response.strip(), parse_mode='Markdown')
                else:
                    await update.message.reply_text(f'❌ Ошибка парсинга:\n`{result.stdout[:200]}`', parse_mode='Markdown')

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
        elif text == '🔌 Порты':
            return await self.check_ports_cmd(update, context)
        elif text == '⚡ Спидтест':
            return await self.speedtest_menu(update, context)
        elif text == '🔐 WireGuard':
            return await self.wireguard_menu(update, context)
        elif text == '🔐 WG статус':
            return await self.wireguard_status(update, context)
        elif text == '👥 Peers':
            return await self.wireguard_peers(update, context)
        elif text == '📈 Статистика':
            return await self.statistics(update, context)
        elif text == 'ℹ️ Инфо':
            return await self.system_info(update, context)
        elif text == '👥 SSH':
            return await self.ssh_connections(update, context)
        elif text == '🩺 Диагностика':
            return await self.diagnostics(update, context)
        elif '🔄' in text:
            return await self.manage_service(update, context)
        elif text in ['▶️ Запустить', '⏹️ Остановить', '🔄 Перезагрузить']:
            return await self.execute_service_action(update, context)
        elif text == '⚙️ Управление':
            return await self.manage_menu(update, context)
        elif text == '🧨 Удалить бота с VPS':
            return await self.uninstall_bot(update, context)
        elif text == '◀️ Назад':
            return await self.start(update, context)
        elif text == '✅ Да, удалить':
            return await self.confirm_uninstall(update, context)
        elif text == '❌ Отмена' or text == '❌ Отмена.':
            return await self.start(update, context)
        elif text == '🧹 Очистить историю':
            return await self.clear_history(update, context)

        return MAIN_MENU

    async def monitor_alerts(self):
        """Background task to monitor system and send alerts with smart filtering."""
        while True:
            try:
                # Use SmartAlertManager for intelligent filtering and GLaDoS integration
                alerts = SmartAlertManager.check_alerts(glados_client=self.glados_client)

                for alert in alerts:
                    # Send all alerts (SmartAlertManager handles filtering)
                    message = SmartAlertManager.format_alert(alert)

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

    async def send_hourly_report_to_glados(self):
        """Send system status report to GLaDoS every 60 minutes."""
        if not self.glados_client:
            return

        while True:
            try:
                await asyncio.sleep(3600)  # Wait 60 minutes

                # Collect system metrics
                cpu = SystemAgent.get_cpu_status()
                memory = SystemAgent.get_memory_status()
                uptime = SystemAgent.get_uptime()
                disks = SystemAgent.get_disk_status()
                system_info = SystemAgent.get_system_info()

                # Build report content
                content_lines = [
                    f"📊 Статус системы",
                    f"",
                    f"<b>CPU:</b> {cpu['percent']}% ({cpu['count']} cores)",
                    f"<b>RAM:</b> {memory['percent']}% ({format_bytes(memory['used'])} / {format_bytes(memory['total'])})",
                    f"<b>Uptime:</b> {uptime}",
                ]

                # Add disk info
                if disks:
                    content_lines.append(f"")
                    content_lines.append(f"<b>Диски:</b>")
                    for disk in disks:
                        content_lines.append(f"  {disk['device']}: {disk['percent']}%")

                # Get service status
                services_status = SystemAgent.get_services_status(self.services)
                if services_status:
                    content_lines.append(f"")
                    content_lines.append(f"<b>Сервисы:</b>")
                    for service, status in services_status.items():
                        emoji = '✅' if status == 'active' else '❌'
                        content_lines.append(f"  {emoji} {service}: {status}")

                content = "\n".join(content_lines)
                details = {
                    "Hostname": system_info.get('hostname', 'Unknown'),
                    "Kernel": system_info.get('kernel', 'Unknown'),
                }

                await self.glados_client.send_report(
                    title="Hourly Status Report",
                    content=content,
                    details=details
                )

            except Exception as e:
                logger.error(f"Failed to send hourly report to GLaDoS: {e}")
                # Try again in 1 minute if error occurs
                await asyncio.sleep(60)

    async def post_init(self, app):
        """Start background tasks after application initialization."""
        self.app = app
        self.alert_task = asyncio.create_task(self.monitor_alerts())
        logger.info('Alert monitor started')

        if self.glados_client:
            self.glados_report_task = asyncio.create_task(self.send_hourly_report_to_glados())
            logger.info('GLaDoS hourly reporting started')

    async def pre_shutdown(self, app):
        """Cleanup before shutdown."""
        if self.alert_task:
            self.alert_task.cancel()
            try:
                await self.alert_task
            except asyncio.CancelledError:
                pass

        if self.glados_report_task:
            self.glados_report_task.cancel()
            try:
                await self.glados_report_task
            except asyncio.CancelledError:
                pass

        if self.glados_client:
            await self.glados_client.close()

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

        # Send startup report
        try:
            system_info = SystemAgent.get_system_info()
            ReportBot.send_report(
                "Bot Startup",
                f"mini-bot успешно запущен\n\n*Hostname:* {system_info.get('hostname', 'Unknown')}\n*Kernel:* {system_info.get('kernel', 'Unknown')}",
                "success"
            )
        except Exception as e:
            logger.warning(f"Could not send startup report: {e}")

        app.run_polling()

if __name__ == '__main__':
    bot = VPSBot(
        CONFIG['telegram_token'],
        CONFIG['admin_chat_ids'],
        glados_token=CONFIG.get('glados_token'),
        glados_owner_id=CONFIG.get('glados_owner_id')
    )
    bot.run()

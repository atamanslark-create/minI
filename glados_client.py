"""
Inter-bot communication: mini-bot <-> GLaDoS
Handles command receiving and report sending.
"""

import asyncio
from typing import Optional, Callable
from telegram import Bot, Update
from telegram.error import TelegramError
import logging

log = logging.getLogger("GLaDos-Client")


class GLaDosClient:
    """Client for communicating with GLaDoS master bot."""

    def __init__(self, glados_token: str, glados_chat_id: int, bot_name: str = "mini-bot"):
        """
        Args:
            glados_token: GLaDoS bot token
            glados_chat_id: GLaDoS owner chat ID (to send reports)
            bot_name: This bot's name for identification
        """
        self.glados_bot = Bot(token=glados_token)
        self.glados_chat_id = glados_chat_id
        self.bot_name = bot_name
        self.command_handlers = {}

    def register_command(self, command: str, handler: Callable):
        """Register a handler for a specific command from GLaDoS."""
        self.command_handlers[command] = handler

    async def send_report(self, title: str, content: str, details: Optional[dict] = None) -> bool:
        """
        Send a report to GLaDoS.

        Args:
            title: Report title
            content: Main report content (can be multiline)
            details: Optional dict of key-value details

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            lines = [f"<b>📊 {self.bot_name}</b>: {title}"]
            lines.append("")
            lines.append(content)

            if details:
                lines.append("")
                lines.append("<b>Детали:</b>")
                for key, value in details.items():
                    lines.append(f"• <b>{key}</b>: {value}")

            message = "\n".join(lines)
            await self.glados_bot.send_message(
                chat_id=self.glados_chat_id,
                text=message,
                parse_mode="HTML"
            )
            log.info(f"Report sent to GLaDoS: {title}")
            return True
        except TelegramError as e:
            log.error(f"Failed to send report: {e}")
            return False
        except Exception as e:
            log.error(f"Unexpected error sending report: {e}")
            return False

    async def send_command_result(self, command: str, success: bool, message: str) -> bool:
        """
        Send command execution result to GLaDoS.

        Args:
            command: The command that was executed
            success: Whether command execution was successful
            message: Result/error message

        Returns:
            True if sent successfully, False otherwise
        """
        icon = "✅" if success else "❌"
        title = f"Команда '{command}'"

        return await self.send_report(
            title=title,
            content=f"{icon} {message}"
        )

    async def handle_message(self, message_text: str) -> Optional[str]:
        """
        Handle incoming message that might contain a command from GLaDoS.
        Expected format: "command:arg1:arg2"

        Returns:
            Response message if handled, None otherwise
        """
        parts = message_text.strip().split(":", 1)
        command = parts[0].lower()

        if command not in self.command_handlers:
            return None

        handler = self.command_handlers[command]
        try:
            result = await handler(parts[1] if len(parts) > 1 else "")
            return result
        except Exception as e:
            log.error(f"Error handling command {command}: {e}")
            return f"Error: {str(e)}"

    async def execute_command(self, command: str, args: str = "") -> dict:
        """
        Execute a system command received from GLaDoS.

        Args:
            command: Command name (e.g., 'restart', 'cleanup')
            args: Command arguments (e.g., 'nginx' for 'restart')

        Returns:
            Dict with 'success' bool and 'message' str
        """
        from agent import SystemAgent
        import asyncio

        try:
            if command == "status":
                cpu = SystemAgent.get_cpu_status()
                mem = SystemAgent.get_memory_status()
                uptime = SystemAgent.get_uptime()
                return {
                    'success': True,
                    'message': f"CPU: {cpu['percent']}%, RAM: {mem['percent']}%, Uptime: {uptime}"
                }

            elif command == "restart" and args:
                result = SystemAgent.manage_service(args, "restart")
                return {
                    'success': result['success'],
                    'message': result['message']
                }

            elif command == "cleanup" and args == "logs":
                result = SystemAgent.cleanup_logs()
                return {
                    'success': result['success'],
                    'message': result['message']
                }

            elif command == "processes":
                processes = SystemAgent.get_top_processes(limit=5)
                lines = ["Top processes:"]
                for proc in processes:
                    lines.append(f"  {proc['name']}: {proc['cpu_percent']:.1f}%")
                return {
                    'success': True,
                    'message': "\n".join(lines)
                }

            elif command == "reboot":
                if args == "confirm":
                    # Dangerous command - requires explicit confirmation
                    result = SystemAgent.reboot_vps()
                    return {
                        'success': result['success'],
                        'message': result['message']
                    }
                else:
                    return {
                        'success': False,
                        'message': "Reboot requires confirmation argument"
                    }

            elif command == "speedtest":
                result = SystemAgent.run_speedtest()
                return {
                    'success': result['success'],
                    'message': result.get('output', result['message'])
                }

            else:
                return {
                    'success': False,
                    'message': f"Unknown command: {command}"
                }

        except Exception as e:
            log.error(f"Error executing command {command}: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }

    async def close(self):
        """Close the bot session."""
        await self.glados_bot.session.close()

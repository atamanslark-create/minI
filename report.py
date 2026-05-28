import requests
import json
from datetime import datetime

class ReportBot:
    """Send reports to external bot."""

    REPORT_BOT_TOKEN = "8173809033:AAFwMF0wtCZRM8JT1P-vMB-G0lFr5FQPlAU"  # @r2d2minimini_bot
    REPORT_BOT_CHAT_ID = 8173809033  # Admin chat ID

    @staticmethod
    def send_report(title, message, status='info'):
        """Send installation/status report to report bot."""
        try:
            emoji_map = {
                'success': '✅',
                'error': '❌',
                'warning': '⚠️',
                'info': 'ℹ️',
            }

            emoji = emoji_map.get(status, 'ℹ️')

            full_message = f"""{emoji} *{title}*

{message}

__{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}__
"""

            # Try to send via Telegram API
            url = f"https://api.telegram.org/bot{ReportBot.REPORT_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': ReportBot.REPORT_BOT_CHAT_ID,
                'text': full_message,
                'parse_mode': 'Markdown'
            }

            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200

        except Exception as e:
            print(f"Report error: {str(e)}")
            return False

    @staticmethod
    def send_install_report(hostname, status, details):
        """Send installation status report."""
        message = f"""
*Hostname:* {hostname}
*Status:* {status}

*Details:*
{details}
"""
        ReportBot.send_report("Installation Report", message, status)

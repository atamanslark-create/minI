import json
import time
from pathlib import Path
from datetime import datetime
from agent import SystemAgent
from metrics import MetricsCollector

STATUS_FILE = Path("/opt/mini-bot/status.json")

class AlertManager:
    """Manages system alerts and thresholds."""

    # Default thresholds
    THRESHOLDS = {
        'cpu_percent': 80,
        'memory_percent': 85,
        'disk_percent': 90,
    }

    @staticmethod
    def load_status():
        """Load previous status from file."""
        if STATUS_FILE.exists():
            try:
                with open(STATUS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    @staticmethod
    def save_status(status):
        """Save current status to file."""
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATUS_FILE, 'w') as f:
                json.dump(status, f, indent=2)
        except:
            pass

    @staticmethod
    def check_alerts():
        """Check for system alerts."""
        alerts = []
        previous_status = AlertManager.load_status()
        current_status = {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': None,
            'memory_percent': None,
            'disk_percent': None,
            'online': True,
        }

        try:
            # Initialize metrics DB on first run
            MetricsCollector.init_db()

            # Check CPU
            cpu = SystemAgent.get_cpu_status()
            current_status['cpu_percent'] = cpu['percent']
            if cpu['percent'] > AlertManager.THRESHOLDS['cpu_percent']:
                alerts.append({
                    'type': 'cpu_high',
                    'severity': 'warning',
                    'message': f"⚠️ CPU нагрузка высокая: {cpu['percent']}%"
                })

            # Check Memory
            mem = SystemAgent.get_memory_status()
            current_status['memory_percent'] = mem['percent']
            if mem['percent'] > AlertManager.THRESHOLDS['memory_percent']:
                alerts.append({
                    'type': 'memory_high',
                    'severity': 'warning',
                    'message': f"⚠️ RAM использование высокое: {mem['percent']}%"
                })

            # Check Disk
            disks = SystemAgent.get_disk_status()
            for disk in disks:
                if disk['percent'] > AlertManager.THRESHOLDS['disk_percent']:
                    current_status['disk_percent'] = disk['percent']
                    alerts.append({
                        'type': 'disk_high',
                        'severity': 'warning',
                        'message': f"⚠️ Диск заполнен: {disk['device']} - {disk['percent']}%"
                    })

            # Check failed services
            if 'failed_services' in previous_status:
                failed_now = []
                try:
                    failed = SystemAgent.get_failed_units()
                    if 'No failed units' not in failed:
                        failed_now = [line.split()[0] for line in failed.split('\n') if line]
                except:
                    pass

                previous_failed = previous_status.get('failed_services', [])
                newly_failed = set(failed_now) - set(previous_failed)
                newly_recovered = set(previous_failed) - set(failed_now)

                for service in newly_failed:
                    alerts.append({
                        'type': 'service_failed',
                        'severity': 'critical',
                        'message': f"🔴 Сервис упал: {service}"
                    })

                for service in newly_recovered:
                    alerts.append({
                        'type': 'service_recovered',
                        'severity': 'info',
                        'message': f"🟢 Сервис восстановлен: {service}"
                    })

                current_status['failed_services'] = failed_now

            # Check online status (uptime)
            try:
                uptime = SystemAgent.get_uptime()
                current_status['uptime'] = uptime

                # If previous uptime was set and current is lower, VPS was rebooted
                if 'uptime' in previous_status:
                    prev_uptime_str = previous_status['uptime']
                    # Simple check: if current uptime < previous, it was rebooted
                    if prev_uptime_str and uptime < prev_uptime_str:
                        alerts.append({
                            'type': 'vps_reboot',
                            'severity': 'info',
                            'message': f"🔄 VPS была перезагружена"
                        })
            except:
                pass

        except Exception as e:
            alerts.append({
                'type': 'check_error',
                'severity': 'error',
                'message': f"❌ Ошибка при проверке: {str(e)}"
            })

        current_status['last_check'] = datetime.now().isoformat()
        AlertManager.save_status(current_status)

        # Save metrics for statistics
        if current_status.get('cpu_percent') is not None:
            try:
                uptime = SystemAgent.get_uptime()
                uptime_seconds = int(uptime.split(':')[0]) * 3600 if ':' in uptime else 0
                disk_percent = current_status.get('disk_percent', 0)

                MetricsCollector.save_metric(
                    current_status['cpu_percent'],
                    current_status['memory_percent'] or 0,
                    disk_percent,
                    uptime_seconds
                )
            except:
                pass

        return alerts

    @staticmethod
    def format_alert(alert):
        """Format alert for Telegram message."""
        return alert['message']

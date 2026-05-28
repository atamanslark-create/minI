"""
Smart alert system with intelligent filtering.
Prevents spam while maintaining safety alerts.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from agent import SystemAgent
from metrics import MetricsCollector

ALERT_STATUS_FILE = Path("/opt/mini-bot/alert_status.json")

class SmartAlertManager:
    """Smart alert manager with cooldown periods to prevent spam."""

    # Resource thresholds
    THRESHOLDS = {
        'cpu_warning': 80,
        'cpu_critical': 90,
        'memory_warning': 80,
        'memory_critical': 85,
        'disk_warning': 85,
        'disk_critical': 90,
    }

    # Cooldown periods (seconds)
    COOLDOWNS = {
        'critical': 300,   # 5 minutes for critical alerts
        'warning': 600,    # 10 minutes for warnings
        'info': 3600,      # 1 hour for info
    }

    # Service restart tracking (max restarts before alert)
    SERVICE_RESTART_THRESHOLD = 3
    SERVICE_RESTART_WINDOW = 3600  # 1 hour

    @staticmethod
    def load_alert_status():
        """Load previous alert status from file."""
        if ALERT_STATUS_FILE.exists():
            try:
                with open(ALERT_STATUS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    @staticmethod
    def save_alert_status(status):
        """Save alert status to file."""
        try:
            ALERT_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(ALERT_STATUS_FILE, 'w') as f:
                json.dump(status, f, indent=2)
        except:
            pass

    @staticmethod
    def should_send_alert(alert_type: str, severity: str, status: dict) -> bool:
        """
        Check if enough time has passed since last similar alert.

        Returns True if alert should be sent, False if in cooldown.
        """
        last_alert_time = status.get(f"last_{alert_type}", 0)
        current_time = time.time()
        cooldown = SmartAlertManager.COOLDOWNS.get(severity, 600)

        time_since_last = current_time - last_alert_time
        return time_since_last >= cooldown

    @staticmethod
    def check_alerts(glados_client=None):
        """
        Check system and return only relevant alerts (smart filtering).

        Args:
            glados_client: Optional GLaDosClient for sending critical alerts

        Returns:
            List of alert dicts with type, severity, message
        """
        alerts = []
        status = SmartAlertManager.load_alert_status()
        current_time = time.time()

        try:
            # Initialize metrics DB
            MetricsCollector.init_db()

            # ===== CPU Check =====
            cpu = SystemAgent.get_cpu_status()
            cpu_percent = cpu['percent']

            if cpu_percent >= SmartAlertManager.THRESHOLDS['cpu_critical']:
                if SmartAlertManager.should_send_alert('cpu_critical', 'critical', status):
                    alert = {
                        'type': 'cpu_critical',
                        'severity': 'critical',
                        'message': f"🔴 CPU КРИТИЧНА: {cpu_percent}%"
                    }
                    alerts.append(alert)
                    status[f"last_cpu_critical"] = current_time

                    # Send to GLaDoS if connected
                    if glados_client:
                        try:
                            import asyncio
                            asyncio.create_task(glados_client.send_report(
                                title="🔴 Critical Alert: CPU",
                                content=f"CPU usage is critical: {cpu_percent}%",
                                details={"Cores": str(cpu['count'])}
                            ))
                        except:
                            pass

            elif cpu_percent >= SmartAlertManager.THRESHOLDS['cpu_warning']:
                if SmartAlertManager.should_send_alert('cpu_warning', 'warning', status):
                    alert = {
                        'type': 'cpu_warning',
                        'severity': 'warning',
                        'message': f"🟡 CPU высокая: {cpu_percent}%"
                    }
                    alerts.append(alert)
                    status[f"last_cpu_warning"] = current_time

            # ===== Memory Check =====
            mem = SystemAgent.get_memory_status()
            mem_percent = mem['percent']

            if mem_percent >= SmartAlertManager.THRESHOLDS['memory_critical']:
                if SmartAlertManager.should_send_alert('memory_critical', 'critical', status):
                    alert = {
                        'type': 'memory_critical',
                        'severity': 'critical',
                        'message': f"🔴 RAM КРИТИЧНА: {mem_percent}%"
                    }
                    alerts.append(alert)
                    status[f"last_memory_critical"] = current_time

                    # Send to GLaDoS if connected
                    if glados_client:
                        try:
                            import asyncio
                            asyncio.create_task(glados_client.send_report(
                                title="🔴 Critical Alert: Memory",
                                content=f"Memory usage is critical: {mem_percent}%",
                                details={"Total": f"{mem['total'] / (1024**3):.1f} GB"}
                            ))
                        except:
                            pass

            elif mem_percent >= SmartAlertManager.THRESHOLDS['memory_warning']:
                if SmartAlertManager.should_send_alert('memory_warning', 'warning', status):
                    alert = {
                        'type': 'memory_warning',
                        'severity': 'warning',
                        'message': f"🟡 RAM высокая: {mem_percent}%"
                    }
                    alerts.append(alert)
                    status[f"last_memory_warning"] = current_time

            # ===== Disk Check =====
            disks = SystemAgent.get_disk_status()
            for disk in disks:
                disk_percent = disk['percent']
                disk_key = disk['device'].replace('/', '_').replace('-', '_')

                if disk_percent >= SmartAlertManager.THRESHOLDS['disk_critical']:
                    alert_type = f"disk_critical_{disk_key}"
                    if SmartAlertManager.should_send_alert(alert_type, 'critical', status):
                        alert = {
                            'type': alert_type,
                            'severity': 'critical',
                            'message': f"🔴 ДИСК ЗАПОЛНЕН: {disk['device']} - {disk_percent}%"
                        }
                        alerts.append(alert)
                        status[f"last_{alert_type}"] = current_time

                        # Send to GLaDoS if connected
                        if glados_client:
                            try:
                                import asyncio
                                asyncio.create_task(glados_client.send_report(
                                    title="🔴 Critical Alert: Disk",
                                    content=f"Disk {disk['device']} is critical: {disk_percent}%",
                                    details={"Used": f"{disk['used'] / (1024**3):.1f} GB"}
                                ))
                            except:
                                pass

                elif disk_percent >= SmartAlertManager.THRESHOLDS['disk_warning']:
                    alert_type = f"disk_warning_{disk_key}"
                    if SmartAlertManager.should_send_alert(alert_type, 'warning', status):
                        alert = {
                            'type': alert_type,
                            'severity': 'warning',
                            'message': f"🟡 Диск заполнен: {disk['device']} - {disk_percent}%"
                        }
                        alerts.append(alert)
                        status[f"last_{alert_type}"] = current_time

            # ===== Service Status Check =====
            try:
                failed_units = SystemAgent.get_failed_units()
                failed_services = set()
                if 'No failed units' not in failed_units:
                    failed_services = {
                        line.split()[0] for line in failed_units.split('\n') if line.strip()
                    }

                if 'failed_services' not in status:
                    status['failed_services'] = []

                previous_failed = set(status.get('failed_services', []))
                newly_failed = failed_services - previous_failed
                recovered = previous_failed - failed_services

                for service in newly_failed:
                    if SmartAlertManager.should_send_alert(f'service_failed_{service}', 'critical', status):
                        alert = {
                            'type': 'service_failed',
                            'severity': 'critical',
                            'message': f"🔴 Сервис упал: {service}"
                        }
                        alerts.append(alert)
                        status[f"last_service_failed_{service}"] = current_time

                        # Send to GLaDoS if connected
                        if glados_client:
                            try:
                                import asyncio
                                asyncio.create_task(glados_client.send_report(
                                    title="🔴 Service Down",
                                    content=f"Service {service} has failed",
                                ))
                            except:
                                pass

                for service in recovered:
                    if SmartAlertManager.should_send_alert(f'service_recovered_{service}', 'info', status):
                        alert = {
                            'type': 'service_recovered',
                            'severity': 'info',
                            'message': f"🟢 Сервис восстановлен: {service}"
                        }
                        alerts.append(alert)
                        status[f"last_service_recovered_{service}"] = current_time

                status['failed_services'] = list(failed_services)

            except Exception as e:
                pass

            # ===== Uptime / Reboot Check =====
            try:
                uptime = SystemAgent.get_uptime()
                if 'uptime' in status and status['uptime']:
                    prev_uptime_str = status['uptime']
                    # Simple check: if uptime is lower, system was rebooted
                    if uptime < prev_uptime_str:
                        if SmartAlertManager.should_send_alert('vps_reboot', 'info', status):
                            alert = {
                                'type': 'vps_reboot',
                                'severity': 'info',
                                'message': "🔄 VPS была перезагружена"
                            }
                            alerts.append(alert)
                            status[f"last_vps_reboot"] = current_time

                status['uptime'] = uptime
            except:
                pass

        except Exception as e:
            # Don't alert on errors, just log
            pass

        status['last_check'] = datetime.now().isoformat()
        SmartAlertManager.save_alert_status(status)

        # Save metrics for statistics
        try:
            cpu = SystemAgent.get_cpu_status()
            mem = SystemAgent.get_memory_status()
            disks = SystemAgent.get_disk_status()
            uptime = SystemAgent.get_uptime()

            disk_percent = disks[0]['percent'] if disks else 0
            uptime_seconds = int(uptime.split(':')[0]) * 3600 if ':' in uptime else 0

            MetricsCollector.save_metric(
                cpu['percent'],
                mem['percent'],
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

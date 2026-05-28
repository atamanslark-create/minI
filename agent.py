import psutil
import subprocess
import re
from datetime import datetime, timedelta
from network_checks import ping_host, check_port, check_ports, PingResult, PortResult

class SystemAgent:
    """Collects system metrics and diagnostic information from VPS."""

    @staticmethod
    def get_cpu_status():
        """Get CPU load and count."""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        return {
            'percent': cpu_percent,
            'count': cpu_count,
        }

    @staticmethod
    def get_memory_status():
        """Get memory usage."""
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'used': mem.used,
            'percent': mem.percent,
            'available': mem.available,
        }

    @staticmethod
    def get_disk_status():
        """Get disk usage for all partitions."""
        disks = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'total': usage.total,
                    'used': usage.used,
                    'percent': usage.percent,
                })
            except PermissionError:
                continue
        return disks

    @staticmethod
    def get_uptime():
        """Get system uptime."""
        boot_time = psutil.boot_time()
        uptime_seconds = (datetime.now() - datetime.fromtimestamp(boot_time)).total_seconds()
        uptime = timedelta(seconds=int(uptime_seconds))
        return str(uptime)

    @staticmethod
    def get_load_average():
        """Get load average (1min, 5min, 15min)."""
        return psutil.getloadavg()

    @staticmethod
    def get_top_processes(limit=5):
        """Get top CPU consuming processes."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                pinfo = proc.info
                if pinfo['cpu_percent'] is None:
                    pinfo['cpu_percent'] = 0
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        return processes[:limit]

    @staticmethod
    def service_exists(service_name):
        """Check if systemd service exists."""
        try:
            # Try to get service status - if it works, service exists
            result = subprocess.run(
                ['/usr/bin/systemctl', 'show', '-p', 'Type', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            # If return code is 0 or output contains Type=, service exists
            return result.returncode == 0 or 'Type=' in result.stdout
        except:
            return False

    @staticmethod
    def get_service_status(service_name):
        """Get status of a systemd service."""
        try:
            result = subprocess.run(
                ['/usr/bin/systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            status = result.stdout.strip()
            if status == 'unknown':
                return 'not-found'
            return status
        except subprocess.TimeoutExpired:
            return 'timeout'
        except Exception as e:
            return 'error'

    @staticmethod
    def get_services_status(services):
        """Get status of multiple services."""
        status = {}
        for service in services:
            # Only check services that exist
            if SystemAgent.service_exists(service):
                status[service] = SystemAgent.get_service_status(service)
        return status

    @staticmethod
    def get_failed_units():
        """Get failed systemd units."""
        try:
            result = subprocess.run(
                ['/usr/bin/systemctl', 'list-units', '--failed', '--no-pager'],
                capture_output=True,
                text=True,
                timeout=10
            )
            lines = result.stdout.strip().split('\n')[0:20]
            return '\n'.join(lines) if lines else 'No failed units'
        except Exception as e:
            return f'Error: {str(e)}'

    @staticmethod
    def get_journalctl_errors(limit=10):
        """Get last critical journal entries."""
        try:
            result = subprocess.run(
                ['journalctl', '-p', 'err', '-n', str(limit), '--no-pager'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() if result.stdout else 'No errors found'
        except Exception as e:
            return f'Error: {str(e)}'

    @staticmethod
    def get_listening_ports():
        """Get listening network connections."""
        connections = []
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN':
                    connections.append({
                        'protocol': 'TCP' if conn.type == 1 else 'UDP',
                        'address': conn.laddr.ip,
                        'port': conn.laddr.port,
                        'pid': conn.pid,
                    })
        except Exception as e:
            return [{'error': str(e)}]

        return connections[:20]

    @staticmethod
    def get_network_interfaces():
        """Get network interface stats."""
        interfaces = {}
        for iface_name, iface_addrs in psutil.net_if_addrs().items():
            interfaces[iface_name] = []
            for addr in iface_addrs:
                interfaces[iface_name].append({
                    'family': addr.family.name,
                    'address': addr.address,
                })
        return interfaces

    @staticmethod
    async def ping_host_async(host='8.8.8.8', count=4, timeout=5):
        """Check internet connectivity with packet loss detection."""
        result = await ping_host(host, count, timeout)
        return {
            'status': 'OK' if result.reachable else 'FAILED',
            'host': host,
            'reachable': result.reachable,
            'avg_ms': result.avg_ms,
            'packet_loss_pct': result.packet_loss_pct,
            'message': (
                f'✅ Интернет доступен\n'
                f'Host: {host}\n'
                f'Ping: {result.avg_ms:.1f}ms\n'
                f'Loss: {result.packet_loss_pct:.1f}%'
                if result.reachable else
                f'❌ Интернет недоступен\n'
                f'Host: {host}\n'
                f'Error: {result.error if result.error else "No response"}\n'
                f'Loss: {result.packet_loss_pct:.1f}%'
            )
        }

    @staticmethod
    def ping_host_sync(host='8.8.8.8'):
        """Sync wrapper for DNS-based connectivity check."""
        import socket
        try:
            socket.setdefaulttimeout(4)
            socket.gethostbyname(host)
            return {
                'status': 'OK',
                'host': host,
                'message': f'✅ DNS доступен ({host})'
            }
        except Exception as e:
            return {
                'status': 'FAILED',
                'host': host,
                'message': f'❌ Ошибка: {str(e)}'
            }

    @staticmethod
    def get_wireguard_status():
        """Get WireGuard tunnel status."""
        try:
            result = subprocess.run(
                ['wg', 'show', 'wg0'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return {
                    'active': True,
                    'output': result.stdout.strip()
                }
            else:
                return {
                    'active': False,
                    'output': 'WireGuard interface not found'
                }
        except FileNotFoundError:
            return {
                'active': False,
                'output': 'WireGuard not installed'
            }
        except Exception as e:
            return {
                'active': False,
                'output': f'Error: {str(e)}'
            }

    @staticmethod
    def manage_service(service_name, action):
        """Manage systemd service (start, stop, restart)."""
        valid_actions = ['start', 'stop', 'restart']
        if action not in valid_actions:
            return {'status': 'ERROR', 'message': f'Invalid action. Use: {", ".join(valid_actions)}'}

        # Check if service exists first
        if not SystemAgent.service_exists(service_name):
            return {
                'status': 'ERROR',
                'message': f'Сервис {service_name} не установлен на сервере'
            }

        try:
            result = subprocess.run(
                ['/usr/bin/systemctl', action, service_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    'status': 'OK',
                    'message': f'✅ Сервис {service_name} успешно {action}ed'
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else f'Failed to {action} {service_name}'
                # Clean up error message
                if 'not found' in error_msg.lower():
                    error_msg = f'Сервис {service_name} не найден'
                return {
                    'status': 'ERROR',
                    'message': f'❌ {error_msg}'
                }
        except subprocess.TimeoutExpired:
            return {'status': 'ERROR', 'message': '❌ Command timeout'}
        except Exception as e:
            return {'status': 'ERROR', 'message': f'❌ {str(e)}'}

    @staticmethod
    def get_ssh_connections():
        """Get active SSH connections."""
        try:
            result = subprocess.run(
                ['ss', '-tunap'],
                capture_output=True,
                text=True,
                timeout=5
            )

            connections = []
            for line in result.stdout.split('\n'):
                if 'ssh' in line.lower() or ':22' in line:
                    connections.append(line)

            return connections[:10] if connections else ['No SSH connections']
        except Exception as e:
            return [f'Error: {str(e)}']

    @staticmethod
    def get_system_info():
        """Get detailed system information."""
        try:
            hostname = subprocess.run(
                ['hostname'],
                capture_output=True,
                text=True,
                timeout=2
            ).stdout.strip()

            kernel = subprocess.run(
                ['uname', '-r'],
                capture_output=True,
                text=True,
                timeout=2
            ).stdout.strip()

            return {
                'hostname': hostname,
                'kernel': kernel,
            }
        except Exception as e:
            return {'error': str(e)}
        """Get WireGuard peers with handshake info."""
        try:
            result = subprocess.run(
                ['wg', 'show', 'wg0', 'peers'],
                capture_output=True,
                text=True,
                timeout=5
            )
            peers = []
            if result.returncode == 0 and result.stdout.strip():
                for peer in result.stdout.strip().split('\n'):
                    if peer:
                        peers.append(peer)

                handshake_result = subprocess.run(
                    ['wg', 'show', 'wg0', 'latest-handshakes'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if handshake_result.returncode == 0:
                    handshakes = {}
                    for line in handshake_result.stdout.strip().split('\n'):
                        if line:
                            parts = line.split('\t')
                            if len(parts) == 2:
                                peer_key = parts[0]
                                timestamp = int(parts[1])
                                time_ago = int(datetime.now().timestamp()) - timestamp
                                handshakes[peer_key] = time_ago

                    return {
                        'status': 'OK',
                        'peers': peers,
                        'handshakes': handshakes
                    }

            return {
                'status': 'OK',
                'peers': peers if peers else [],
                'handshakes': {}
            }
        except Exception as e:
            return {
                'status': 'ERROR',
                'error': str(e)
            }

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/opt/mini-bot/metrics.db")

class MetricsCollector:
    """Collects and stores system metrics over time for statistics."""

    @staticmethod
    def init_db():
        """Initialize database with tables."""
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY,
                    timestamp INTEGER,
                    cpu_percent REAL,
                    memory_percent REAL,
                    disk_percent REAL,
                    uptime_seconds INTEGER
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY,
                    timestamp INTEGER,
                    event_type TEXT,
                    message TEXT
                )
            ''')

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database init error: {e}")

    @staticmethod
    def save_metric(cpu_percent, memory_percent, disk_percent, uptime_seconds):
        """Save system metrics to database."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            timestamp = int(datetime.now().timestamp())
            cursor.execute('''
                INSERT INTO metrics (timestamp, cpu_percent, memory_percent, disk_percent, uptime_seconds)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, cpu_percent, memory_percent, disk_percent, uptime_seconds))

            # Keep only last 30 days of data
            cutoff_time = timestamp - (30 * 24 * 3600)
            cursor.execute('DELETE FROM metrics WHERE timestamp < ?', (cutoff_time,))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Metric save error: {e}")

    @staticmethod
    def log_event(event_type, message):
        """Log a system event."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            timestamp = int(datetime.now().timestamp())
            cursor.execute('''
                INSERT INTO events (timestamp, event_type, message)
                VALUES (?, ?, ?)
            ''', (timestamp, event_type, message))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Event log error: {e}")

    @staticmethod
    def get_stats(hours=24):
        """Get statistics for the last N hours."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            cutoff_time = int((datetime.now() - timedelta(hours=hours)).timestamp())

            cursor.execute('''
                SELECT AVG(cpu_percent), MAX(cpu_percent),
                       AVG(memory_percent), MAX(memory_percent),
                       AVG(disk_percent), MAX(disk_percent)
                FROM metrics WHERE timestamp > ?
            ''', (cutoff_time,))

            result = cursor.fetchone()
            conn.close()

            if result and result[0] is not None:
                return {
                    'cpu_avg': round(result[0], 1),
                    'cpu_max': round(result[1], 1),
                    'memory_avg': round(result[2], 1),
                    'memory_max': round(result[3], 1),
                    'disk_avg': round(result[4], 1),
                    'disk_max': round(result[5], 1),
                }

            return None

        except Exception as e:
            print(f"Stats error: {e}")
            return None

    @staticmethod
    def get_events(event_type=None, limit=10):
        """Get recent events."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()

            if event_type:
                cursor.execute('''
                    SELECT timestamp, event_type, message
                    FROM events WHERE event_type = ?
                    ORDER BY timestamp DESC LIMIT ?
                ''', (event_type, limit))
            else:
                cursor.execute('''
                    SELECT timestamp, event_type, message
                    FROM events ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))

            results = cursor.fetchall()
            conn.close()

            events = []
            for row in results:
                ts = datetime.fromtimestamp(row[0])
                events.append({
                    'time': ts.strftime('%H:%M:%S'),
                    'type': row[1],
                    'message': row[2]
                })

            return events

        except Exception as e:
            print(f"Events fetch error: {e}")
            return []

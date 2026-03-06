"""
Smart alerting engine for homelab dashboard.
Checks Glances metrics against thresholds, fires Discord webhooks with deduplication.
"""

import os
import time
import json
import threading
import requests as http_requests
from collections import deque
from datetime import datetime

# Alert thresholds (defaults)
THRESHOLDS = {
    'memory_percent': {'warning': 85, 'critical': 90},
    'temp_c': {'warning': 75, 'critical': 80},
    'cpu_percent': {'warning': 90, 'critical': 95},
}

# How many consecutive checks before firing an alert (prevents transient spikes)
SUSTAINED_CHECKS = 2

# Cooldown: don't re-alert for the same metric on the same machine within this window
COOLDOWN_SECS = 600  # 10 minutes

# Max alert history entries
MAX_HISTORY = 100

# Discord user ID to ping
DISCORD_USER_ID = '139476150786195456'


HISTORY_FILE = os.path.join(os.path.dirname(__file__), '.alert_history.json')


class AlertEngine:
    def __init__(self, discord_webhook_url=None, glances_hosts=None):
        self.webhook_url = discord_webhook_url
        self.glances_hosts = glances_hosts or {}  # {machine_id: {'host': ip, 'port': 61999}}
        self.lock = threading.Lock()

        # Track consecutive breach counts: {(machine_id, metric): count}
        self._breach_counts = {}

        # Track active alerts: {(machine_id, metric): timestamp_fired}
        self._active_alerts = {}

        # Alert history: deque of dicts
        self.history = deque(maxlen=MAX_HISTORY)

        # Resolved alerts waiting to be sent
        self._pending_resolved = []

        # Load persisted history
        self._load_history()

    def check_all(self):
        """Run threshold checks for all configured machines. Call from bg thread."""
        for machine_id, cfg in self.glances_hosts.items():
            host = cfg['host']
            port = cfg.get('port', 61999)
            stats = self._fetch_glances(host, port)
            if stats is None:
                continue
            self._evaluate(machine_id, stats)

        # Send any pending resolved notifications
        with self.lock:
            resolved = list(self._pending_resolved)
            self._pending_resolved.clear()
        for r in resolved:
            self._send_discord(r)

    def _fetch_glances(self, host, port, timeout=3):
        """Fetch CPU, memory, temp, and top processes from Glances API v4."""
        base = f'http://{host}:{port}/api/4'
        stats = {}
        try:
            mem = http_requests.get(f'{base}/mem', timeout=timeout)
            if mem.status_code == 200:
                stats['memory_percent'] = mem.json().get('percent')

            cpu = http_requests.get(f'{base}/cpu', timeout=timeout)
            if cpu.status_code == 200:
                stats['cpu_percent'] = cpu.json().get('total')

            sensors = http_requests.get(f'{base}/sensors', timeout=timeout)
            if sensors.status_code == 200:
                sensor_data = sensors.json()
                if isinstance(sensor_data, list):
                    core_temps = []
                    for s in sensor_data:
                        stype = s.get('type', '')
                        val = s.get('value')
                        if val is None:
                            continue
                        if stype == 'temperature_core':
                            label = s.get('label', '')
                            if 'package' in label.lower():
                                stats['temp_c'] = val
                            elif 'core' in label.lower():
                                core_temps.append(val)
                    if 'temp_c' not in stats and core_temps:
                        stats['temp_c'] = max(core_temps)

            # Top processes by memory for context in alerts
            try:
                proc = http_requests.get(f'{base}/processlist', timeout=timeout)
                if proc.status_code == 200:
                    proc_list = proc.json()
                    if isinstance(proc_list, list):
                        top = sorted(proc_list, key=lambda p: p.get('memory_percent', 0), reverse=True)[:5]
                        stats['_top_processes'] = [
                            {'name': p.get('name', '?'), 'mem': round(p.get('memory_percent', 0), 1), 'cpu': round(p.get('cpu_percent', 0), 1)}
                            for p in top
                        ]
            except Exception:
                pass

            return stats if stats else None
        except Exception:
            return None

    def _evaluate(self, machine_id, stats):
        """Check stats against thresholds, manage breach counts, fire/resolve alerts."""
        now = time.time()

        for metric, thresholds in THRESHOLDS.items():
            value = stats.get(metric)
            if value is None:
                continue

            key = (machine_id, metric)
            level = None

            if value >= thresholds['critical']:
                level = 'critical'
            elif value >= thresholds['warning']:
                level = 'warning'

            if level:
                # Increment breach count
                with self.lock:
                    self._breach_counts[key] = self._breach_counts.get(key, 0) + 1
                    count = self._breach_counts[key]

                if count >= SUSTAINED_CHECKS:
                    self._maybe_fire_alert(machine_id, metric, value, level, thresholds, stats, now)
            else:
                # Value is back to normal
                with self.lock:
                    self._breach_counts.pop(key, None)
                    if key in self._active_alerts:
                        fired_at = self._active_alerts.pop(key)
                        duration = int(now - fired_at)
                        self._record_resolved(machine_id, metric, value, duration, now)

    def _maybe_fire_alert(self, machine_id, metric, value, level, thresholds, stats, now):
        """Fire alert if not in cooldown."""
        key = (machine_id, metric)
        with self.lock:
            last_fired = self._active_alerts.get(key, 0)
            if (now - last_fired) < COOLDOWN_SECS and key in self._active_alerts:
                return  # Still in cooldown
            self._active_alerts[key] = now

        alert = {
            'machine': machine_id,
            'metric': metric,
            'value': round(value, 1),
            'level': level,
            'threshold': thresholds[level],
            'top_processes': stats.get('_top_processes', []),
            'timestamp': now,
            'resolved': False,
        }

        with self.lock:
            self.history.append(alert)
        self._save_history()

        self._send_discord(alert)

    def _record_resolved(self, machine_id, metric, value, duration_secs, now):
        """Record a resolved alert and queue Discord notification."""
        resolved = {
            'machine': machine_id,
            'metric': metric,
            'value': round(value, 1),
            'level': 'resolved',
            'duration_secs': duration_secs,
            'timestamp': now,
            'resolved': True,
        }
        with self.lock:
            self.history.append(resolved)
            self._pending_resolved.append(resolved)
        self._save_history()

    def _send_discord(self, alert):
        """Send a Discord webhook embed for an alert."""
        if not self.webhook_url:
            return

        metric_labels = {
            'memory_percent': 'Memory',
            'temp_c': 'Temperature',
            'cpu_percent': 'CPU',
        }
        metric_units = {
            'memory_percent': '%',
            'temp_c': '\u00b0C',
            'cpu_percent': '%',
        }

        metric_name = metric_labels.get(alert['metric'], alert['metric'])
        unit = metric_units.get(alert['metric'], '')
        machine = alert['machine']

        if alert.get('resolved'):
            duration = alert.get('duration_secs', 0)
            dur_str = f"{duration // 60}m {duration % 60}s" if duration >= 60 else f"{duration}s"
            embed = {
                'title': f'{machine} -- {metric_name} Resolved',
                'description': f'{metric_name} returned to normal: **{alert["value"]}{unit}**\nDuration: {dur_str}',
                'color': 0x34d399,  # green
                'timestamp': datetime.utcfromtimestamp(alert['timestamp']).isoformat(),
            }
            content = ''
        else:
            color = 0xf87171 if alert['level'] == 'critical' else 0xf59e0b  # red / amber
            top_procs = alert.get('top_processes', [])
            proc_lines = '\n'.join(
                f"`{p['name'][:20]:<20}` mem {p['mem']}% cpu {p['cpu']}%"
                for p in top_procs
            ) if top_procs else 'N/A'

            embed = {
                'title': f'{machine} -- {metric_name} {alert["level"].upper()}',
                'description': (
                    f'**{metric_name}**: {alert["value"]}{unit} (threshold: {alert.get("threshold", "?")}{unit})\n\n'
                    f'**Top Consumers:**\n{proc_lines}'
                ),
                'color': color,
                'timestamp': datetime.utcfromtimestamp(alert['timestamp']).isoformat(),
            }
            content = f'<@{DISCORD_USER_ID}>'

        payload = {
            'content': content,
            'embeds': [embed],
        }

        try:
            http_requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception:
            pass

    def get_history(self, limit=50):
        """Return recent alert history as list of dicts, newest first."""
        with self.lock:
            items = list(self.history)
        items.reverse()
        return items[:limit]

    def get_active_count(self):
        """Return number of currently active (unresolved) alerts."""
        with self.lock:
            return len(self._active_alerts)

    def get_active_alerts(self):
        """Return list of currently active alert keys."""
        with self.lock:
            return [
                {'machine': k[0], 'metric': k[1], 'since': v}
                for k, v in self._active_alerts.items()
            ]

    def _save_history(self):
        """Persist alert history to disk."""
        try:
            with self.lock:
                items = list(self.history)
            with open(HISTORY_FILE, 'w') as f:
                json.dump(items, f)
        except Exception:
            pass

    def _load_history(self):
        """Load alert history from disk."""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE) as f:
                    items = json.load(f)
                with self.lock:
                    for item in items[-MAX_HISTORY:]:
                        self.history.append(item)
        except Exception:
            pass

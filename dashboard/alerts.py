"""
Smart alerting engine for homelab dashboard.
Checks Glances metrics against thresholds, fires Discord webhooks with deduplication.
Also includes SecurityHealthMonitor for proactive checks on critical security
services (CrowdSec, firewall-bouncer) that systemd OnFailure can't catch:
panic-restart loops, stale LAPI pulls, ipset drift.
"""

import os
import subprocess
import time
import json
import threading
import requests as http_requests
from collections import deque
from datetime import datetime

# Alert thresholds (defaults)
# 'below': True means alert when value drops BELOW threshold (e.g. battery)
THRESHOLDS = {
    'memory_percent': {'warning': 85, 'critical': 90},
    'temp_c': {'warning': 100, 'critical': 110},
    'cpu_percent': {'warning': 90, 'critical': 95},
    'battery_percent': {'warning': 25, 'critical': 10, 'below': True},
}

# Per-metric sustained-check overrides (default is SUSTAINED_CHECKS)
METRIC_SUSTAINED = {
    'battery_percent': 3,   # ~30s — battery reads are stable, not transient
}

# AC power lost detection (binary, separate from threshold metrics)
AC_POWER_SUSTAINED = 2      # ~20s — filter cable wiggle, alert fast
AC_POWER_COOLDOWN = 3600    # 1 hour — don't nag once you know it's on battery

# Per-machine threshold overrides. Merge on top of THRESHOLDS by metric.
# noc-claw runs mlx_lm.server (~7.5GB resident) so memory routinely sits in the
# high 80s -- default 85/90 memory thresholds would fire constantly. Bump the
# floor so we only get alerted when it's genuinely out of headroom.
MACHINE_OVERRIDES = {
    'noc-claw': {
        'memory_percent': {'warning': 92, 'critical': 96},
    },
}


def _get_thresholds(machine_id, metric):
    override = MACHINE_OVERRIDES.get(machine_id, {}).get(metric)
    return override if override else THRESHOLDS[metric]

# How many consecutive checks before firing an alert (prevents transient spikes)
# At 10s check intervals, 12 = requires ~2 minutes of sustained breach before alerting
SUSTAINED_CHECKS = 12

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
                        elif stype == 'battery':
                            stats['battery_percent'] = val
                            stats['battery_status'] = s.get('status', '')
                    if 'temp_c' not in stats and core_temps:
                        stats['temp_c'] = max(core_temps)

            # Top processes by memory for context in alerts
            try:
                proc = http_requests.get(f'{base}/processlist', timeout=timeout)
                if proc.status_code == 200:
                    proc_list = proc.json()
                    if isinstance(proc_list, list):
                        top = sorted(proc_list, key=lambda p: p.get('memory_percent') or 0, reverse=True)[:5]
                        stats['_top_processes'] = [
                            {'name': p.get('name', '?'), 'mem': round(p.get('memory_percent') or 0, 1), 'cpu': round(p.get('cpu_percent') or 0, 1)}
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

        for metric in THRESHOLDS.keys():
            value = stats.get(metric)
            if value is None:
                continue

            thresholds = _get_thresholds(machine_id, metric)
            key = (machine_id, metric)
            level = None
            below = thresholds.get('below', False)

            if below:
                if value <= thresholds['critical']:
                    level = 'critical'
                elif value <= thresholds['warning']:
                    level = 'warning'
            else:
                if value >= thresholds['critical']:
                    level = 'critical'
                elif value >= thresholds['warning']:
                    level = 'warning'

            if level:
                with self.lock:
                    self._breach_counts[key] = self._breach_counts.get(key, 0) + 1
                    count = self._breach_counts[key]

                sustained = METRIC_SUSTAINED.get(metric, SUSTAINED_CHECKS)
                if count >= sustained:
                    self._maybe_fire_alert(machine_id, metric, value, level, thresholds, stats, now)
            else:
                fired_at = None
                with self.lock:
                    self._breach_counts.pop(key, None)
                    if key in self._active_alerts:
                        fired_at = self._active_alerts.pop(key)
                if fired_at is not None:
                    duration = int(now - fired_at)
                    self._record_resolved(machine_id, metric, value, duration, now)

        self._evaluate_power_state(machine_id, stats, now)

    def _evaluate_power_state(self, machine_id, stats, now):
        """Alert when a machine switches to battery power (AC unplugged)."""
        battery_status = stats.get('battery_status')
        if not battery_status:
            return

        key = (machine_id, 'ac_power_lost')
        discharging = battery_status.lower() == 'discharging'

        if discharging:
            with self.lock:
                self._breach_counts[key] = self._breach_counts.get(key, 0) + 1
                count = self._breach_counts[key]

            if count >= AC_POWER_SUSTAINED:
                with self.lock:
                    last_fired = self._active_alerts.get(key, 0)
                    if (now - last_fired) < AC_POWER_COOLDOWN and key in self._active_alerts:
                        return
                    self._active_alerts[key] = now

                battery_pct = stats.get('battery_percent', '?')
                alert = {
                    'machine': machine_id,
                    'metric': 'ac_power_lost',
                    'value': battery_pct if isinstance(battery_pct, (int, float)) else 0,
                    'level': 'warning',
                    'threshold': 'AC',
                    'top_processes': [],
                    'timestamp': now,
                    'resolved': False,
                }
                with self.lock:
                    self.history.append(alert)
                self._save_history()
                self._send_discord(alert)
        else:
            with self.lock:
                self._breach_counts.pop(key, None)
                fired_at = self._active_alerts.pop(key, None)
            if fired_at is not None:
                duration = int(now - fired_at)
                self._record_resolved(machine_id, 'ac_power_lost', 0, duration, now)

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
            'battery_percent': 'Battery Low',
            'ac_power_lost': 'AC Power Lost',
        }
        metric_units = {
            'memory_percent': '%',
            'temp_c': '\u00b0C',
            'cpu_percent': '%',
            'battery_percent': '%',
            'ac_power_lost': '%',
        }

        metric_name = metric_labels.get(alert['metric'], alert['metric'])
        unit = metric_units.get(alert['metric'], '')
        machine = alert['machine']

        if alert.get('resolved'):
            duration = alert.get('duration_secs', 0)
            dur_str = f"{duration // 60}m {duration % 60}s" if duration >= 60 else f"{duration}s"
            if alert['metric'] == 'ac_power_lost':
                desc = f'AC power restored. Was on battery for {dur_str}.'
            else:
                desc = f'{metric_name} returned to normal: **{alert["value"]}{unit}**\nDuration: {dur_str}'
            embed = {
                'title': f'{machine} -- {metric_name} Resolved',
                'description': desc,
                'color': 0x34d399,  # green
                'timestamp': datetime.utcfromtimestamp(alert['timestamp']).isoformat(),
            }
            content = ''
        else:
            color = 0xf87171 if alert['level'] == 'critical' else 0xf59e0b  # red / amber

            if alert['metric'] == 'ac_power_lost':
                desc = f'Running on battery at **{alert["value"]}%**\nPlug in to prevent shutdown.'
            elif alert['metric'] == 'battery_percent':
                desc = f'**Battery**: {alert["value"]}% (threshold: {alert.get("threshold", "?")}{unit})\nPlug in immediately!'
            else:
                top_procs = alert.get('top_processes', [])
                proc_lines = '\n'.join(
                    f"`{p['name'][:20]:<20}` mem {p['mem']}% cpu {p['cpu']}%"
                    for p in top_procs
                ) if top_procs else 'N/A'
                desc = (
                    f'**{metric_name}**: {alert["value"]}{unit} (threshold: {alert.get("threshold", "?")}{unit})\n\n'
                    f'**Top Consumers:**\n{proc_lines}'
                )

            embed = {
                'title': f'{machine} -- {metric_name} {alert["level"].upper()}',
                'description': desc,
                'color': color,
                'timestamp': datetime.utcfromtimestamp(alert['timestamp']).isoformat(),
            }
            content = f'<@{DISCORD_USER_ID}>'

        payload = {
            'content': content,
            'embeds': [embed],
        }

        def _post():
            try:
                http_requests.post(self.webhook_url, json=payload, timeout=10)
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()

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
        """Persist alert history to disk (called from bg thread only)."""
        try:
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


class SecurityHealthMonitor:
    """Proactive health checks for critical security services.

    Catches silent failures that systemd OnFailure can't detect:
      * Panic-restart loops (Restart=always keeps unit "active" so OnFailure
        never fires, but the bouncer crashes every N minutes)
      * Stale LAPI pulls (bouncer running but auth broken / network down)
      * ipset drift (decisions exist in DB but missing from firewall ipset)
      * crowdsec.service quietly failed mid-Restart cycle

    Runs SSH probes against each watched host every CHECK_INTERVAL seconds and
    fires Discord alerts via the parent AlertEngine's webhook.
    """

    CHECK_INTERVAL = 60       # seconds between probes
    SUSTAINED_CHECKS = 2      # consecutive bad probes before alerting (~2 min)
    COOLDOWN_SECS = 1800      # 30 min between repeats for same issue
    PANIC_LOOKBACK = "10 min ago"
    LAST_PULL_MAX_AGE = 300   # bouncer pulls every 10s; >5 min = broken
    IPSET_DRIFT_TOLERANCE = 5 # tolerate small race between db & firewall

    # (machine_id, ssh_user, ssh_host)
    HOSTS = [
        ('noc-tux', 'noc', 'noc-tux'),
    ]

    def __init__(self, alert_engine):
        self._engine = alert_engine
        self._last_check = 0.0
        self._lock = threading.Lock()
        # {(machine, check_name): consecutive_breach_count}
        self._breach_counts = {}
        # {(machine, check_name): timestamp_fired}
        self._active_alerts = {}

    def maybe_check(self):
        """Throttled entry point. Call from background loop every iteration."""
        now = time.time()
        if now - self._last_check < self.CHECK_INTERVAL:
            return
        self._last_check = now
        for machine_id, ssh_user, ssh_host in self.HOSTS:
            try:
                self._check_host(machine_id, ssh_user, ssh_host)
            except Exception:
                # Never let monitor exceptions kill the loop
                pass

    def _check_host(self, machine_id, ssh_user, ssh_host):
        """Run a single combined SSH probe and evaluate each check."""
        probe = self._run_probe(ssh_user, ssh_host)
        if probe is None:
            return  # SSH itself failed; don't alert (could be transient network)

        now = time.time()

        # Check 1: crowdsec.service active
        self._eval_binary(
            machine_id, 'crowdsec_service',
            ok=(probe.get('crowdsec_active') == 'active'),
            failure_msg=f"crowdsec.service is {probe.get('crowdsec_active')}",
            now=now,
        )

        # Check 2: crowdsec-firewall-bouncer.service active
        self._eval_binary(
            machine_id, 'bouncer_service',
            ok=(probe.get('bouncer_active') == 'active'),
            failure_msg=f"crowdsec-firewall-bouncer.service is {probe.get('bouncer_active')}",
            now=now,
        )

        # Check 3: panic-restart loop detection
        panics = probe.get('panics', 0)
        self._eval_binary(
            machine_id, 'bouncer_panics',
            ok=(panics == 0),
            failure_msg=f"{panics} panic(s) in bouncer log over last 10 min (silent restart loop)",
            now=now,
        )

        # Check 4: bouncer LAPI pull recency
        last_pull_age = probe.get('last_pull_age')
        if last_pull_age is not None:
            self._eval_binary(
                machine_id, 'bouncer_stale_pull',
                ok=(last_pull_age <= self.LAST_PULL_MAX_AGE),
                failure_msg=f"bouncer hasn't pulled LAPI in {last_pull_age}s (auth/network broken)",
                now=now,
            )

        # Check 5: ipset drift (decisions in DB but missing from firewall)
        decisions_count = probe.get('decisions_count')
        ipset_count = probe.get('ipset_count')
        if decisions_count is not None and ipset_count is not None:
            drift = decisions_count - ipset_count
            self._eval_binary(
                machine_id, 'ipset_drift',
                ok=(drift <= self.IPSET_DRIFT_TOLERANCE),
                failure_msg=(
                    f"firewall ipset missing {drift} bans "
                    f"(decisions={decisions_count}, ipset={ipset_count})"
                ),
                now=now,
            )

    # Path to probe script on the remote host (in the homelab repo)
    REMOTE_PROBE_PATH = "/home/noc/noc-homelab/linux/scripts/security-health-probe.py"

    def _run_probe(self, ssh_user, ssh_host):
        """SSH-invoke the remote probe script, return parsed JSON dict or None.

        Returns None on any SSH/parse failure -- we never alert on probe
        failure itself, only on bad findings, to avoid noise from transient
        network blips.
        """
        try:
            result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=no',
                 f'{ssh_user}@{ssh_host}', 'python3', self.REMOTE_PROBE_PATH],
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode != 0:
                return None
            # Pick the last line that looks like JSON (script may emit
            # deprecation warnings to stderr; stdout should be one JSON line)
            for line in reversed(result.stdout.strip().splitlines()):
                line = line.strip()
                if line.startswith('{'):
                    return json.loads(line)
            return None
        except Exception:
            return None

    def _eval_binary(self, machine_id, check_name, ok, failure_msg, now):
        """Evaluate a binary (ok/not-ok) check, manage breach counts, fire alert."""
        key = (machine_id, check_name)
        if ok:
            with self._lock:
                self._breach_counts.pop(key, None)
                fired_at = self._active_alerts.pop(key, None)
            if fired_at is not None:
                self._send_security_alert(
                    machine_id, check_name,
                    f"Resolved after {int(now - fired_at)}s",
                    now, resolved=True,
                )
            return

        # Currently breaching
        with self._lock:
            self._breach_counts[key] = self._breach_counts.get(key, 0) + 1
            count = self._breach_counts[key]

        if count < self.SUSTAINED_CHECKS:
            return  # not sustained yet

        with self._lock:
            last_fired = self._active_alerts.get(key, 0)
            if (now - last_fired) < self.COOLDOWN_SECS and key in self._active_alerts:
                return  # in cooldown
            self._active_alerts[key] = now

        self._send_security_alert(machine_id, check_name, failure_msg, now)

    def _send_security_alert(self, machine_id, check_name, failure_msg, now, resolved=False):
        """Send a security-themed Discord embed via the parent engine's webhook."""
        webhook = getattr(self._engine, 'webhook_url', None)
        if not webhook:
            return

        labels = {
            'crowdsec_service':   'CrowdSec Agent Down',
            'bouncer_service':    'Firewall Bouncer Down',
            'bouncer_panics':     'Bouncer Panic Loop',
            'bouncer_stale_pull': 'Bouncer LAPI Stale',
            'ipset_drift':        'Firewall ipset Drift',
        }
        label = labels.get(check_name, check_name)
        if resolved:
            title = f"{machine_id} -- {label} Resolved"
            color = 0x34d399  # green
            content = ''
        else:
            title = f"{machine_id} -- {label}"
            color = 0xef4444  # red
            content = f'<@{DISCORD_USER_ID}>'

        embed = {
            'title': title,
            'description': (
                f"**{failure_msg}**\n\n"
                f"**Check:** `{check_name}`"
            ),
            'color': color,
            'timestamp': datetime.utcfromtimestamp(now).isoformat(),
            'footer': {'text': 'SecurityHealthMonitor -- noc-homelab'},
        }
        payload = {'content': content, 'embeds': [embed]}

        def _post():
            try:
                http_requests.post(webhook, json=payload, timeout=10)
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()

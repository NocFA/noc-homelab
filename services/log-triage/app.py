"""
Log triage webhook service.

Consumes CrowdSec alerts, fetches surrounding log context from Loki, asks the
local MLX LLM on noc-claw to produce a one-paragraph human summary, and posts
the result to Discord. Runs as a LaunchAgent on noc-claw so it's co-located
with the MLX server (no Tailscale round-trip for inference).

Endpoints
---------
POST /alert     — CrowdSec HTTP notifier target
GET  /health    — readiness probe
GET  /          — index

Auth
----
If AUTH_TOKEN is set, inbound requests must carry matching
`X-Auth-Token` header. Keep CrowdSec notifier headers in sync.

Rate limiting
-------------
Same alert key (scenario, source IP) is ignored for DEDUPE_WINDOW seconds.
Total summaries capped at MAX_PER_HOUR to guard against runaway LLM spend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Config (env-driven, see .env.example)
# ---------------------------------------------------------------------------

MLX_URL         = os.environ.get("MLX_URL", "http://localhost:8181/v1/chat/completions")
MLX_MODEL       = os.environ.get("MLX_MODEL", "mlx-community/gemma-3-12b-it-4bit")
MLX_RETRY_DELAY = float(os.environ.get("MLX_RETRY_DELAY_SECONDS", "10"))
LOKI_URL        = os.environ.get("LOKI_URL", "http://noc-tux:3100")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "").strip()
AUTH_TOKEN      = os.environ.get("AUTH_TOKEN", "").strip()
LISTEN_PORT     = int(os.environ.get("LISTEN_PORT", "8182"))
LISTEN_HOST     = os.environ.get("LISTEN_HOST", "0.0.0.0")
DEDUPE_WINDOW   = int(os.environ.get("DEDUPE_WINDOW_SECONDS", "600"))  # 10 min
MAX_PER_HOUR    = int(os.environ.get("MAX_PER_HOUR", "30"))
LOG_LEVEL       = os.environ.get("LOG_LEVEL", "INFO").upper()
# Displayed as the "Mode" field in Discord. Override when the bouncer
# posture changes (e.g. "active (firewall-bouncer)" once enforcement is on).
MODE_LABEL      = os.environ.get("MODE_LABEL", "active (firewall-bouncer)")

# mlx_lm.server serializes requests but the underlying Metal runtime can
# still SIGABRT from mlx::core::gpu::check_error when two inference calls
# land on the GPU concurrently (observed on M4 16GB, gemma-3-12b-4bit).
# Gate every MLX call through a single-slot semaphore at the client side.
_MLX_LOCK = asyncio.Semaphore(1)

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("log-triage")

# ---------------------------------------------------------------------------
# State (process-local)
# ---------------------------------------------------------------------------


class _State:
    """Lightweight in-memory dedupe + rate limit tracker."""

    def __init__(self) -> None:
        self._seen: dict[str, float] = {}
        self._hour_window: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def should_process(self, key: str) -> tuple[bool, str]:
        async with self._lock:
            now = time.time()

            # Purge hour window
            while self._hour_window and self._hour_window[0] < now - 3600:
                self._hour_window.popleft()

            if len(self._hour_window) >= MAX_PER_HOUR:
                return False, f"rate_limited (> {MAX_PER_HOUR}/h)"

            seen_at = self._seen.get(key, 0)
            if now - seen_at < DEDUPE_WINDOW:
                age = int(now - seen_at)
                return False, f"deduped (same key seen {age}s ago)"

            self._seen[key] = now
            self._hour_window.append(now)

            # Periodically drop old dedupe keys
            for k, ts in list(self._seen.items()):
                if now - ts > DEDUPE_WINDOW * 4:
                    del self._seen[k]

            return True, "ok"


state = _State()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
    log.info("triage service up — MLX=%s Loki=%s discord=%s",
             MLX_URL, LOKI_URL, "configured" if DISCORD_WEBHOOK else "MISSING")
    yield
    await app.state.http.aclose()


app = FastAPI(title="homelab log-triage", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_http_events(alert: dict[str, Any]) -> list[dict[str, str]]:
    """Pull HTTP request details from CrowdSec event meta.

    Returns a list of dicts like:
      {"verb": "GET", "path": "/.env", "status": "404",
       "target": "84.203.199.55", "user_agent": "...", "timestamp": "..."}

    The CrowdSec notifier template (http_triage.yaml) flattens meta into a
    plain {key: value} dict. As a fallback we still handle the native
    [{Key, Value}, ...] shape in case the template is ever changed.
    """
    events = alert.get("events") or []
    out: list[dict[str, str]] = []
    for e in events:
        meta = e.get("meta") or {}
        if isinstance(meta, list):  # fallback: native CrowdSec shape
            meta = {
                (m.get("key") or m.get("Key")): (m.get("value") or m.get("Value"))
                for m in meta if isinstance(m, dict)
            }
        if not isinstance(meta, dict):
            continue
        # Only keep http log-type events — scenarios like ssh-bf emit other shapes
        log_type = str(meta.get("log_type") or "")
        if meta.get("service") != "http" and not log_type.startswith("http"):
            continue
        out.append({
            "verb":       str(meta.get("http_verb") or "?"),
            "path":       str(meta.get("http_path") or "?"),
            "status":     str(meta.get("http_status") or "?"),
            "target":     str(meta.get("target_fqdn") or ""),
            "user_agent": str(meta.get("http_user_agent") or ""),
            "timestamp":  str(e.get("timestamp") or ""),
        })
    return out


def format_events_for_discord(events: list[dict[str, str]], limit: int = 10) -> str:
    """Render HTTP events as a compact multi-line Discord field value.

    Discord embed field values are capped at 1024 chars — we truncate paths
    at 60 chars each and cut the list at `limit`, with a `+N more` suffix.
    """
    if not events:
        return ""
    shown = events[:limit]
    extra = len(events) - len(shown)
    lines: list[str] = []
    for e in shown:
        path = e["path"]
        if len(path) > 60:
            path = path[:57] + "..."
        lines.append(f"`{e['verb']}` `{path}` → {e['status']}")
    out = "\n".join(lines)
    if extra > 0:
        out += f"\n_+{extra} more request(s)_"
    return out[:1020]


def format_events_for_llm(events: list[dict[str, str]], limit: int = 25) -> str:
    """One line per event, stable format for the LLM prompt."""
    if not events:
        return ""
    lines = []
    for e in events[:limit]:
        tgt = f" on {e['target']}" if e["target"] else ""
        lines.append(f"  {e['verb']} {e['path']} -> {e['status']}{tgt}")
    if len(events) > limit:
        lines.append(f"  ...+{len(events) - limit} more")
    return "\n".join(lines)


async def fetch_loki_context(client: httpx.AsyncClient,
                             source_ip: str,
                             start_ts: int | None = None,
                             window_seconds: int = 600,
                             limit: int = 40) -> list[str]:
    """Pull recent log lines mentioning the attacker IP for LLM context."""
    if start_ts is None:
        start_ts = int(time.time()) - window_seconds
    end_ts = start_ts + window_seconds * 2  # +/- window around the event
    params = {
        "query": f'{{machine=~".+"}} |= "{source_ip}"',
        "start": f"{start_ts}000000000",
        "end":   f"{end_ts}000000000",
        "limit": str(limit),
        "direction": "backward",
    }
    try:
        r = await client.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
        r.raise_for_status()
        data = r.json().get("data", {}).get("result", [])
        lines: list[tuple[int, str, dict]] = []
        for stream in data:
            labels = stream.get("stream", {})
            for ts, line in stream.get("values", []):
                lines.append((int(ts), line, labels))
        lines.sort(key=lambda x: x[0])
        # Compact form for the LLM prompt
        return [
            f"[{labels.get('machine','?')}:{labels.get('job','?')}] {line.strip()[:280]}"
            for _, line, labels in lines[-limit:]
        ]
    except Exception as exc:
        log.warning("Loki fetch failed for %s: %s", source_ip, exc)
        return []


async def summarize(client: httpx.AsyncClient,
                    scenario: str,
                    source_ip: str,
                    source_cn: str,
                    count: int,
                    duration: str,
                    log_lines: list[str],
                    events: list[dict[str, str]] | None = None) -> str:
    """Ask the MLX model for a one-paragraph incident summary."""
    system = (
        "You are a security-ops triage assistant on a home lab. "
        "Given a CrowdSec alert and the surrounding log lines, write a single "
        "terse paragraph (3-5 sentences) that tells a human: what the attacker "
        "appears to be doing, which service is exposed, whether this looks like "
        "a known scanner pattern (e.g. Mirai, SSH credential stuffing, WP-scan), "
        "and whether the homelab's existing protection is sufficient. No "
        "markdown, no bullet points, no questions, no greetings. Plain prose."
    )
    ctx = "\n".join(log_lines[-30:]) or "(no matching log lines found in Loki)"
    events_block = format_events_for_llm(events or [])
    if events_block:
        user = (
            f"Alert: scenario={scenario}, source_ip={source_ip} ({source_cn}), "
            f"events={count}, ban_duration={duration}\n\n"
            f"Triggering requests (from CrowdSec, primary evidence):\n{events_block}\n\n"
            f"Surrounding log lines mentioning that IP (may include unrelated noise):\n{ctx}"
        )
    else:
        user = (
            f"Alert: scenario={scenario}, source_ip={source_ip} ({source_cn}), "
            f"events={count}, ban_duration={duration}\n\n"
            f"Recent log lines mentioning that IP:\n{ctx}"
        )
    body = {
        "model": MLX_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 350,
    }
    # Serialize MLX calls + give the KeepAlive-restarted server one retry
    # if it crashed mid-response (httpx.RemoteProtocolError / ReadError).
    async with _MLX_LOCK:
        for attempt in (1, 2):
            try:
                r = await client.post(MLX_URL, json=body, timeout=60.0)
                r.raise_for_status()
                data = r.json()
                msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return msg.strip() or "(LLM returned empty summary)"
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError) as exc:
                if attempt == 1:
                    log.warning("MLX call failed (%s) on attempt 1, "
                                "waiting %.0fs for mlx-server restart",
                                exc.__class__.__name__, MLX_RETRY_DELAY)
                    await asyncio.sleep(MLX_RETRY_DELAY)
                    continue
                log.warning("MLX summarize failed after retry: %s", exc)
                return f"(LLM summary unavailable: {exc.__class__.__name__})"
            except Exception as exc:
                log.warning("MLX summarize failed: %s", exc)
                return f"(LLM summary unavailable: {exc.__class__.__name__})"
    # unreachable, but satisfies type-checkers
    return "(LLM summary unavailable: loop_exhausted)"


async def post_discord(client: httpx.AsyncClient,
                       scenario: str,
                       source_ip: str,
                       source_cn: str,
                       count: int,
                       duration: str,
                       summary: str,
                       events: list[dict[str, str]] | None = None,
                       mode_label: str | None = None) -> None:
    mode_label = mode_label or MODE_LABEL
    if not DISCORD_WEBHOOK:
        log.info("DISCORD_WEBHOOK unset, skipping post")
        return
    fields: list[dict[str, Any]] = [
        {"name": "Scenario",     "value": f"`{scenario}`",      "inline": True},
        {"name": "Origin",       "value": source_cn or "??",    "inline": True},
        {"name": "Events",       "value": str(count),           "inline": True},
        {"name": "Ban duration", "value": duration or "?",      "inline": True},
        {"name": "Source IP",    "value": f"`{source_ip}`",     "inline": True},
        {"name": "Mode",         "value": mode_label,           "inline": True},
    ]
    # Paths probed: show actual URLs from CrowdSec event meta when available.
    paths_block = format_events_for_discord(events or [])
    if paths_block:
        # Target FQDN is usually constant across events; surface it once if so.
        targets = {e["target"] for e in (events or []) if e.get("target")}
        if len(targets) == 1:
            fields.append({"name": "Target", "value": f"`{next(iter(targets))}`", "inline": False})
        fields.append({"name": "Paths probed", "value": paths_block, "inline": False})
    embed = {
        "title": f"CrowdSec + LLM triage — {source_ip}",
        "description": summary[:4000],
        "color": 15105570,  # amber
        "fields": fields,
        "footer": {"text": f"noc-claw · {MLX_MODEL}"},
    }
    payload = {"username": "Log-Triage", "embeds": [embed]}
    try:
        r = await client.post(DISCORD_WEBHOOK, json=payload, timeout=15.0)
        r.raise_for_status()
    except Exception as exc:
        log.warning("Discord post failed: %s", exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
async def index() -> dict[str, str]:
    return {"service": "homelab log-triage", "mlx_model": MLX_MODEL}


@app.get("/health")
async def health(req: Request) -> dict[str, Any]:
    client: httpx.AsyncClient = req.app.state.http
    checks: dict[str, Any] = {}
    try:
        r = await client.get(f"{LOKI_URL}/ready", timeout=3.0)
        checks["loki"] = {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as exc:
        checks["loki"] = {"ok": False, "error": str(exc)}
    try:
        r = await client.get(MLX_URL.replace("/v1/chat/completions", "/v1/models"), timeout=3.0)
        checks["mlx"] = {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as exc:
        checks["mlx"] = {"ok": False, "error": str(exc)}
    checks["discord_configured"] = bool(DISCORD_WEBHOOK)
    return {"checks": checks}


async def _process_alert(client: httpx.AsyncClient, a: dict[str, Any]) -> None:
    """Background-task worker: hydrate one CrowdSec alert, summarize, post."""
    source_ip = (a.get("source") or {}).get("ip", "unknown")
    source_cn = (a.get("source") or {}).get("cn", "") or ""
    scenario  = a.get("scenario") or (a.get("labels", {}).get("scenario") or "unknown")
    count     = int(a.get("events_count", 0) or 0)
    decisions = a.get("decisions") or []
    duration  = (decisions[0].get("duration") if decisions else "") or ""

    key = f"{scenario}::{source_ip}"
    ok, reason = await state.should_process(key)
    if not ok:
        log.info("skip %s (%s)", key, reason)
        return

    http_events = extract_http_events(a)
    log.info("triage %s events=%d http_events=%d scenario=%s",
             source_ip, count, len(http_events), scenario)
    try:
        ctx = await fetch_loki_context(client, source_ip)
        summary = await summarize(client, scenario, source_ip, source_cn,
                                   count, duration, ctx, http_events)
        await post_discord(client, scenario, source_ip, source_cn,
                           count, duration, summary, http_events)
        log.info("triage done %s ctx=%d http=%d sum=%d",
                 source_ip, len(ctx), len(http_events), len(summary))
    except Exception as exc:  # never let a background failure leak
        log.warning("triage failed for %s: %s", source_ip, exc)


@app.post("/alert", status_code=202)
async def alert_handler(req: Request,
                        bg: BackgroundTasks,
                        x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    if AUTH_TOKEN and x_auth_token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="bad auth token")

    # CrowdSec HTTP notifier sends a JSON array of alert objects.
    # Handle both array and object (for manual probes).
    try:
        raw = await req.body()
        payload = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON")

    if isinstance(payload, dict):
        alerts = [payload]
    elif isinstance(payload, list):
        alerts = payload
    else:
        raise HTTPException(status_code=400, detail="payload must be array or object")

    # Fire-and-forget: CrowdSec (or Loki ruler, etc.) gets an immediate 202
    # so its own retry/timeout loop never blocks on MLX inference.
    client: httpx.AsyncClient = req.app.state.http
    queued: list[str] = []
    for a in alerts:
        bg.add_task(_process_alert, client, a)
        source_ip = (a.get("source") or {}).get("ip", "?")
        scenario = a.get("scenario", "?")
        queued.append(f"{scenario}::{source_ip}")

    return {"ok": True, "queued": queued}


# ---------------------------------------------------------------------------
# Entrypoint (uvicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=LISTEN_HOST, port=LISTEN_PORT,
                log_level=LOG_LEVEL.lower(), access_log=False)

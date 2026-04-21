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
LOKI_URL        = os.environ.get("LOKI_URL", "http://noc-tux:3100")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "").strip()
AUTH_TOKEN      = os.environ.get("AUTH_TOKEN", "").strip()
LISTEN_PORT     = int(os.environ.get("LISTEN_PORT", "8182"))
LISTEN_HOST     = os.environ.get("LISTEN_HOST", "0.0.0.0")
DEDUPE_WINDOW   = int(os.environ.get("DEDUPE_WINDOW_SECONDS", "600"))  # 10 min
MAX_PER_HOUR    = int(os.environ.get("MAX_PER_HOUR", "30"))
LOG_LEVEL       = os.environ.get("LOG_LEVEL", "INFO").upper()

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
                    log_lines: list[str]) -> str:
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
    try:
        r = await client.post(MLX_URL, json=body, timeout=60.0)
        r.raise_for_status()
        data = r.json()
        msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return msg.strip() or "(LLM returned empty summary)"
    except Exception as exc:
        log.warning("MLX summarize failed: %s", exc)
        return f"(LLM summary unavailable: {exc.__class__.__name__})"


async def post_discord(client: httpx.AsyncClient,
                       scenario: str,
                       source_ip: str,
                       source_cn: str,
                       count: int,
                       duration: str,
                       summary: str) -> None:
    if not DISCORD_WEBHOOK:
        log.info("DISCORD_WEBHOOK unset, skipping post")
        return
    embed = {
        "title": f"CrowdSec + LLM triage — {source_ip}",
        "description": summary[:4000],
        "color": 15105570,  # amber
        "fields": [
            {"name": "Scenario",     "value": f"`{scenario}`",      "inline": True},
            {"name": "Origin",       "value": source_cn or "??",    "inline": True},
            {"name": "Events",       "value": str(count),           "inline": True},
            {"name": "Ban duration", "value": duration or "?",      "inline": True},
            {"name": "Source IP",    "value": f"`{source_ip}`",     "inline": True},
            {"name": "Mode",         "value": "observation (no bouncer)", "inline": True},
        ],
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

    log.info("triage %s events=%d scenario=%s", source_ip, count, scenario)
    try:
        ctx = await fetch_loki_context(client, source_ip)
        summary = await summarize(client, scenario, source_ip, source_cn,
                                   count, duration, ctx)
        await post_discord(client, scenario, source_ip, source_cn,
                           count, duration, summary)
        log.info("triage done %s ctx=%d sum=%d",
                 source_ip, len(ctx), len(summary))
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

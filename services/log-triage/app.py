"""
Log triage webhook service.

Consumes CrowdSec alert batches, groups alerts by source IP, fetches
surrounding log context from Loki, asks the local MLX LLM on noc-claw to
produce a single structured verdict per IP, and posts one combined Discord
embed per IP. Runs as a LaunchAgent on noc-claw so it's co-located with the
MLX server (no Tailscale round-trip for inference).

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
Same source IP is ignored for DEDUPE_WINDOW seconds (per-IP, not
per-scenario — multi-scenario scans coalesce into one post).
Total summaries capped at MAX_PER_HOUR to guard against runaway LLM spend.

Coalescing
----------
A single CrowdSec notifier batch (group_wait=60s, group_threshold=50)
typically contains every scenario that fired for an attack. We group the
batch by source IP and emit ONE embed per IP, listing every scenario, the
longest ban duration, and a combined LLM verdict over the union of events.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
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

MLX_URL             = os.environ.get("MLX_URL", "http://localhost:8181/v1/chat/completions")
MLX_MODEL           = os.environ.get("MLX_MODEL", "mlx-community/gemma-3-12b-it-4bit")
MLX_RETRY_DELAY     = float(os.environ.get("MLX_RETRY_DELAY_SECONDS", "10"))
# 60s was too tight for fat-context prompts: gemma-3-12b-4bit on M4 16GB takes
# ~50s just to do prompt processing on ~2.8k tokens, then has to actually
# generate a response. 180s gives reliable headroom; the events_block + ctx
# caps below also keep the prompt small enough for the typical case.
MLX_REQUEST_TIMEOUT = float(os.environ.get("MLX_REQUEST_TIMEOUT_SECONDS", "180"))
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
    # Default client timeout is the floor — per-request overrides set higher
    # values for MLX. Keep the default at 30s so non-MLX calls (Loki, Discord)
    # fail fast.
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
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


# ---------------------------------------------------------------------------
# Scenario → Loki job allowlist
# ---------------------------------------------------------------------------
#
# Loki has the following `job` labels (from alloy configs on noc-tux):
#   auth      — sshd / sudo / pam events (auth.log via journal pipeline)
#   caddy     — caddy-websites access logs
#   docker    — container stdout/stderr (matrix excluded)
#   homelab   — homelab-agent + dashboard journal (OUR OWN AUTOMATION)
#   journal   — generic systemd journal
#   synapse   — Matrix Synapse server log
#   system    — syslog
#   traefik   — Traefik access log (Matrix proxy)
#
# Different CrowdSec scenarios trigger on completely different log sources, so
# pulling everything that mentions the attacker IP drowns the prompt in
# unrelated noise (and is the root cause of the LLM weaving false narratives
# in noc-homelab-1fq). For each scenario family we pin to the jobs that could
# plausibly have produced the trigger.
#
# `job=homelab` is ALWAYS dropped — it's our dashboard polling agents over
# Tailscale, never the attacker.

_HTTP_JOBS    = ("traefik", "caddy", "synapse", "docker")
_SSH_JOBS     = ("auth",)
_GENERIC_JOBS = ("traefik", "caddy", "auth", "journal", "synapse", "docker", "system")


def jobs_for_scenario(scenario: str) -> tuple[str, ...]:
    """Return the Loki job allowlist appropriate for this CrowdSec scenario."""
    s = (scenario or "").lower()
    # Anything web-shaped: HTTP CVEs, web crawlers, LFI/RFI, sensitive files
    if any(tok in s for tok in ("http", "wp-", "f5-", "cve", "nuclei",
                                  "wordpress", "phpmyadmin", "joomla", "lfi",
                                  "rfi", "shellshock", "log4j", "spring",
                                  "exchange", "fortinet", "vsphere")):
        return _HTTP_JOBS
    if any(tok in s for tok in ("ssh", "auth-bf", "credential", "pam")):
        return _SSH_JOBS
    return _GENERIC_JOBS


# Lines we never want to feed the LLM, even when they match the IP.
# Each tuple: (substring, reason). Substring match is case-sensitive on the
# raw log line.
_LINE_DROP_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Accepted publickey",      "successful pubkey auth (legit automation)"),
    ("Accepted password for noc", "interactive shell from operator (rare)"),
    ("session opened for user noc", "operator session"),
    ("homelab-agent",           "dashboard polling our own agent"),
    ("/api/agent/",             "dashboard polling agent endpoints"),
    ("/api/observability/",     "dashboard polling observability"),
    ("/api/status",             "dashboard polling status"),
)


_DEDUP_DIGIT_RUN = re.compile(r"\d+")
_DEDUP_QUOTED    = re.compile(r'"[^"]*"')


def _dedup_signature(line: str) -> str:
    """Collapse a log line to a fingerprint for near-duplicate detection.

    Strips the `[machine:job]` prefix, replaces digit runs with `#` and quoted
    strings with `"…"`. http-probing scanners often emit dozens of access lines
    that differ only by timestamp and request ID — fingerprinting collapses
    them so the LLM doesn't see the same shape 30 times.
    """
    body = line.split("] ", 1)[-1] if "] " in line else line
    body = _DEDUP_QUOTED.sub('"_"', body)
    body = _DEDUP_DIGIT_RUN.sub("#", body)
    return body.strip()


def filter_loki_lines(streams: list[dict[str, Any]],
                       allowed_jobs: tuple[str, ...],
                       limit: int,
                       max_per_signature: int = 2) -> list[str]:
    """Apply scenario-aware job allowlist, drop list, and near-dup collapse.

    Returns formatted prompt-ready lines, newest last. Always drops
    `job=homelab` (our own automation noise) regardless of allowlist.
    Near-duplicate lines (same signature after digit/quote stripping) are
    capped at `max_per_signature` occurrences to avoid feeding the LLM a
    wall of nearly-identical traefik 404s.
    """
    rows: list[tuple[int, str, dict[str, Any]]] = []
    for stream in streams:
        labels = stream.get("stream", {}) or {}
        job = str(labels.get("job", ""))
        if job == "homelab":
            continue  # never useful — that's our agent + dashboard
        if allowed_jobs and job and job not in allowed_jobs:
            continue
        for ts, line in stream.get("values", []) or []:
            text = str(line or "")
            if any(pat in text for pat, _ in _LINE_DROP_PATTERNS):
                continue
            try:
                rows.append((int(ts), text, labels))
            except (TypeError, ValueError):
                continue
    rows.sort(key=lambda x: x[0])
    formatted = [
        f"[{labels.get('machine','?')}:{labels.get('job','?')}] {text.strip()[:240]}"
        for _, text, labels in rows
    ]
    # Newest-last; walk newest-first for dedup so the most-recent example of a
    # repeated signature is preserved, then reverse.
    seen: dict[str, int] = {}
    kept: list[str] = []
    for line in reversed(formatted):
        sig = _dedup_signature(line)
        if seen.get(sig, 0) >= max_per_signature:
            continue
        seen[sig] = seen.get(sig, 0) + 1
        kept.append(line)
        if len(kept) >= limit:
            break
    kept.reverse()
    return kept


async def fetch_loki_context(client: httpx.AsyncClient,
                             source_ip: str,
                             allowed_jobs: tuple[str, ...] = (),
                             start_ts: int | None = None,
                             window_seconds: int = 600,
                             limit: int = 40) -> list[str]:
    """Pull recent log lines mentioning the attacker IP, filtered by job allowlist.

    Caller computes the allowlist from the union of jobs across every
    scenario in the IP group (see _process_ip_group). Empty allowlist falls
    back to a global query (any machine, any job) — only useful for ad-hoc
    manual probes.
    """
    if start_ts is None:
        start_ts = int(time.time()) - window_seconds
    end_ts = start_ts + window_seconds * 2  # +/- window around the event

    # Push the job filter into the LogQL query when we have one — avoids
    # transferring streams we'd just drop client-side. The matcher uses
    # regex anchoring so "auth" doesn't match "authelia".
    if allowed_jobs:
        job_re = "|".join(allowed_jobs)
        query = f'{{job=~"^({job_re})$"}} |= "{source_ip}"'
    else:
        query = f'{{machine=~".+"}} |= "{source_ip}"'

    params = {
        "query": query,
        "start": f"{start_ts}000000000",
        "end":   f"{end_ts}000000000",
        "limit": str(limit * 2),  # fetch extra to cover post-filter drops
        "direction": "backward",
    }
    try:
        r = await client.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
        r.raise_for_status()
        data = r.json().get("data", {}).get("result", [])
        return filter_loki_lines(data, allowed_jobs, limit)
    except Exception as exc:
        log.warning("Loki fetch failed for %s: %s", source_ip, exc)
        return []


# ---------------------------------------------------------------------------
# Prompt + structured output (anti-confabulation)
# ---------------------------------------------------------------------------

# Topology block — the LLM has no way of knowing this otherwise, and most of
# the false narratives in the wild traced back to the model misreading
# Tailscale/CF-tunnel proxy hops as attacker activity. Keep this terse;
# every token is in the context window for every alert.
_TOPOLOGY = (
    "HOMELAB TOPOLOGY (use this to interpret log entries):\n"
    "- Tailscale CGNAT range 100.64.0.0/10 is our private mesh — any IP in "
    "that range is one of our own machines (noc-local, noc-claw, noc-tux, "
    "noc-baguette), NEVER an attacker.\n"
    "- LAN range 192.168.0.0/16 is local devices — also not attackers.\n"
    "- Cloudflare tunnels terminate on noc-local; tunnelled traffic to "
    "games.nocfa.net / matrix.nocfa.net / element.nocfa.net / api.nocfa.net "
    "appears in nginx/caddy/traefik with the CF edge IP, NOT the attacker's IP.\n"
    "- Our dashboard polls `/api/agent/*`, `/api/observability/*`, `/api/status` "
    "every 10s over Tailscale; those are NOT probes.\n"
    "- SSH `Accepted publickey` from a Tailscale IP for user `noc` is "
    "automation (already filtered out, but flag if you see it).\n"
    "- The user `noc` is the legitimate operator on every host."
)

_OUTPUT_CONTRACT = (
    "OUTPUT CONTRACT — emit a SINGLE JSON object, no prose, no code fences, "
    "no preamble. Schema:\n"
    "{\n"
    '  "verdict": "<one short sentence: what the attacker actually did, '
    'based ONLY on the Triggering Requests section>",\n'
    '  "intent": "<scanner|cve-probe|brute-force|credential-stuffing|'
    'recon|exploit-attempt|unknown>",\n'
    '  "exposure": "<none|low|medium|high>",\n'
    '  "real_attacker_ip": "<the alert source_ip, OR \'masked by proxy\' '
    'if you only see Cloudflare/Tailscale IPs in the logs>",\n'
    '  "internal_noise": <true|false — true ONLY if the triggering events '
    'all look like our own automation hitting us>,\n'
    '  "notes": "<at most one short caveat, or empty string>"\n'
    "}\n\n"
    "RULES:\n"
    "1. Base `verdict` and `intent` ONLY on the Triggering Requests block. "
    "The Surrounding Logs block may contain unrelated traffic — use it for "
    "context but DO NOT invent a narrative that connects unrelated events.\n"
    "2. If the triggering requests are a single 404 to one path, say so — "
    "do NOT escalate to 'sustained brute-force campaign'.\n"
    "3. If you are not sure, set `intent`='unknown' and put your "
    "uncertainty in `notes`. Confabulating is worse than admitting "
    "uncertainty.\n"
    "4. NEVER claim SSH brute-force unless the Triggering Requests "
    "explicitly include sshd Failed/Invalid lines.\n"
    "5. `exposure` rules: if every HTTP status in Triggering Requests is 4xx "
    "or 5xx, `exposure` MUST be `none` (the request was rejected). `low` "
    "is for 200/3xx on benign endpoints (favicon, static assets). "
    "`medium` is 200 on a recognised admin/login endpoint. `high` is only "
    "for evidence of a successful exploit (e.g. 200 on a known CVE path "
    "with a payload in the URL)."
)


def _strip_code_fences(s: str) -> str:
    """Strip ```json ... ``` wrappers some models emit despite instructions."""
    s = s.strip()
    if s.startswith("```"):
        # remove first fence line
        s = s.split("\n", 1)[1] if "\n" in s else s.lstrip("`")
        # remove trailing fence
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def parse_verdict(raw: str) -> dict[str, Any] | None:
    """Try to parse the LLM's JSON verdict; return None if unparseable."""
    if not raw:
        return None
    try:
        return json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        # Some models prepend a sentence before the JSON. Try to find a
        # `{...}` block inside the response as a last-ditch recovery.
        s = _strip_code_fences(raw)
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(s[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None


async def summarize(client: httpx.AsyncClient,
                    scenarios: list[str],
                    source_ip: str,
                    source_cn: str,
                    count: int,
                    duration: str,
                    log_lines: list[str],
                    events: list[dict[str, str]] | None = None) -> str:
    """Ask the MLX model for a structured incident verdict (JSON string).

    `scenarios` is a list (possibly with one element) of every CrowdSec
    scenario that fired for this IP in the current batch. Returns the raw
    response text — caller uses parse_verdict() to extract fields and falls
    back to rendering the raw text if parsing fails.
    """
    system = (
        "You are a security-ops triage assistant on a home lab. Your job "
        "is to interpret a CrowdSec alert WITHOUT inventing details that "
        "the evidence does not directly support.\n\n"
        + _TOPOLOGY
        + "\n\n"
        + _OUTPUT_CONTRACT
    )
    # Hard caps on the surrounding-logs context. Was previously [-30:] with no
    # byte budget, which let http-probing alerts balloon the prompt past 2.8k
    # tokens — slow enough on M4 16GB gemma-3-12b-4bit to ReadTimeout at 60s.
    # Keep this aggressive: surrounding logs are CONTEXT ONLY, the LLM should
    # base the verdict on the events_block (already separately capped).
    ctx_lines = log_lines[-15:]
    ctx_total = 0
    ctx_kept: list[str] = []
    for line in ctx_lines:
        if ctx_total + len(line) > 3500:
            ctx_kept.append(f"... ({len(ctx_lines) - len(ctx_kept)} more line(s) truncated)")
            break
        ctx_kept.append(line)
        ctx_total += len(line) + 1
    ctx = "\n".join(ctx_kept) or "(no matching log lines found in Loki)"
    events_block = format_events_for_llm(events or [])
    scenarios_str = ", ".join(scenarios) if scenarios else "unknown"
    header = (
        f"Alert: scenarios=[{scenarios_str}], source_ip={source_ip} "
        f"({source_cn or '??'}), total_events={count}, "
        f"ban_duration={duration or '?'}"
    )
    if len(scenarios) > 1:
        header += (
            f"\n\nNOTE: multiple scenarios fired for this single IP in the "
            f"same window — treat them as one coordinated scan."
        )
    if events_block:
        user = (
            f"{header}\n\n"
            f"=== Triggering Requests (PRIMARY EVIDENCE — base your verdict on these) ===\n"
            f"{events_block}\n\n"
            f"=== Surrounding Logs (CONTEXT ONLY — may include unrelated noise) ===\n"
            f"{ctx}\n\n"
            f"Now emit the JSON verdict per the OUTPUT CONTRACT."
        )
    else:
        user = (
            f"{header}\n\n"
            f"=== Triggering Requests ===\n"
            f"(none — CrowdSec did not attach HTTP event meta; this may be "
            f"an ssh, network, or other non-http scenario)\n\n"
            f"=== Surrounding Logs (CONTEXT ONLY) ===\n"
            f"{ctx}\n\n"
            f"Now emit the JSON verdict per the OUTPUT CONTRACT."
        )
    body = {
        "model": MLX_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        # JSON-mode hint — mlx_lm.server accepts this even though enforcement
        # is partial; combined with the OUTPUT CONTRACT it lifts adherence
        # noticeably (mdsf-crew uses the same trick).
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 350,
    }
    # Serialize MLX calls + give the KeepAlive-restarted server one retry
    # if it crashed mid-response (httpx.RemoteProtocolError / ReadError).
    async with _MLX_LOCK:
        for attempt in (1, 2):
            try:
                r = await client.post(MLX_URL, json=body, timeout=MLX_REQUEST_TIMEOUT)
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


# Discord embed colors keyed by exposure level (decimal RGB).
# `none` = attack attempted but blocked (404/4xx). Orange not green — green
# implies "all fine" but it's still an attack worth surfacing.
_COLORS = {
    "internal": 9807270,   # grey   — likely false positive (our own automation)
    "none":     16747008,  # orange — every request blocked / 404'd (FF8C00)
    "low":      15844367,  # gold
    "medium":   15105570,  # amber-orange (E67E22)
    "high":     15548997,  # red    — actual hit on a vulnerable surface
    "unknown":  10070709,  # blurple
}


def _render_attribution_line(source_ip: str,
                              source_cn: str,
                              as_number: str,
                              as_name: str,
                              count: int,
                              duration: str) -> str:
    """Render the rich CrowdSec attribution line at the top of the description.

    Mirrors the format that http_discord.yaml used to emit so the merged
    embed retains the same scannable header (IP, flag, country, ASN, ban
    duration, event count) that operators were already used to.
    """
    flag = f" :flag_{source_cn.lower()}: {source_cn}" if source_cn else ""
    asn = ""
    if as_number:
        asn = f" · AS{as_number}"
        if as_name:
            asn += f" *{as_name}*"
    head = f"**`{source_ip}`**{flag}{asn}"
    body = f"BAN for **{duration or '?'}** · {count} event(s)"
    return f"{head}\n{body}"


def render_description_from_verdict(verdict: dict[str, Any]) -> str:
    """Build the verdict-derived portion of the description (no attribution)."""
    bits: list[str] = []
    v = (verdict.get("verdict") or "").strip()
    if v:
        bits.append(v)
    intent = (verdict.get("intent") or "").strip()
    real_ip = (verdict.get("real_attacker_ip") or "").strip()
    notes = (verdict.get("notes") or "").strip()
    meta_bits: list[str] = []
    if intent and intent.lower() != "unknown":
        meta_bits.append(f"intent: **{intent}**")
    if real_ip and real_ip.lower() != "unknown":
        meta_bits.append(f"attacker: `{real_ip}`")
    if meta_bits:
        bits.append("_" + " · ".join(meta_bits) + "_")
    if notes:
        bits.append(f"> {notes}")
    return "\n\n".join(bits)


def _format_scenarios_field(scenarios_with_counts: list[tuple[str, int]]) -> str:
    """Render the Scenarios field for multi-scenario coalesced posts.

    Each line: `scenario_name` (N events). Sorted by count descending so the
    biggest contributors land at the top. Discord field cap is 1024 chars,
    so we truncate very long lists with `+N more`.
    """
    if not scenarios_with_counts:
        return ""
    ranked = sorted(scenarios_with_counts, key=lambda x: -x[1])
    lines: list[str] = []
    used = 0
    for s, n in ranked:
        line = f"`{s}` — {n} event(s)"
        if used + len(line) + 1 > 1000:
            remaining = len(ranked) - len(lines)
            if remaining > 0:
                lines.append(f"_+{remaining} more scenario(s)_")
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def _pick_longest_duration(durations: list[str]) -> str:
    """Return the longest CrowdSec duration string from a list (e.g. '336h0m0s' > '48h0m0s').

    Parses each duration as hours/minutes/seconds and returns the original
    string corresponding to the largest total. Falls back to the first
    non-empty value if parsing fails.
    """
    if not durations:
        return ""
    best_secs = -1
    best_str = ""
    for d in durations:
        if not d:
            continue
        if best_str == "":
            best_str = d
        secs = 0
        m_h = re.search(r"(\d+)h", d)
        m_m = re.search(r"(\d+)m", d)
        m_s = re.search(r"(\d+)s", d)
        if m_h: secs += int(m_h.group(1)) * 3600
        if m_m: secs += int(m_m.group(1)) * 60
        if m_s: secs += int(m_s.group(1))
        if secs > best_secs:
            best_secs = secs
            best_str = d
    return best_str


async def post_discord(client: httpx.AsyncClient,
                       scenarios_with_counts: list[tuple[str, int]],
                       source_ip: str,
                       source_cn: str,
                       as_number: str,
                       as_name: str,
                       count: int,
                       duration: str,
                       summary: str,
                       events: list[dict[str, str]] | None = None,
                       mode_label: str | None = None) -> None:
    """Post one combined Discord embed for a single source IP.

    `scenarios_with_counts` is the list of (scenario_name, event_count) for
    every CrowdSec scenario that fired against this IP in the current batch.
    A single-scenario post still goes through this path (with one entry).
    """
    mode_label = mode_label or MODE_LABEL
    if not DISCORD_WEBHOOK:
        log.info("DISCORD_WEBHOOK unset, skipping post")
        return

    primary_scenario = scenarios_with_counts[0][0] if scenarios_with_counts else "unknown"
    n_scenarios = len(scenarios_with_counts)

    # Try to parse the structured verdict; fall back to raw prose if the
    # model misbehaved or timed out.
    verdict = parse_verdict(summary)
    attribution = _render_attribution_line(source_ip, source_cn,
                                            as_number, as_name,
                                            count, duration)
    if verdict:
        verdict_block = render_description_from_verdict(verdict) \
                        or "_(LLM returned an empty verdict)_"
        exposure = str(verdict.get("exposure") or "unknown").lower()
        internal = bool(verdict.get("internal_noise"))
        color = _COLORS.get("internal" if internal else exposure,
                            _COLORS["unknown"])
        title_prefix = "[INTERNAL NOISE] " if internal else ""
    else:
        # LLM down / unparseable. Still ship the attribution + raw text so the
        # alert never gets dropped on the floor.
        verdict_block = f"_{summary}_" if summary else "_(no LLM verdict available)_"
        color = _COLORS["unknown"]
        internal = False
        exposure = "unknown"
        title_prefix = ""

    description = (attribution + "\n\n" + verdict_block)[:4000]

    if n_scenarios > 1:
        title = f"{title_prefix}Multi-scenario scan ({n_scenarios} scenarios)"
    else:
        title = f"{title_prefix}{primary_scenario}"

    fields: list[dict[str, Any]] = []
    # When multiple scenarios fired, list them all in a dedicated field so
    # operators can see at a glance what the IP triggered (and its weight).
    if n_scenarios > 1:
        fields.append({
            "name": "Scenarios",
            "value": _format_scenarios_field(scenarios_with_counts),
            "inline": False,
        })
    else:
        fields.append({"name": "Scenario", "value": f"`{primary_scenario}`", "inline": True})
    fields.extend([
        {"name": "Origin",       "value": source_cn or "??",    "inline": True},
        {"name": "Events",       "value": str(count),           "inline": True},
        {"name": "Ban duration", "value": duration or "?",      "inline": True},
        {"name": "Source IP",    "value": f"`{source_ip}`",     "inline": True},
        {"name": "Mode",         "value": mode_label,           "inline": True},
    ])
    if verdict:
        fields.append({"name": "Exposure", "value": exposure, "inline": True})
    # Paths probed: show actual URLs from CrowdSec event meta when available.
    paths_block = format_events_for_discord(events or [])
    if paths_block:
        # Target FQDN is usually constant across events; surface all if many.
        targets = {e["target"] for e in (events or []) if e.get("target")}
        if len(targets) == 1:
            fields.append({"name": "Target", "value": f"`{next(iter(targets))}`", "inline": False})
        elif len(targets) > 1:
            target_list = ", ".join(f"`{t}`" for t in sorted(targets))
            fields.append({"name": "Targets", "value": target_list[:1020], "inline": False})
        fields.append({"name": "Paths probed", "value": paths_block, "inline": False})
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "fields": fields,
        "footer": {"text": f"noc-claw · {MLX_MODEL}"},
    }
    payload = {"username": "CrowdSec + Triage", "embeds": [embed]}
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


def _alert_source(a: dict[str, Any]) -> tuple[str, str, str, str]:
    """Extract (source_ip, source_cn, as_number, as_name) from a CrowdSec alert."""
    src = a.get("source") or {}
    source_ip = src.get("ip", "unknown")
    source_cn = src.get("cn", "") or ""
    # AsNumber comes through as a JSON number from the CrowdSec template
    # (`{{$a.Source.AsNumber | toJson}}`) — normalise to a string so the
    # downstream `f"AS{as_number}"` rendering doesn't say "AS0".
    raw_asn = src.get("as_number")
    as_number = "" if raw_asn in (None, 0, "0", "") else str(raw_asn)
    as_name = (src.get("as_name") or "").strip()
    return source_ip, source_cn, as_number, as_name


def _alert_scenario(a: dict[str, Any]) -> str:
    return a.get("scenario") or (a.get("labels", {}).get("scenario") or "unknown")


def _alert_duration(a: dict[str, Any]) -> str:
    decisions = a.get("decisions") or []
    return (decisions[0].get("duration") if decisions else "") or ""


def _dedup_events_by_path(events: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop near-identical (verb, path, target) tuples from the combined list.

    A multi-scenario scan often has overlapping events (same path matched by
    multiple scenarios). Keep the first occurrence to preserve timestamp
    ordering, drop subsequent dups.
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for e in events:
        key = (e.get("verb", ""), e.get("path", ""), e.get("target", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


async def _process_ip_group(client: httpx.AsyncClient,
                             source_ip: str,
                             alerts: list[dict[str, Any]]) -> None:
    """Background-task worker: process every alert for one source IP as a unit.

    - Combines events across scenarios (deduped by verb+path+target)
    - Picks the longest ban duration as the headline
    - Uses the union of Loki job allowlists across all scenarios
    - Makes ONE LLM call covering every scenario
    - Posts ONE combined Discord embed
    """
    if not alerts:
        return

    # Source attribution comes from the first alert; CrowdSec emits identical
    # source blocks for every alert pertaining to the same IP.
    _, source_cn, as_number, as_name = _alert_source(alerts[0])

    # Collect per-scenario data + union of events.
    scenarios_with_counts: list[tuple[str, int]] = []
    durations: list[str] = []
    seen_scenarios: set[str] = set()
    all_events: list[dict[str, str]] = []
    job_allowlist: set[str] = set()
    total_events_count = 0

    for a in alerts:
        scenario = _alert_scenario(a)
        per_alert_events = int(a.get("events_count", 0) or 0)
        total_events_count += per_alert_events
        durations.append(_alert_duration(a))
        if scenario not in seen_scenarios:
            seen_scenarios.add(scenario)
            scenarios_with_counts.append((scenario, per_alert_events))
            for j in jobs_for_scenario(scenario):
                job_allowlist.add(j)
        else:
            # Same scenario fired twice for the same IP in this batch — bump
            # the event count on the existing entry rather than adding a row.
            for i, (s, n) in enumerate(scenarios_with_counts):
                if s == scenario:
                    scenarios_with_counts[i] = (s, n + per_alert_events)
                    break
        all_events.extend(extract_http_events(a))

    combined_events = _dedup_events_by_path(all_events)
    longest_duration = _pick_longest_duration(durations)
    scenarios = [s for s, _ in scenarios_with_counts]

    key = source_ip
    ok, reason = await state.should_process(key)
    if not ok:
        log.info("skip %s (%s, scenarios=%d)", key, reason, len(scenarios))
        return

    log.info("triage %s scenarios=%d total_events=%d http_events=%d "
             "longest_ban=%s allowed_jobs=%s",
             source_ip, len(scenarios), total_events_count,
             len(combined_events), longest_duration,
             ",".join(sorted(job_allowlist)))

    try:
        # Loki: query once, reusing the union of jobs across every scenario
        # in this group. The allowlist is what matters for filtering noise.
        ctx = await fetch_loki_context(client, source_ip,
                                        allowed_jobs=tuple(sorted(job_allowlist)))
        summary = await summarize(client, scenarios, source_ip, source_cn,
                                   total_events_count, longest_duration,
                                   ctx, combined_events)
        await post_discord(client, scenarios_with_counts, source_ip, source_cn,
                           as_number, as_name, total_events_count,
                           longest_duration, summary, combined_events)
        log.info("triage done %s ctx=%d http=%d sum=%d",
                 source_ip, len(ctx), len(combined_events), len(summary))
    except Exception as exc:  # never let a background failure leak
        log.warning("triage failed for %s: %s", source_ip, exc)


@app.post("/alert", status_code=202)
async def alert_handler(req: Request,
                        bg: BackgroundTasks,
                        x_auth_token: str | None = Header(default=None)) -> dict[str, Any]:
    if AUTH_TOKEN and x_auth_token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="bad auth token")

    # CrowdSec HTTP notifier sends a JSON array of alert objects (batched
    # via group_wait/group_threshold). Handle both array and object (for
    # manual probes).
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

    # Group by source IP — every alert for one IP coalesces into a single
    # downstream LLM call + Discord post. Different IPs in the same batch
    # are processed independently in parallel background tasks.
    by_ip: dict[str, list[dict[str, Any]]] = {}
    for a in alerts:
        ip = (a.get("source") or {}).get("ip") or "unknown"
        by_ip.setdefault(ip, []).append(a)

    # Fire-and-forget: CrowdSec gets an immediate 202 so its own retry/
    # timeout loop never blocks on MLX inference.
    client: httpx.AsyncClient = req.app.state.http
    queued: list[str] = []
    for ip, ip_alerts in by_ip.items():
        bg.add_task(_process_ip_group, client, ip, ip_alerts)
        scenarios = sorted({_alert_scenario(a) for a in ip_alerts})
        queued.append(f"{ip} ({len(ip_alerts)} alert(s), {len(scenarios)} scenario(s))")

    return {"ok": True, "queued": queued, "alert_count": len(alerts), "ip_count": len(by_ip)}


# ---------------------------------------------------------------------------
# Entrypoint (uvicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=LISTEN_HOST, port=LISTEN_PORT,
                log_level=LOG_LEVEL.lower(), access_log=False)

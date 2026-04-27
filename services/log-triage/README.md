# log-triage — LLM enrichment for CrowdSec alerts

FastAPI service that consumes CrowdSec HTTP notifier POSTs, pulls surrounding
log context from Loki, asks the local MLX model on noc-claw for a structured
JSON verdict, and posts the result to Discord with verdict-derived colors and
fields.

```
CrowdSec (noc-tux, active firewall bouncer)
       │  HTTP POST /alert  (notifier: http_triage → forwards events[])
       ▼
log-triage  (noc-claw, :8182)
       │  extract_http_events() ── http_verb/path/status/target_fqdn
       │  fetch_loki_context(scenario=...) → scenario-aware job filter
       │     (http-* → traefik/caddy/synapse/docker;
       │      ssh-* → auth only;
       │      always drop job=homelab and "Accepted publickey" lines)
       │  POST /v1/chat/completions  → structured JSON verdict
       │   ├── topology preamble (Tailscale = us, CF = proxy, agent polls)
       │   ├── "Triggering Requests" labelled PRIMARY EVIDENCE
       │   ├── "Surrounding Logs" labelled CONTEXT ONLY (may be unrelated)
       │   ├── OUTPUT CONTRACT: {verdict, intent, exposure, real_attacker_ip,
       │   │                     internal_noise, notes}
       │   └── serialized via asyncio.Semaphore(1), one retry on
       │       httpx.RemoteProtocolError (MLX SIGABRTs on concurrent GPU)
       └──▶ Discord embed: color by exposure, fields rendered from verdict,
            falls back to raw text if JSON parse fails
```

## Anti-confabulation design

The earlier prose-summary design (pre-noc-homelab-1fq) let the small model
weave false narratives by combining unrelated log events that share a source
IP. Three structural changes:

1. **Loki context is filtered by scenario family** — http alerts only see
   web-server logs, ssh alerts only see auth.log; `job=homelab` (our own
   agent + dashboard polls) is always dropped, as is any line containing
   `Accepted publickey`, `homelab-agent`, or `/api/agent/*` patterns.
2. **Topology preamble** tells the model that Tailscale CGNAT = our own
   machines, Cloudflare tunnels terminate on noc-local (so tunnelled traffic
   appears with edge IPs not attacker IPs), and dashboard polling is not a
   probe.
3. **Structured JSON output** with explicit anti-confab rules: "base verdict
   ONLY on Triggering Requests", "if uncertain set intent=unknown", "NEVER
   claim SSH brute-force unless the Triggering Requests include sshd Failed
   lines". Discord color is keyed off `exposure` (none=green, high=red,
   internal_noise=grey).

Co-located with mlx-server on noc-claw: inference stays on the loopback, no
cross-Tailscale hop. Observability is `/health` (checks Loki, MLX, Discord
config) and service logs under `~/Library/Logs/noc-homelab/log-triage*.log`.

## Deploy (noc-claw)

```bash
# 1. Put the service files where the LaunchAgent expects them
rsync -avz services/log-triage/ noc-claw:/Users/noc/noc-homelab/services/log-triage/

ssh noc-claw
cd /Users/noc/noc-homelab/services/log-triage

# 2. Python venv (system site-packages avoided deliberately)
/opt/homebrew/bin/python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt

# 3. Fill in .env
cp .env.example .env
# edit DISCORD_WEBHOOK, generate AUTH_TOKEN (`openssl rand -hex 32`)

# 4. Install LaunchAgent
ln -sfn /Users/noc/noc-homelab/launchagents/com.noc.log-triage.plist \
        ~/Library/LaunchAgents/com.noc.log-triage.plist
launchctl load ~/Library/LaunchAgents/com.noc.log-triage.plist

# 5. Smoke test
curl -s http://noc-claw:8182/health | jq .
curl -s -X POST http://noc-claw:8182/alert \
  -H "X-Auth-Token: $(grep ^AUTH_TOKEN .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '[{"source":{"ip":"1.2.3.4","cn":"TestCountry"},"scenario":"test/manual","events_count":5,"decisions":[{"duration":"4h"}]}]'
```

## CrowdSec side

Add `http_triage` to `services/crowdsec/notifications/http_triage.yaml` and
list it in the notification array of `services/crowdsec/profiles.yaml`. The
notifier POSTs JSON-wrapped decisions.

## Operational notes

- If the MLX model hangs, the webhook returns with `(LLM summary unavailable)`
  and the Discord post still fires with context fields. CrowdSec is never
  blocked on our LLM — POST is async.
- Rate limiter: same `scenario::ip` key is ignored for 10 min; global cap 30/h.
  Tune via `DEDUPE_WINDOW_SECONDS` / `MAX_PER_HOUR` in `.env`.
- Port 8182 bound to `0.0.0.0` but noc-claw pf firewall only admits Tailscale.

## Why noc-claw, not noc-tux?

- mlx-server already lives there (Apple Silicon ≫ Linux CUDA at small models
  and low power).
- Keeps the Matrix host (noc-tux) free of a Python service and LLM inference
  spikes.
- One less Tailscale hop per alert.

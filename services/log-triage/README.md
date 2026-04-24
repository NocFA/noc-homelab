# log-triage — LLM enrichment for CrowdSec alerts

FastAPI service that consumes CrowdSec HTTP notifier POSTs, pulls surrounding
log context from Loki, asks the local MLX model on noc-claw for a one-paragraph
human summary, and posts the result to Discord.

```
CrowdSec (noc-tux, active firewall bouncer)
       │  HTTP POST /alert  (notifier: http_triage → forwards events[])
       ▼
log-triage  (noc-claw, :8182)
       │  extract_http_events() ── http_verb/path/status/target_fqdn
       │  GET /loki/api/v1/query_range  → 20-40 context lines
       │  POST /v1/chat/completions     → one-paragraph summary
       │   └── serialized via asyncio.Semaphore(1), one retry on
       │       httpx.RemoteProtocolError (MLX SIGABRTs on concurrent GPU)
       └──▶ Discord embed: Target, Paths probed, LLM summary
```

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

# Loki + Grafana log aggregation

Central log stack for the homelab. Runs on noc-tux. All three machines ship
logs here via Alloy agents.

- **Loki** — log storage + query engine (port 3100)
- **Grafana** — UI + dashboards (port 3000)
- **Retention** — 14 days, filesystem-backed, capped by disk

## Topology

```
          noc-local ──┐
                      ├── Alloy push (HTTP) ──▶ noc-tux:3100 (Loki)
           noc-claw ──┤                                │
                      │                                ▼
            noc-tux ──┘                        noc-tux:3000 (Grafana)
```

Exposure: UFW default-deny from WAN. Reachable from Tailscale and LAN.
No Cloudflare/Traefik routing — internal only.

## Deploy

```bash
cd services/loki
cp .env.example .env
# edit .env to set GRAFANA_ADMIN_PASSWORD
docker compose up -d
```

Then browse to `http://noc-tux:3000` from a Tailscale peer.

## Update

```bash
docker compose pull && docker compose up -d
```

## Where logs go

- Raw chunks: `loki_data` Docker volume (`/var/lib/docker/volumes/loki_loki_data/_data`)
- Grafana state: `grafana_data` Docker volume

## Troubleshooting

- `docker compose logs loki` — Loki server errors (ingestion, storage, rate limits)
- `docker compose logs grafana` — UI errors
- `curl http://noc-tux:3100/ready` — Loki readiness
- `curl http://noc-tux:3100/metrics` — Loki Prometheus metrics
- `curl -G -s http://noc-tux:3100/loki/api/v1/label` — list labels currently ingested

## Pairs with

- `services/alloy/` — log shippers (one config per machine)
- `services/crowdsec/` — SSH brute-force / intrusion detection (observation mode by default)

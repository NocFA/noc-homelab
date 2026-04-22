# Loki + Prometheus + Grafana observability stack

Central observability stack for the homelab. Runs on noc-tux. All three
machines ship logs + expose metrics.

- **Loki** — log storage + query engine (port 3100)
- **Prometheus** — metrics storage, 30d retention (port 9090)
- **Grafana** — UI + dashboards (port 3000)
- **Retention** — logs 14d, metrics 30d, filesystem-backed

## Topology

```
          noc-local ──┐                                  Loki ────▶ Grafana
             + Netdata├── Alloy push (logs) ──▶ noc-tux:3100       :3000
                      │                         (Loki)
           noc-claw ──┤                                  Prom ────▶ Grafana
             + Netdata│                         noc-tux:9090
                      │                         (scrapes Netdata
            noc-tux ──┘                          :19999 on each host)
             + Netdata
```

Metrics data source is Prometheus, which scrapes each host's Netdata
Prometheus exporter at `/api/v1/allmetrics?format=prometheus` every 15s.
Netdata tags every series with `instance=<hostname>`, so one unified
data source in Grafana covers all three machines.

Exposure: UFW default-deny from WAN. Reachable from Tailscale and LAN.
No Cloudflare/Traefik routing — internal only.

## Dashboards

- **Homelab Overview** (`/d/homelab-overview`) — at-a-glance CPU, memory,
  load, WAN bandwidth, disk across all three hosts. Default view for
  spotting anomalies ("why is noc-tux pulling 500 Mbit/s right now?").
- **Homelab Network** (`/d/homelab-network`) — per-interface rx/tx, packet
  rate, errors/drops. Drill-down from overview.
- **Homelab Logs** (`/d/homelab-logs`) — log volume, auth failures,
  Traefik 4xx, live tail.

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
- `docker compose logs prometheus` — scrape failures
- `curl http://noc-tux:3100/ready` — Loki readiness
- `curl http://noc-tux:9090/-/ready` — Prometheus readiness
- `curl http://noc-tux:9090/api/v1/targets` — Prometheus scrape target health
- `curl http://noc-tux:3100/metrics` — Loki Prometheus metrics
- `curl -G -s http://noc-tux:3100/loki/api/v1/label` — list labels currently ingested

## Pairs with

- `services/alloy/` — log shippers (one config per machine)
- `services/crowdsec/` — SSH brute-force / intrusion detection (observation mode by default)
- Netdata on each host — provides the metrics Prometheus scrapes

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
# noc-homelab

A three-machine homelab running macOS and Linux, connected over Tailscale. Manages media streaming, Matrix communications, game streaming, and monitoring through a central dashboard and agent API.

<img src="docs/dashboard.gif" alt="Dashboard" width="700">

---

## Machines

| Machine | OS | Role | Connectivity |
|---|---|---|---|
| **noc-local** | macOS (Sonoma) | Dashboard host, local services | LAN + Tailscale |
| **noc-claw** | macOS (Sequoia) | On-device LLM runtime (MLX) | Tailscale `100.95.102.128` |
| **noc-tux** | Ubuntu 24.04 LTS | Agent, media, Matrix, streaming | LAN + Tailscale `100.91.104.124` |
| **noc-baguette** | AlmaLinux 9 | VPS, rathole tunnel server | Public IP + Tailscale `100.96.57.116` |

## Architecture

```
noc-local (macOS)                          noc-tux (Ubuntu)
┌──────────────────────┐                   ┌──────────────────────┐
│  Dashboard :8080     │◄── Agent API ───► │  Agent :8080         │
│                      │    (Tailscale)    │                      │
│  Copyparty           │                   │  Matrix Stack        │
│  Maloja              │                   │    Synapse           │
│  Multi-Scrobbler     │                   │    Element Web       │
│  TeamSpeak 6         │                   │    Synapse Admin     │
│  Syncthing           │                   │    Postgres/Traefik  │
│  Gatus / Glances     │                   │    Coturn (TURN)     │
│  Caddy / Beads UI    │                   │                      │
│  VoiceSeq            │                   │  Media Pipeline      │
│  Tailscale           │                   │    Zurg → Rclone     │
│                      │                   │    FileBot           │
│                      │                   │    Emby / Jellyfin   │
│  MDSF Crew (Web/API) │                   │                      │
│  MDSF Org Dashboard  │                   │  Sunshine / NoMachine│
└──────────────────────┘                   │  Gatus / Glances     │
           ▲                               │  Arcane (Docker UI)  │
           │                               │  Animated Media API  │
           │ Agent API                     │  looney.eu           │
           │ (Tailscale)                   │                      │
           ▼                               │  Rathole Client ─────┼──► noc-baguette :2333
┌──────────────────────┐                   └──────────────────────┘         │
│  noc-claw (macOS)    │                                              (Tailscale tunnel)
│                      │                   ┌──────────────────────┐         │
│  MLX Server :8181    │                   │  noc-baguette (VPS)  │◄────────┘
│    Gemma-3 12B 4bit  │                   │                      │
│  Glances             │                   │  Rathole Server      │
└──────────────────────┘                   │    :23512/udp ──────────► Internet (Resonite)
                                           │    :2333/tcp (Tailscale only)
                                           └──────────────────────┘
```

The dashboard on noc-local polls the agent API on noc-tux and noc-claw for real-time service status. Service control (start/stop/restart) is forwarded through the agents, which manage systemd units, LaunchAgents, and Docker containers.

## Services

### noc-local

| Service | Port | Manager | Description |
|---|---|---|---|
| Dashboard | 8080 | launchd | Central control plane |
| Copyparty | 8081 | launchd | File server with web UI |
| Maloja | 42010 | launchd | Music scrobble server |
| Multi-Scrobbler | 9078 | launchd | Scrobbler aggregator |
| TeamSpeak 6 | 9987 | Docker | Voice chat + P2P Screenshare |
| Syncthing | 8384 | launchd | File sync |
| Gatus | 3001 | Docker | Health monitoring |
| Glances | 61999 | launchd | System metrics API |
| Caddy | 80/443 | launchd | Reverse proxy |
| Beads UI | 3000 | launchd | Issue tracker dashboard |
| Forgejo | 3090 | launchd | Self-hosted Git forge (git.nocfa.net) |
| VoiceSeq | 61998 | launchd | Voice note upload server (iOS) |
| MDSF Crew API | 3100 | launchd | Crew management backend |
| MDSF Crew Web | 5173 | launchd | Crew management frontend |
| MDSF Org Dashboard | 8190 | launchd | Organization landing page |
| Alloy | -- | brew | Log shipper → Loki |
| CrowdSec Agent | -- | launchd | Native v1.7.7, forwards alerts to noc-tux LAPI |
| Netdata | 19999 | brew | System metrics (child, streams to noc-tux parent) |
| Tailscale | -- | system | Mesh VPN |

### noc-claw

| Service | Port | Manager | Description |
|---|---|---|---|
| MLX Server | 8181 | launchd | `mlx_lm.server` serving `mlx-community/gemma-3-12b-it-4bit` (OpenAI-compatible API) |
| log-triage | 8182 | launchd | MLX-backed CrowdSec alert enricher (FastAPI) |
| Alloy | -- | brew | Log shipper → Loki |
| CrowdSec Agent | -- | launchd | Native v1.7.7, forwards alerts to noc-tux LAPI |
| Netdata | 19999 | brew | System metrics (child, streams to noc-tux parent) |
| Glances | 61999 | launchd | System metrics API |

### noc-baguette

| Service | Port | Manager | Description |
|---|---|---|---|
| Rathole Server | 2333/tcp | systemd | Tunnel control (Tailscale-only) |
| Forgejo SSH | 2222/tcp | rathole | Forgejo git-only SSH (ssh.git.nocfa.net) |
| Resonite | 23512/udp | rathole | Resonite headless server tunnel |
| Attack-surface scanner | -- | systemd timer | Weekly nuclei + testssl + ssh-audit scan of public endpoints |

### noc-tux

| Service | Port | Manager | Description |
|---|---|---|---|
| **Matrix Synapse** | -- | systemd | Matrix homeserver |
| **Element Web** | -- | systemd | Matrix web client |
| **Synapse Admin** | -- | systemd | Matrix admin UI |
| Matrix Postgres | -- | systemd | Matrix database |
| Matrix Traefik | 443 | systemd | Matrix reverse proxy + TLS |
| Matrix Coturn | 3478 | systemd | TURN/STUN for calls |
| Emby | 8096 | systemd | Media streaming |
| Jellyfin | 8097 | systemd | Media streaming |
| Plex | 32400 | systemd | Media streaming |
| Zurg | 9999 | systemd (user) | Real-Debrid WebDAV |
| Rclone Zurg | -- | systemd (user) | FUSE mount at `/mnt/zurg` |
| Sunshine | 47990 | systemd (user) | Game streaming (HEVC/AV1) |
| NoMachine | 4000 | systemd | Remote desktop |
| Gatus | 3001 | systemd (user) | Health monitoring |
| Glances | 61999 | systemd | System metrics API |
| Arcane | 3552 | Docker | Docker management UI |
| Animated Media API | -- | Docker | Animated cover art converter |
| looney.eu | -- | Caddy | Personal homepage |
| Loki | 3100 | Docker | Log aggregation (14-day retention) |
| Grafana | 3000 | Docker | Log + metrics dashboards |
| Alloy | -- | systemd | Log shipper (local → Loki) |
| CrowdSec LAPI | 8150 | systemd | Central alerting (3 agents connected, observation mode) |
| Netdata | 19999 | systemd | Metrics parent (streams from noc-local + noc-claw) |

## Media Pipeline

```
Real-Debrid Cloud
       │ (API poll every 10s)
       ▼
Zurg (WebDAV, port 9999)
       │
       ▼
Rclone FUSE mount (/mnt/zurg)
       │ (on_library_update hook)
       ▼
library-update.sh
  ├── Cleanup stale symlinks
  ├── FileBot: movies → media/movies/
  ├── FileBot: shows  → media/shows/
  ├── Emby /Library/Refresh
  ├── Jellyfin /Library/Refresh
  └── Plex /library/sections/all/refresh
       │
       ▼
Emby (8096) + Jellyfin (8097) + Plex (32400)
```

Content stays in the Real-Debrid cloud — no local storage needed. Zurg exposes it as a WebDAV mount, Rclone makes it a local filesystem, FileBot organizes with symlinks, and all three media servers auto-scan.

A `zurg-healthcheck` systemd timer runs every 5 minutes comparing the Real-Debrid API torrent count against what Zurg is serving. If they diverge by more than one item the stack is restarted automatically, catching the occasional state drift without requiring a manual reboot.

## Matrix Stack

Self-hosted Matrix homeserver at `matrix.nocfa.net` with Element Web at `element.nocfa.net`. Provides encrypted messaging, voice/video calls, and screen sharing — replacing Stoat Chat.

All six services run as native systemd units (no Docker). Traefik handles TLS termination and routing. Coturn provides TURN/STUN for NAT traversal on calls.

Admin interface at `matrix.nocfa.net/synapse-admin/`.

## Rathole Tunnels

Game servers run on noc-tux behind NAT. [Rathole](https://github.com/rapiz1/rathole) punches outbound through the NAT to noc-baguette (OVH VPS), exposing UDP/TCP ports publicly without opening the home router.

```
Internet ──► noc-baguette :23512/udp ──► rathole tunnel ──► noc-tux :23512/udp  ──► Resonite
Internet ──► noc-baguette :2222/tcp  ──► rathole tunnel ──► noc-local :2222/tcp ──► Forgejo SSH (git-only)
```

The control channel (port 2333) is Tailscale-only — the VPS is not a jump box. SSH on the VPS is locked to Tailscale CGNAT + home /24 with key-only auth and fail2ban.

**Adding a new tunnel:**
1. Add `[server.services.NAME]` to `/etc/rathole/server.toml` on noc-baguette, open the port in firewalld
2. Add matching `[client.services.NAME]` to `linux/services/rathole/client.toml` on noc-tux
3. Restart rathole on both ends

Template configs with commented examples (Minecraft, Bedrock/Geyser, Simple Voice Chat) are in `linux/services/rathole-server/server.toml` and `linux/services/rathole/client.toml`.

## Observability & Security

Four pillars, all deployed on the `homelab-lockdown` branch.

**Central log aggregation** — Loki (noc-tux :3100) ingests logs from all
three machines via [Grafana Alloy](https://grafana.com/docs/alloy/).
Grafana at `noc-tux:3000` surfaces a provisioned "Homelab Logs"
dashboard. Retention 14 days, filesystem backend, ~118MB at bootstrap.
Label cardinality kept tight (no `unit=session-*.scope` explosion);
every Alloy pipeline drops samples older than 5 minutes so stale file
reads don't flood on restart.

**Per-process network & metrics visibility** — Netdata parent on
noc-tux (:19999) with brew-installed children on both macs streaming
via the parent-child API. Dropdown at the UI switches between hosts.
4GB dbengine retention.

**Intrusion detection** — CrowdSec LAPI on noc-tux (:8150, Tailscale +
LAN only, trusted_ips 127.0.0.1 + ::1 + 100.64.0.0/10). Both macs run
native v1.7.7 agents (brew-built, under `/opt/homebrew/`, managed by
`com.noc.crowdsec-agent` LaunchAgent) in agent-only mode. Two notifiers:
a direct Discord webhook (`http_discord`) and an LLM-enrichment
(`http_triage`) that fires the alert at the **log-triage** service on
noc-claw (:8182), which pulls Loki context, asks the local MLX server
for a short triage summary, and posts the enriched embed back to
Discord. Fire-and-forget (202 in <5s) so CrowdSec's notifier never
times out on a cold MLX call. Running in **observation mode** —
decisions stored, nothing blocked yet. Flipping the firewall bouncer
is tracked in `noc-homelab-b2r`.

**External attack-surface audit** — nuclei + testssl + ssh-audit
installed under `/opt/hl-scan/` on noc-baguette, fired by a weekly
systemd timer (Sundays 03:15 UTC). Rate-limited (8rps / 4 concurrency)
to avoid tripping Cloudflare anti-abuse. Results stash in
`/var/lib/hl-scan/runs/`, Discord webhook on findings.

Baseline host-hardening audit (Lynis) was run once on all three hosts;
findings triaged into follow-up beads.

See [`noc-homelab-beads/memory/observability_stack.md`](./noc-homelab-beads/memory/observability_stack.md)
for the deployment detail and gotchas; the stack is driven entirely
from tracked configs under `services/loki/`, `services/alloy/`,
`services/crowdsec/`, `services/crowdsec-agent/`, `services/log-triage/`,
`services/attack-surface/`.

## Secrets Management

Uses **SOPS + age** encryption with a plaintext-at-rest workflow:

- Configs are **plaintext on disk** for easy editing and direct use by services
- A **pre-commit hook** auto-encrypts sensitive files before they enter git
- A **post-merge hook** auto-decrypts after `git pull`
- Git always stores encrypted content; the working tree always has plaintext

Covered paths: `configs/*`, `*.env`, `linux/services/*/config.*`, `services/*/config/*`, `services/*/vars*`.

Age recipient: `age1jdd07e42w6hgjncpsz0uxe0nruqgpexsl8nhh2vauwn9w0r53paqm9s87h`

The age key and Claude Code shared memory live in a separate private sync repo (`noc-homelab-beads/`) that is gitignored here.

## Git Framework

Every clone of this repo runs the same framework, installed by the setup scripts:

| Component | What it does |
|---|---|
| SOPS pre-commit | Auto-encrypts secrets before commit — aborts if encryption fails |
| SOPS post-merge | Auto-decrypts on `git pull` |
| GPG signing | All commits are signed (`user.signingkey` set per machine) |
| Codeberg auto-pull | Polls Codeberg every 5min and fast-forward pulls if new commits exist |

**Remotes:**
All machines use `origin` with dual push URLs (Codeberg SSH + GitHub SSH). A single `git push origin main` reaches both simultaneously.

Codeberg is the canonical pull source. Each machine's auto-pull fetches from Codeberg; GitHub is a mirror for discoverability.

## Repository Structure

```
noc-homelab/
├── agent/                  # REST API agent (runs on all machines)
│   ├── agent.py            # Flask app, port 5005 (macOS) / 8080 (Linux)
│   ├── config.yaml         # Per-machine service definitions (gitignored, skip-worktree)
│   └── platforms/           # Linux/macOS/Windows handlers
├── dashboard/              # Control dashboard (runs on noc-local)
│   ├── app.py              # Flask app, port 8080
│   ├── template.html       # Dashboard UI
│   └── machines.json       # Machine topology (agent machines: service list from agent API)
├── linux/
│   ├── scripts/            # Automation (library-update, filebot, ddns)
│   ├── services/           # Native service configs (gatus, zurg)
│   └── systemd/            # Systemd unit files
├── services/               # Docker Compose stacks
│   ├── arcane/             # Docker management UI
│   └── teamspeak6/         # TeamSpeak 6 Server
├── configs/                # SOPS-encrypted service configs
├── launchagents/           # macOS LaunchAgent plists
├── scripts/                # Utility scripts (tailscale, teamspeak, newrepo)
├── setup/
│   ├── setup-linux.sh      # noc-tux deployment
│   └── setup-monitoring.sh # Glances + Gatus setup
└── docs/
    ├── architecture.md
    ├── setup-linux.md
    └── setup-macos.md
```

## New Repository Setup

The `scripts/newrepo` script scaffolds a new repo with the full standard stack: SOPS + age encryption, beads issue tracking, GPG commit signing, and a Codeberg remote.

```bash
newrepo my-project              # public repo on Codeberg
newrepo my-project --private    # private repo
newrepo my-project --no-remote  # local only, no Codeberg
```

Creates: `.sops.yaml`, `config.sops.yaml`, full SOPS hook chain (encrypt-on-commit, assume-unchanged, decrypt-on-pull, decrypt-on-checkout), `bd init`, MIT license, AGENTS.md, and pushes to `codeberg.org/noc/<project>`. Plaintext at rest, encrypted in git — the full cycle.

Requires `CODEBERG_TOKEN` in env or `~/.config/newrepo/token` for automatic Codeberg repo creation. The script lives at `~/.local/bin/newrepo` (on PATH) — the copy here is for backup.

## Deployment

### Prerequisites (all machines)

Before running the setup scripts, you need:
1. The `noc-homelab-beads` age key at `noc-homelab/noc-homelab-beads/homelab.agekey`
2. Your SSH key added to Codeberg
3. Your GPG public key added to Codeberg (setup script can generate one)

### noc-tux (Linux)

```bash
# Clone from Codeberg (canonical) or GitHub
git clone ssh://git@codeberg.org/noc/noc-homelab.git
cd noc-homelab

# Place the age key
mkdir -p noc-homelab-beads
cp /path/to/homelab.agekey noc-homelab-beads/homelab.agekey

./setup/setup-linux.sh
```

Installs: SOPS hooks, GPG signing, Codeberg remote + auto-pull timer, media pipeline services (Zurg, Rclone, FileBot), and links Claude Code memory to the beads repo.

### noc-local (macOS)

```bash
# Clone from Codeberg (canonical) or GitHub
git clone ssh://git@codeberg.org/noc/noc-homelab.git
cd noc-homelab

# Place the age key
mkdir -p noc-homelab-beads
cp /path/to/homelab.agekey noc-homelab-beads/homelab.agekey

./setup/setup-macos.sh
```

Installs: Homebrew deps (SOPS, age, gpg), SOPS hooks, GPG signing, Codeberg as origin, LaunchAgents, auto-pull launchd timer, and links Claude Code memory to the beads repo.

Dashboard available at `http://localhost:8080` after loading `com.noc.dashboard.plist`.

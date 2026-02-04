<p align="center">
  <img src="https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/home-assistant.svg" width="100" />
</p>

<h1 align="center">NOC Homelab</h1>

<p align="center">
  <em>A distributed homelab spanning macOS and Windows machines, connected via Tailscale mesh VPN</em>
</p>

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-services">Services</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="docs/architecture.md">Docs</a>
</p>

---

## 📖 Overview

This repository contains the configuration and management tools for a professional multi-machine homelab infrastructure. The standout feature is a fully automated Real-Debrid media pipeline on Windows that goes from torrent to organized 4K streaming in seconds.

### Key Features

- **🎬 Real-Debrid Media Automation** - Cloud torrents → Auto-organized libraries → 4K streaming (see below)
- **Multi-machine management** - Single dashboard controls services on macOS and Windows
- **Tailscale mesh networking** - Secure, zero-config connectivity between all machines
- **SSH-based remote control** - Direct control of Windows services via SSH
- **Web-based dashboard** - Modern UI for monitoring and controlling all services
- **One-command deployment** - Setup scripts for fresh installs

## 🎬 Real-Debrid Media Automation (Windows)

The **killer feature** of this homelab is the fully automated media pipeline:

```
Real-Debrid Cloud → Zurg WebDAV → Rclone Mount → FileBot Auto-Organize → Emby/Jellyfin
```

**What this means**:
1. Add torrent to Real-Debrid (browser, app, RSS, or automation like Sonarr/Radarr)
2. Zurg detects change in 10 seconds, exposes as local files
3. FileBot automatically organizes into proper folder structure with symlinks
4. Emby/Jellyfin libraries update automatically
5. Start streaming in 4K with zero manual work

**Benefits**:
- No downloads - stream directly from Real-Debrid
- No storage needed - content stays in cloud
- Automatic organization - Movies and TV shows properly named
- 4K REMUX support - VFS caching for smooth playback
- Library automation - New content appears in media servers automatically

**See full documentation**: [windows/README.md](windows/README.md)

**Quick Start**: `.\setup\setup-windows.ps1` (prompts for API keys, deploys everything)

## 🖥️ Machines

| Machine | Platform | Role | Services |
|---------|----------|------|----------|
| **noc-local** | macOS | Primary | Dashboard, media scrobbling, file sharing, TeamSpeak |
| **noc-winlocal** | Windows | Media | Emby, Jellyfin, Sunshine, Real-Debrid streaming |

## 🏗️ Architecture

```
                    ┌──────────────────────────────────────────┐
                    │            Tailscale Mesh VPN            │
                    └──────────────────────────────────────────┘
                                        │
            ┌───────────────────────────┴───────────────────────────┐
            │                                                       │
            ▼                                                       ▼
  ┌───────────────────┐                               ┌───────────────────┐
  │    noc-local      │                               │   noc-winlocal    │
  │     (macOS)       │         SSH Control           │    (Windows)      │
  │                   │◄─────────────────────────────►│                   │
  │  ┌─────────────┐  │                               │  ┌─────────────┐  │
  │  │  Dashboard  │  │                               │  │  Scheduled  │  │
  │  │   :8080     │  │                               │  │    Tasks    │  │
  │  └─────────────┘  │                               │  └─────────────┘  │
  │                   │                               │                   │
  │  Services:        │                               │  Services:        │
  │  • Copyparty      │                               │  • Emby           │
  │  • Maloja         │                               │  • Jellyfin       │
  │  • TeamSpeak      │                               │  • Sunshine       │
  │  • Nextcloud      │                               │  • Zurg/Rclone    │
  │  • Syncthing      │                               │  • Parsec         │
  │  • Gatus          │                               │  • Gatus          │
  └───────────────────┘                               └───────────────────┘
```

<details>
<summary>📂 Repository Structure</summary>

```
noc-homelab/
├── dashboard/              # Flask-based control dashboard
│   ├── app.py             # Main application
│   ├── template.html      # Dashboard UI
│   └── machines.json      # Remote machine definitions
├── launchagents/          # macOS LaunchAgent plists
├── services/              # Docker Compose services
│   ├── gatus/             # Status monitoring
│   ├── nextcloud/         # Cloud storage
│   ├── ts3audiobot/       # TeamSpeak music bot
│   └── chatwoot/          # Customer support (experimental)
├── windows/               # Windows-specific content (NEW)
│   ├── scripts/           # PowerShell automation scripts
│   │   ├── library-update.ps1         # FileBot + library scan
│   │   ├── library-update.example.ps1 # Template
│   │   ├── filebot-symlinks.ps1       # Manual FileBot runner
│   │   └── [other management scripts]
│   ├── services/          # Service configurations
│   │   └── zurg/
│   │       ├── config.yml             # Zurg config (gitignored)
│   │       └── config.example.yml     # Template
│   ├── scheduled-tasks/   # Windows Scheduled Task XMLs
│   └── README.md          # Full Real-Debrid pipeline docs
├── setup/                 # Deployment scripts (NEW)
│   ├── setup-windows.ps1  # Windows one-command setup
│   └── setup-macos.sh     # macOS one-command setup
├── scripts/               # Utility scripts
│   ├── tailscale_manager.py
│   ├── teamspeak_manager.py
│   └── sync-beads.sh
├── configs/               # Service configurations
└── docs/                  # Documentation
    ├── architecture.md
    └── deployment.md      # Fresh install guide
```

</details>

## 🚀 Services

### noc-local (macOS)

| Service | Port | Description |
|---------|------|-------------|
| **Dashboard** | 8080 | Central control plane |
| **Copyparty** | 8081 | File server with web UI |
| **Maloja** | 42010 | Music scrobbler |
| **Multi-Scrobbler** | 9078 | Scrobbler aggregator |
| **Gatus** | 3001 | Status page & monitoring |
| **TeamSpeak** | 9987 | Voice chat server |
| **TS3AudioBot** | 58913 | TeamSpeak music bot |
| **Nextcloud** | 9080 | Cloud storage |
| **Syncthing** | 8384 | File synchronization |
| **VoiceSeq** | 61998 | iOS audio upload server |
| **Beads UI** | 3000 | Issue tracker dashboard |
| **Tailscale** | 5252 | VPN webclient |

### noc-winlocal (Windows)

| Service | Port | Description |
|---------|------|-------------|
| **Emby** | 8096 | Media streaming |
| **Jellyfin** | 8097 | Media streaming |
| **Sunshine** | 47990 | Game streaming |
| **Zurg** | 9999 | Real-Debrid WebDAV |
| **Rclone Mount** | - | Mounts Zurg as Z: drive |
| **Parsec** | - | Remote desktop gaming |
| **Gatus** | 3001 | Service health monitoring |
| **Glances** | 61999 | System metrics |

## 🛠️ Getting Started

### Prerequisites

- **macOS**: Homebrew, Python 3.9+, Docker
- **Windows**: Python 3.9+, NSSM for services
- **Both**: Tailscale installed and configured

### Quick Start (macOS)

```bash
# Clone the repository
git clone https://github.com/NocFA/noc-homelab.git
cd noc-homelab

# Install LaunchAgents
cd launchagents
for plist in *.plist; do
  ln -sf "$(pwd)/$plist" ~/Library/LaunchAgents/
done

# Start the dashboard
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist

# Access at http://localhost:8080
```

### Quick Start (Windows)

```powershell
# Windows services are managed remotely via SSH from noc-local
# Ensure SSH server is running and key-based auth is configured

# Services are started via Scheduled Tasks (Homelab-* prefix)
# or Windows Services (via NSSM for background services)
```

## 📚 Documentation

- [Architecture Overview](docs/architecture.md) - System design and multi-machine API spec
- [macOS Setup](docs/setup-macos.md) - Installation and service management
- [Windows Setup](docs/setup-windows.md) - Service deployment and configuration

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built with ☕ and late nights</sub>
</p>

# NOC Homelab

macOS homelab configuration accessible via Tailscale at `http://noc-local/`.

## Services

| Service | Port | Description |
|---------|------|-------------|
| Dashboard | 8080 | Service management UI |
| Copyparty | 8081 | File server |
| Maloja | 42010 | Music scrobbler |
| Multi-Scrobbler | 9078 | Scrobbler hub |
| Gatus | 3001 | Status page & monitoring |
| TeamSpeak | 9987 | Voice chat |
| TS3AudioBot | 58913 | Music bot |
| Nextcloud | 9080 | Cloud storage |
| VoiceSeq | 61998 | iOS audio recording receiver |
| Syncthing | 8384 | File sync |
| Tailscale | 5252 | VPN webclient |

## Structure

```
noc-homelab/
├── dashboard/      # Flask dashboard app
├── launchagents/   # macOS LaunchAgent plists
├── configs/        # Service configs
├── scripts/        # Utility scripts
└── services/       # Docker Compose services
```

## Logs

All service logs are in `~/Library/Logs/noc-homelab/`.

## Commands

```bash
# Reload a service
launchctl unload ~/Library/LaunchAgents/<plist>
launchctl load ~/Library/LaunchAgents/<plist>

# Check service status
launchctl list | grep -E "(dashboard|maloja|multi|copyparty|teamspeak)"

# Docker services
cd services/<name> && docker compose up -d
```

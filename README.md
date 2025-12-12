# NOC Homelab Configuration

This repository contains configuration files and custom applications for the NOC homelab setup, accessible via Tailscale at `http://noc-local/`.

## Repository Structure

```
noc-homelab/
├── dashboard/          # Custom service dashboard (Flask app)
├── launchagents/       # macOS LaunchAgent plists for service management
├── configs/            # Service configuration files
│   ├── nzbhydra2/     # NZBHydra2 config
│   ├── nzbget/        # NZBGet config
│   ├── multi-scrobbler/ # Multi-Scrobbler config
│   └── uptime-kuma/   # Uptime Kuma notes
├── scripts/            # Utility scripts
└── docs/              # Additional documentation
```

## Services

### Dashboard (Custom)
- **Port**: 8080 (forwarded from 80)
- **Location**: `/Users/noc/noc-homelab/dashboard/`
- **Description**: Custom Flask dashboard for managing all services
- **Features**: Start/stop/restart services, view logs, check status

### Media Services

#### Emby Media Server
- **Port**: 8096
- **URL**: http://noc-local:8096
- **Management**: macOS Login Items
- **Config**: Managed via Emby UI

#### NZBGet
- **Port**: 6789
- **URL**: http://noc-local:6789
- **LaunchAgent**: `homebrew.mxcl.nzbget`
- **Config**: `/opt/homebrew/etc/nzbget.conf` (backed up in `configs/nzbget/`)

#### NZBHydra2
- **Port**: 5076
- **URL**: http://noc-local:5076
- **LaunchAgent**: `com.noc.nzbhydra2`
- **Config**: `/Users/noc/nzbhydra2/config/` (backed up in `configs/nzbhydra2/`)

### File & Network Services

#### copyparty File Server
- **Port**: 8081
- **URL**: http://noc-local:8081
- **LaunchAgent**: `com.noc.copyparty`
- **Config**: Command-line arguments in LaunchAgent plist

### Music Services

#### Maloja
- **Port**: 42010
- **URL**: http://noc-local:42010
- **LaunchAgent**: `com.maloja.service`
- **Source**: Git clone at `/Users/noc/maloja/`

#### Multi-Scrobbler
- **Port**: 9078
- **URL**: http://noc-local:9078
- **LaunchAgent**: `com.multiscrobbler.service`
- **Source**: Git clone at `/Users/noc/multi-scrobbler/`
- **Config**: `/Users/noc/multi-scrobbler/config/config.json` (backed up in `configs/multi-scrobbler/`)

### Monitoring

#### Uptime Kuma
- **Port**: 3001
- **URL**: http://noc-local:3001
- **Management**: PM2
- **Source**: Git clone at `/Users/noc/uptime-kuma/`
- **Config**: Stored in SQLite database

## Setup Instructions

### Initial Setup

1. Clone this repository:
   ```bash
   cd /Users/noc/
   git clone <your-repo-url> noc-homelab
   ```

2. Install LaunchAgents (creates symlinks):
   ```bash
   cd /Users/noc/noc-homelab/launchagents
   for plist in *.plist; do
     ln -sf "/Users/noc/noc-homelab/launchagents/$plist" "/Users/noc/Library/LaunchAgents/$plist"
   done
   ```

3. Load the dashboard service:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
   ```

### Managing Services

#### Via Dashboard
Access http://noc-local/ and use the web UI to start/stop/restart services.

#### Via Command Line

**Using launchctl** (for LaunchAgent services):
```bash
# Start
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist

# Stop
launchctl unload ~/Library/LaunchAgents/com.noc.dashboard.plist

# Restart
launchctl unload ~/Library/LaunchAgents/com.noc.dashboard.plist && \
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
```

**Using brew services** (for NZBGet):
```bash
brew services start nzbget
brew services stop nzbget
brew services restart nzbget
```

**Using PM2** (for Uptime Kuma):
```bash
pm2 start uptime-kuma
pm2 stop uptime-kuma
pm2 restart uptime-kuma
pm2 logs uptime-kuma
```

## Configuration Management

### Syncing Configs

After modifying configs in the homelab repo, sync them back to their locations:

**NZBHydra2:**
```bash
cp /Users/noc/noc-homelab/configs/nzbhydra2/nzbhydra.yml \
   /Users/noc/nzbhydra2/config/
```

**NZBGet:**
```bash
sudo cp /Users/noc/noc-homelab/configs/nzbget/nzbget.conf \
   /opt/homebrew/etc/nzbget.conf
```

**Multi-Scrobbler:**
```bash
cp /Users/noc/noc-homelab/configs/multi-scrobbler/config.json \
   /Users/noc/multi-scrobbler/config/
```

### Backup Current Configs

To backup current running configs to the repo:

```bash
# NZBHydra2
cp /Users/noc/nzbhydra2/config/nzbhydra.yml \
   /Users/noc/noc-homelab/configs/nzbhydra2/

# NZBGet
cp /opt/homebrew/etc/nzbget.conf \
   /Users/noc/noc-homelab/configs/nzbget/

# Multi-Scrobbler
cp /Users/noc/multi-scrobbler/config/config.json \
   /Users/noc/noc-homelab/configs/multi-scrobbler/

# Commit changes
cd /Users/noc/noc-homelab
git add -A
git commit -m "Update configs"
git push
```

## Network Access

All services are accessible via Tailscale at `http://noc-local:<port>`.

The dashboard proxies port 80 to 8080, so `http://noc-local/` redirects to the dashboard.

## Logs

Service logs are located at:
- Dashboard: `/Users/noc/dashboard.log`, `/Users/noc/dashboard.error.log`
- NZBHydra2: `/Users/noc/nzbhydra2/config/logs/`
- NZBGet: Check via NZBGet web UI
- Maloja: `/Users/noc/maloja.log`
- Multi-Scrobbler: `/Users/noc/multi-scrobbler.log`
- Uptime Kuma: `~/.pm2/logs/uptime-kuma-*.log`

View logs via PM2:
```bash
pm2 logs
```

## Security Notes

⚠️ **Important**: This repository excludes sensitive data via `.gitignore`:
- Database files
- API keys and secrets
- SSL certificates
- Log files
- Cache and backup directories

Before committing changes, always verify no secrets are included:
```bash
git diff --cached
```

## Maintenance

### Updating Services

**Git-based services** (Maloja, Multi-Scrobbler, Uptime Kuma):
```bash
cd /Users/noc/<service-name>
git pull
npm install  # or pip install, depending on the service
# Restart via dashboard or launchctl/PM2
```

**Homebrew services** (NZBGet):
```bash
brew update
brew upgrade nzbget
brew services restart nzbget
```

### Checking Service Status

```bash
# LaunchAgent services
launchctl list | grep -E "(dashboard|nzbhydra|maloja|multi|copyparty)"

# PM2 services
pm2 status

# Homebrew services
brew services list

# Port listening check
lsof -nP -iTCP -sTCP:LISTEN | grep -E ":(80|3001|5076|6789|8080|8081|8096|9078|42010)"
```

## Troubleshooting

### Dashboard not accessible
```bash
# Check if running
launchctl list | grep dashboard

# Check logs
tail -f /Users/noc/dashboard.error.log

# Restart
launchctl unload ~/Library/LaunchAgents/com.noc.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
```

### Service won't start
1. Check LaunchAgent plist file paths are correct
2. Verify service binary exists
3. Check error logs
4. Try running manually to see errors:
   ```bash
   /opt/homebrew/bin/python3 /Users/noc/noc-homelab/dashboard/app.py
   ```

## Contributing

When making changes:
1. Test changes locally first
2. Update relevant configs in `configs/`
3. Update this README if adding/removing services
4. Commit with descriptive messages
5. Verify services still work after changes

## License

Personal homelab configuration - not licensed for redistribution.

# macOS Setup Guide

## Prerequisites

- macOS 13+ (Ventura or later)
- [Homebrew](https://brew.sh)
- Python 3.9+ (`brew install python3`)
- Docker Desktop or OrbStack
- Tailscale (`brew install tailscale`)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/NocFA/noc-homelab.git /Users/noc/noc-homelab
cd /Users/noc/noc-homelab
```

### 2. Install LaunchAgents

LaunchAgents are macOS's built-in service manager. Symlink the plists so macOS can find them:

```bash
cd launchagents
for plist in *.plist; do
  ln -sf "/Users/noc/noc-homelab/launchagents/$plist" ~/Library/LaunchAgents/
done
```

### 3. Load Services

Load individual services:

```bash
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.noc.copyparty.plist
# etc.
```

Or load all at once:

```bash
for plist in ~/Library/LaunchAgents/com.noc.*.plist; do
  launchctl load "$plist"
done
```

### 4. Start Docker Services

```bash
cd /Users/noc/noc-homelab/services/gatus
docker compose up -d

cd /Users/noc/noc-homelab/services/nextcloud
docker compose up -d

cd /Users/noc/noc-homelab/services/ts3audiobot
docker compose up -d
```

### 5. Verify

```bash
# Check LaunchAgent services
launchctl list | grep -E "(dashboard|maloja|multi|copyparty|teamspeak|voiceseq)"

# Check Docker services
docker ps

# Check ports
lsof -nP -iTCP -sTCP:LISTEN | grep -E ":(8080|8081|3001|9078|42010)"

# Open the dashboard
open http://localhost:8080
```

## Service Management

### Start/Stop/Restart a LaunchAgent

```bash
# Stop
launchctl unload ~/Library/LaunchAgents/com.noc.dashboard.plist

# Start
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist

# Restart (unload then load)
launchctl unload ~/Library/LaunchAgents/com.noc.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist
```

### Docker Services

```bash
cd /Users/noc/noc-homelab/services/<name>
docker compose up -d       # Start
docker compose down        # Stop
docker compose restart     # Restart
docker compose logs -f     # Tail logs
```

### Homebrew Services

```bash
brew services start syncthing
brew services stop syncthing
brew services restart syncthing
```

## Logs

All LaunchAgent service logs are in `~/Library/Logs/noc-homelab/`:

```bash
tail -f ~/Library/Logs/noc-homelab/dashboard.log
tail -f ~/Library/Logs/noc-homelab/dashboard.error.log
```

## Configuration

### Adding a New Service

1. Add to `SERVICES` dict in `dashboard/app.py`
2. Create a LaunchAgent plist in `launchagents/` (if applicable)
3. Symlink and load the plist
4. Add config template to `configs/<service>/`

### Environment Files

Service-specific secrets go in `.env` files (gitignored). Copy from examples:

```bash
cp services/nextcloud/.env.example services/nextcloud/.env
# Edit with your values
```

## Troubleshooting

### Service not responding

```bash
# Check if the process is running
launchctl list | grep <service-name>

# Check error logs
tail -20 ~/Library/Logs/noc-homelab/<service>.error.log

# Test manually
/opt/homebrew/bin/python3 /path/to/service/script.py
```

### Port already in use

```bash
lsof -i :<port>
# Kill the process if needed
kill <pid>
```

# TS3AudioBot Setup

Music bot for TeamSpeak 3 server, running via Docker.

## Quick Start

```bash
cd /Users/noc/noc-homelab/services/ts3audiobot
docker compose up -d
```

## Configuration

### Bot Config
Edit `data/bots/default/bot.toml`:
- `address`: TeamSpeak server address (default: `host.docker.internal:9987`)
- `name`: Bot nickname (default: `MusicBot`)
- `server_password`: Server password if required
- `run`: Set to `true` for auto-start

### Main Config
Edit `data/ts3audiobot.toml` for global settings like web API port (58913).

## Usage

### In TeamSpeak
1. Join the same channel as MusicBot
2. Type commands in chat:
   - `!play <url>` - Play YouTube/SoundCloud/Twitch
   - `!stop` - Stop playback
   - `!volume <0-100>` - Set volume
   - `!help` - List all commands

### First-Time Setup
After bot connects, send in chat:
```
!bot setup <privilege_key>
```
Get privilege key from TeamSpeak server admin.

### Web Interface
Access at: http://noc-local:58913

## Management

### Dashboard
TS3AudioBot appears in the homelab dashboard at http://noc-local:8080

### Manual Control
```bash
cd /Users/noc/noc-homelab/services/ts3audiobot

# Start
docker compose up -d

# Stop
docker compose down

# Restart
docker compose restart

# Logs
docker logs ts3audiobot
```

## Ports

| Port | Purpose |
|------|---------|
| 58913 | Web API/Interface |

## Files

- `docker-compose.yml` - Docker configuration
- `data/ts3audiobot.toml` - Main config
- `data/bots/default/bot.toml` - Bot instance config
- `data/rights.toml` - Permissions
- `data/logs/` - Log files

## Troubleshooting

### Bot won't connect
1. Check server password in `data/bots/default/bot.toml`
2. Verify TeamSpeak server is running: `lsof -i :9987`
3. Check logs: `docker logs ts3audiobot`

### No audio
1. Ensure bot is in same channel as users
2. Check volume: `!volume 50`
3. Verify ffmpeg is working in container

### Container keeps restarting
Check logs for errors:
```bash
docker logs ts3audiobot --tail 50
```

## Resources

- [TS3AudioBot GitHub](https://github.com/Splamy/TS3AudioBot)
- [Command Reference](https://github.com/Splamy/TS3AudioBot/wiki/Command-System)
- [Docker Image](https://github.com/CookieCr2nk/TS3AudioBot-Docker)

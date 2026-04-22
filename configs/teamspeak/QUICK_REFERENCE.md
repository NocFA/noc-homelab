# TeamSpeak Server - Quick Reference

## Server Access

### WAN (Internet) Connection
```
ts3server://<public-ip>:9987
```

### LAN / Tailscale Connection
```
ts3server://noc-local:9987
```

## Admin Credentials
See `CREDENTIALS.txt` (gitignored) for the ServerQuery admin password and WebAPI key.

## Quick Commands

### Server Control (Docker)
```bash
# Start
docker start teamspeak6-server

# Stop
docker stop teamspeak6-server

# Restart
docker restart teamspeak6-server

# Status
docker ps --filter name=teamspeak6-server
```

### Server Info
```bash
# Quick status
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py summary

# Detailed info
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py status

# Connected clients
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py clients
```

### View Logs
```bash
# Container logs
docker logs -f teamspeak6-server

# Server logs on disk
tail -f /Users/noc/noc-homelab/services/teamspeak6/data/logs/*_1.log
```

### Update
```bash
/Users/noc/noc-homelab/scripts/teamspeak-update.sh
```
Pulls the latest image, backs up the data dir, recreates the container.

## Port Forwarding (WAN Access)

### Required Router Rules
| Port  | Protocol | Purpose       |
|-------|----------|---------------|
| 9987  | UDP      | Voice         |
| 30033 | TCP      | File Transfer |

### Do NOT Forward
- 10011 (ServerQuery raw)
- 10022 (ServerQuery SSH)
- 10080 (WebQuery HTTP)
- 10443 (WebQuery HTTPS)

## Dashboard
```
http://noc-local:8080
```
Start / Stop / Restart / Logs / Status for the `teamspeak-6` service.

## Important Paths

### Data directory (bind-mounted into container at `/var/tsserver`)
```
/Users/noc/noc-homelab/services/teamspeak6/data
```

### Credentials
```
/Users/noc/noc-homelab/configs/teamspeak/CREDENTIALS.txt
```

### Backups
```
/Users/noc/noc-homelab/configs/teamspeak/backups/
```

### Full Documentation
```
/Users/noc/noc-homelab/configs/teamspeak/README.md
```

## Troubleshooting

### Check listening ports
```bash
lsof -iTCP -sTCP:LISTEN -nP | grep -E ':(9987|10011|10080|30033)'
```

### Test WAN reachability (from outside the LAN)
```bash
nc -vuz <public-ip> 9987
```

### Public IP
```bash
curl -s ifconfig.me
```

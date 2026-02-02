# TeamSpeak 3 Server - Quick Reference

## Server Access

### WAN (Internet) Connection
```
ts3server://84.203.17.98:9987
```

### LAN Connection
```
ts3server://noc-local:9987
```

### Tailscale Connection
```
ts3server://noc-local:9987
ts3server://100.111.190.104:9987
```

## Admin Token
See `CREDENTIALS.txt` for the current admin token.
Use in client: **Permissions → Use Privilege Key**

## Quick Commands

### Server Control
```bash
# Start
launchctl start com.noc.teamspeak

# Stop
launchctl stop com.noc.teamspeak

# Restart
launchctl stop com.noc.teamspeak && launchctl start com.noc.teamspeak

# Status
ps aux | grep ts3server | grep -v grep
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
# Server logs
tail -f /Users/noc/teamspeak3-server_mac/logs/*_1.log

# LaunchAgent logs
tail -f /Users/noc/noc-homelab/logs/teamspeak.log
```

## Port Forwarding (WAN Access)

### Required Router Rules
| Port  | Protocol | Forward To Internal IP |
|-------|----------|------------------------|
| 9987  | UDP      | [Your Mac's LAN IP]    |
| 30033 | TCP      | [Your Mac's LAN IP]    |

### Security: DO NOT Forward
- 10011 (ServerQuery)
- 10022 (ServerQuery SSH)
- 10080 (WebQuery)

## Dashboard
```
http://noc-local:8080
```
Features: Start/Stop/Restart, Logs, Status

## Important Files

### Configuration
```
/Users/noc/teamspeak3-server_mac/ts3server.ini
```

### Credentials
```
/Users/noc/noc-homelab/configs/teamspeak/CREDENTIALS.txt
```

### Backups
```
/Users/noc/noc-homelab/configs/teamspeak/backups/
```

### Documentation
```
/Users/noc/noc-homelab/configs/teamspeak/README.md
```

## Troubleshooting

### Check if running
```bash
lsof -i :9987 -i :10011
```

### Test WAN connectivity
```bash
# From external network
nc -vuz [YOUR_PUBLIC_IP] 9987
```

### Check public IP
```bash
curl ifconfig.me
```

## Server Specs
- **Slots:** 32 (free license)
- **Virtual Servers:** 1
- **License Valid Until:** July 1, 2027
- **Version:** 3.13.7

## Support
- Full docs: `/Users/noc/noc-homelab/configs/teamspeak/README.md`
- Official support: https://support.teamspeak.com/
- Community: https://community.teamspeak.com/

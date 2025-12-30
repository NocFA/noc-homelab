# TeamSpeak 3 Server Configuration

Complete setup documentation for the NOC Homelab TeamSpeak 3 Server with WAN access.

## Server Information

**Version:** TeamSpeak 3 Server 3.13.7
**Installation Path:** `/Users/noc/teamspeak3-server_mac/`
**Configuration:** `/Users/noc/teamspeak3-server_mac/ts3server.ini`
**Status:** Running via LaunchAgent (auto-starts on boot)

## Credentials

**IMPORTANT:** Keep credentials secure. Located in `CREDENTIALS.txt`

### Server Query Admin
- **Login:** serveradmin
- **Password:** REDACTED_PASSWORD
- **API Key:** REDACTED_API_KEY

### Admin Privilege Key (Token)
- **Latest Token:** REDACTED_TOKEN
- Use this in TeamSpeak client: Permissions → Use Privilege Key

## Network Ports

### Required Ports for WAN Access

| Port  | Protocol | Service         | Required | Description                          |
|-------|----------|-----------------|----------|--------------------------------------|
| 9987  | UDP      | Voice Server    | **YES**  | Main voice communication             |
| 30033 | TCP      | File Transfer   | **YES**  | File uploads/downloads               |
| 10011 | TCP      | ServerQuery     | Optional | Admin API (block from WAN!)          |
| 10022 | TCP      | ServerQuery SSH | Optional | SSH ServerQuery (block from WAN!)    |
| 10080 | TCP      | WebQuery HTTP   | Optional | HTTP API (block from WAN!)           |

### Port Forwarding Configuration

To enable WAN access, configure your router to forward these ports:

#### Router Port Forwarding Rules

1. **Voice Server (Required)**
   - External Port: 9987
   - Internal Port: 9987
   - Protocol: UDP
   - Internal IP: [Your Mac's LAN IP]

2. **File Transfer (Required)**
   - External Port: 30033
   - Internal Port: 30033
   - Protocol: TCP
   - Internal IP: [Your Mac's LAN IP]

#### Security Best Practices

**DO NOT** forward these ports to the internet:
- Port 10011 (ServerQuery) - Admin access, local only
- Port 10022 (ServerQuery SSH) - Admin access, local only
- Port 10080 (WebQuery HTTP) - Admin access, local only

These ports are already restricted in `ts3server.ini` to local connections only via the allowlist.

## Network Access Methods

### 1. WAN (Internet) Access
- **Address:** `84.203.17.98:9987`
- **Requirements:** Port forwarding via UPnP (enabled)
- **Use Case:** Friends connecting from anywhere on the internet
- **Note:** Dynamic IP - may change. Consider Dynamic DNS for permanent hostname.

### 2. LAN (Local Network) Access
- **Address:** `noc-local:9987` or `[Mac LAN IP]:9987`
- **Use Case:** Devices on same home network

### 3. Tailscale (VPN) Access
- **Address:** `noc-local:9987` or `100.111.190.104:9987`
- **Use Case:** Secure access from anywhere via Tailscale VPN
- **Advantage:** No port forwarding needed, encrypted

## Dynamic DNS Setup (Recommended for WAN)

Since most home internet has dynamic IP addresses, configure Dynamic DNS:

### Option 1: Router Built-in DDNS
Most routers support DDNS services like:
- No-IP (free)
- DuckDNS (free)
- Dynu (free)
- DynDNS

### Option 2: Tailscale MagicDNS
Use Tailscale hostnames which automatically resolve to the correct IP.

## Server Features

### Enabled Features
- ✅ Voice chat (32 slots, free license)
- ✅ File transfer (30033)
- ✅ Multiple channels
- ✅ Permissions system
- ✅ ServerQuery API (all protocols)
- ✅ AES-256 encryption
- ✅ Auto-start on boot
- ✅ Auto-restart on crash
- ✅ Automatic backups

### Client Features (TS5/TS6)
Modern TeamSpeak clients support:
- Screen sharing (up to 1440p @ 60 FPS)
- Camera sharing
- Enhanced audio quality
- Modern UI

**Note:** TS3 Server 3.13.7 works perfectly with TS3, TS5, and TS6 clients.

## Server Management

### Dashboard Control
Access the NOC Dashboard at `http://noc-local:8080` for:
- Start/Stop/Restart server
- View logs
- Check online status
- View connected clients

### Command Line Management

#### Start Server
```bash
launchctl start com.noc.teamspeak
```

#### Stop Server
```bash
launchctl stop com.noc.teamspeak
```

#### Restart Server
```bash
launchctl stop com.noc.teamspeak && launchctl start com.noc.teamspeak
```

#### View Logs
```bash
tail -f /Users/noc/teamspeak3-server_mac/logs/*_1.log
```

#### Get Server Status
```bash
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py summary
```

### ServerQuery Management Script

The `teamspeak_manager.py` script provides programmatic access:

```bash
# Get detailed status
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py status

# Get brief summary
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py summary

# List connected clients
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py clients

# List channels
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py channels
```

## Connecting to the Server

### For Users (Clients)

1. **Download TeamSpeak Client**
   - Download from: https://teamspeak.com/
   - Available for Windows, macOS, Linux, iOS, Android

2. **Connect to Server**
   - Open TeamSpeak client
   - Click "Connections" → "Connect"
   - Server Address:
     - **Internet:** `84.203.17.98:9987`
     - **LAN:** `noc-local:9987` or `[Mac IP]:9987`
     - **Tailscale:** `noc-local:9987`
   - Nickname: [Your preferred name]
   - Click "Connect"

3. **Gain Admin Rights (First Time)**
   - After connecting, go to Permissions → Use Privilege Key
   - Enter token: `REDACTED_TOKEN`
   - You now have full admin rights

## Backups

### Automatic Backups
The update script (`teamspeak-update.sh`) runs weekly and creates backups:
- **Location:** `/Users/noc/noc-homelab/configs/teamspeak/backups/`
- **Schedule:** Every Monday at 3:00 AM
- **Retention:** Last 5 backups kept
- **Contents:** Database, config, logs

### Manual Backup
```bash
cd /Users/noc/teamspeak3-server_mac
tar -czf ~/teamspeak-backup-$(date +%Y%m%d).tar.gz \
  ts3server.sqlitedb* \
  ts3server.ini \
  query_ip_allowlist.txt \
  query_ip_denylist.txt \
  ssh_host_rsa_key* \
  logs/
```

## Firewall Configuration

### macOS Firewall
If macOS Firewall is enabled, allow TeamSpeak:
```bash
# Allow ts3server through firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /Users/noc/teamspeak3-server_mac/ts3server
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /Users/noc/teamspeak3-server_mac/ts3server
```

### Router Firewall
Ensure UDP 9987 and TCP 30033 are open for incoming connections.

## Security Considerations

### WAN Security Best Practices

1. **Use Strong Passwords**
   - Change default ServerQuery password
   - Require server passwords for public access
   - Use different tokens for different admin levels

2. **Restrict ServerQuery Access**
   - Keep ports 10011, 10022, 10080 local-only
   - Use query_ip_allowlist.txt for trusted IPs
   - Never expose ServerQuery to WAN

3. **Enable Server Password (Optional)**
   - Set via ServerQuery or client admin panel
   - Prevents unauthorized connections

4. **Monitor Connections**
   - Regular log review
   - Dashboard monitoring
   - Use `teamspeak_manager.py clients` to check who's connected

5. **Update Regularly**
   - Check for TeamSpeak updates monthly
   - Review `teamspeak-update.log` for notifications

### Recommended: Use Tailscale Instead of WAN

For maximum security, consider using Tailscale VPN access instead of WAN:
- No port forwarding needed
- Encrypted connections
- Access control via Tailscale
- No exposure to public internet

## Troubleshooting

### Server Won't Start
```bash
# Check if already running
ps aux | grep ts3server

# Check logs
tail -50 /Users/noc/noc-homelab/logs/teamspeak.log

# Check LaunchAgent status
launchctl list | grep teamspeak
```

### Can't Connect from Internet
1. Verify port forwarding is configured correctly
2. Check router firewall rules
3. Verify public IP address: `curl ifconfig.me`
4. Test port: `nc -vuz [public-ip] 9987`
5. Check macOS firewall settings

### Can't Connect from LAN
1. Verify server is running: `ps aux | grep ts3server`
2. Check if ports are listening: `lsof -i :9987 -i :10011`
3. Test with local IP instead of hostname

### Lost Admin Token
View server logs for the original token:
```bash
grep "privilege key" /Users/noc/teamspeak3-server_mac/logs/*
```

Or generate new token via ServerQuery (advanced).

## Configuration Files

### Main Configuration
- **File:** `/Users/noc/teamspeak3-server_mac/ts3server.ini`
- **Auto-loads on startup**
- **Backup before editing**

### LaunchAgent
- **File:** `~/Library/LaunchAgents/com.noc.teamspeak.plist`
- **Auto-start:** Enabled
- **Auto-restart on crash:** Enabled

### Logs
- **Server Logs:** `/Users/noc/teamspeak3-server_mac/logs/`
- **LaunchAgent Logs:** `/Users/noc/noc-homelab/logs/teamspeak*.log`

## Upgrading TeamSpeak

### Manual Upgrade Process
1. Stop the server
2. Backup current installation
3. Download new version from https://teamspeak.com/
4. Extract to temporary directory
5. Copy database and config files to new installation
6. Test new installation
7. Update LaunchAgent if needed
8. Start server

The `teamspeak-update.sh` script automates backup creation but requires manual download/install.

## Advanced Configuration

### WebQuery API Access
WebQuery is enabled on port 10080 (local only):
```bash
# Example: Get server list
curl -H "x-api-key: REDACTED_API_KEY" \
  http://localhost:10080/1/serverlist
```

### Custom Permissions
- Use TeamSpeak client with admin token
- Navigate to Permissions → Server Groups
- Create custom permission groups
- Assign to users/channels

### Channel Configuration
- Permanent channels: Survive server restart
- Semi-permanent: Exist until manually deleted
- Temporary: Deleted when empty
- Configure via client with admin rights

## License Information

**License Type:** No License (Free)
**Max Virtual Servers:** 1
**Max Slots:** 32
**Valid Until:** July 1, 2027

For more slots or commercial use, visit: https://sales.teamspeak.com/

## Resources

- **Official Website:** https://teamspeak.com/
- **Documentation:** https://support.teamspeak.com/
- **Community Forums:** https://community.teamspeak.com/
- **ServerQuery Docs:** `/Users/noc/teamspeak3-server_mac/serverquerydocs/`
- **Server Docs:** `/Users/noc/teamspeak3-server_mac/doc/`

## Support

For issues specific to this setup:
1. Check logs first
2. Review this documentation
3. Test with management scripts
4. Check dashboard status

For TeamSpeak software issues:
- Official Support: https://support.teamspeak.com/
- Community Forums: https://community.teamspeak.com/

---

**Last Updated:** 2025-12-12
**Maintained by:** NOC Homelab

# TeamSpeak 3 Server - Current State

**Last Updated**: 2025-12-12 18:05

## Quick Status

- ✅ Server running at `/Users/noc/teamspeak3-server_mac/`
- ✅ Version 3.13.7 (latest stable)
- ✅ Auto-starts on boot via LaunchAgent
- ✅ WAN accessible at `84.203.17.98:9987` (UPnP enabled)
- ✅ Dashboard integrated at http://noc-local:8080
- ✅ Admin panel at http://noc-local:8080/teamspeak

## Admin Credentials

**File**: `/Users/noc/noc-homelab/configs/teamspeak/CREDENTIALS.txt`

- **ServerQuery Login**: serveradmin
- **ServerQuery Password**: REDACTED_PASSWORD
- **API Key**: REDACTED_API_KEY
- **Admin Token**: REDACTED_TOKEN

## File Locations

### Core Files
- **Server**: `/Users/noc/teamspeak3-server_mac/`
- **Config**: `/Users/noc/teamspeak3-server_mac/ts3server.ini`
- **Database**: `/Users/noc/teamspeak3-server_mac/ts3server.sqlitedb*`
- **Logs**: `/Users/noc/teamspeak3-server_mac/logs/`

### Dashboard Files
- **Main Dashboard**: `/Users/noc/noc-homelab/dashboard/app.py`
- **Main Template**: `/Users/noc/noc-homelab/dashboard/template.html`
- **TS Admin Panel**: `/Users/noc/noc-homelab/dashboard/teamspeak.html`

### Scripts
- **Management Script**: `/Users/noc/noc-homelab/scripts/teamspeak_manager.py`
- **Update Script**: `/Users/noc/noc-homelab/scripts/teamspeak-update.sh`

### LaunchAgents
- **Server Auto-Start**: `~/Library/LaunchAgents/com.noc.teamspeak.plist`
- **Update Checker**: `~/Library/LaunchAgents/com.noc.teamspeak.update.plist`

### Documentation
- **Full Guide**: `/Users/noc/noc-homelab/configs/teamspeak/README.md`
- **Quick Reference**: `/Users/noc/noc-homelab/configs/teamspeak/QUICK_REFERENCE.md`
- **Kickstart**: `/Users/noc/noc-homelab/docs/TEAMSPEAK_KICKSTART.md`
- **Credentials**: `/Users/noc/noc-homelab/configs/teamspeak/CREDENTIALS.txt`

## Dashboard Integration

### Main Dashboard (app.py)
TeamSpeak is added to the `SERVICES` dict with:
```python
'teamspeak': {
    'name': 'TeamSpeak',
    'launchd': 'com.noc.teamspeak',
    'port': 9987,
    'status_port': 10011,  # ServerQuery for status checks
    'log_paths': ['/Users/noc/teamspeak3-server_mac/logs/*_1.log', ...],
    'web_ports': [30033, 10080],
    'use_wan_ip': True  # Dynamically fetches public IP
}
```

### Dynamic IP Fetching
Function `get_public_ip()` in app.py:
- Calls https://api.ipify.org
- Caches result for 5 minutes
- Used to display WAN address in admin panel

### API Routes
1. `/teamspeak` - Serves admin dashboard HTML
2. `/api/teamspeak/status` - Returns server status + client list (15s timeout)
3. `/api/teamspeak/kick` - Kicks client via ServerQuery (15s timeout)
4. `/api/teamspeak/ban` - Bans client via ServerQuery (15s timeout)

## TeamSpeak Admin Dashboard Features

### Server Info Box
- Displays dynamic WAN IP + port (e.g., `84.203.17.98:9987`)
- Copy button with clipboard API + fallback
- Updates automatically when IP changes

### Live Statistics
- Clients Online / Max Slots
- Total Channels
- Server Uptime (hours)
- Refreshes every 5 seconds

### Connected Users
- Shows all connected clients (excludes ServerQuery clients)
- Displays client nickname + connection time
- Avatar with first letter of nickname
- Action buttons: Kick, Ban

### Controls
- Manual refresh button
- Auto-refresh every 5 seconds
- Notifications for success/error messages

## ServerQuery Manager (teamspeak_manager.py)

Python script using custom `TeamSpeakQuery` class:
- Connects to port 10011
- Auto-detects virtual server ID
- Commands: `status`, `summary`, `clients`, `channels`
- Returns JSON output
- Used by dashboard API

**Usage**:
```bash
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py status
```

## Known Issues & Debug Info

### Issue: Script Timeouts
- **Problem**: teamspeak_manager.py was timing out at 5 seconds
- **Solution**: Increased timeout to 15 seconds in all API endpoints
- **Reason**: ServerQuery connection + login + query takes 6-8 seconds

### Issue: Copy Button May Fail
- **Problem**: Clipboard API blocked by browser security
- **Solution**: Added fallback using `document.execCommand('copy')`
- **Current**: Both methods implemented in teamspeak.html

### Issue: Kick/Ban Might Fail
- **Status**: Needs testing with actual connected clients
- **Debugging**: Check Flask logs at `~/dashboard.error.log`
- **Test Command**:
```bash
echo "clientkick clid=X reasonid=5 reasonmsg=test" | \
  ssh -p 10022 serveradmin@localhost
```

## Port Forwarding (UPnP)

Router automatically forwards:
- **9987 UDP** - Voice server (REQUIRED)
- **30033 TCP** - File transfer (REQUIRED)

DO NOT forward (security):
- 10011 - ServerQuery
- 10022 - ServerQuery SSH
- 10080 - WebQuery HTTP

## Server Control

### Via Dashboard
- http://noc-local:8080 → Click TeamSpeak → Start/Stop/Restart buttons

### Via Command Line
```bash
# Start
launchctl start com.noc.teamspeak

# Stop
launchctl stop com.noc.teamspeak

# Restart
launchctl stop com.noc.teamspeak && launchctl start com.noc.teamspeak

# Check status
ps aux | grep ts3server | grep -v grep
lsof -i :9987 -i :10011

# View logs
tail -f /Users/noc/teamspeak3-server_mac/logs/*_1.log
```

### Via Python Script
```bash
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/teamspeak_manager.py summary
```

## Testing Checklist

- [x] Server starts automatically on boot
- [x] Main dashboard shows TeamSpeak status
- [x] Clicking card opens admin panel
- [x] Admin panel loads server info
- [x] WAN IP displays correctly
- [ ] Copy address button works (may need browser testing)
- [ ] Kick button works (needs client connection to test)
- [ ] Ban button works (needs client connection to test)
- [x] Stats refresh every 5 seconds
- [x] Manual refresh button works

## Future Enhancements

1. **Channel Management**
   - Create/delete/rename channels
   - Set channel permissions
   - Move clients between channels

2. **Ban List Viewer**
   - Display all bans
   - Remove bans
   - Edit ban durations

3. **Permission Management**
   - View/edit server groups
   - Assign permissions
   - Create custom roles

4. **Advanced Stats**
   - Bandwidth usage graphs
   - Connection history
   - Peak hours analysis

5. **Notifications**
   - Alert when specific users connect
   - Notify on server errors
   - Daily connection reports

## Troubleshooting Quick Reference

### Server Won't Start
```bash
# Check if already running
ps aux | grep ts3server

# Check LaunchAgent
launchctl list | grep teamspeak

# View logs
tail -50 /Users/noc/noc-homelab/logs/teamspeak.log
```

### Admin Panel Not Loading
```bash
# Check dashboard
ps aux | grep "dashboard/app.py"

# Test API directly
curl http://localhost:8080/api/teamspeak/status

# Check Flask logs
tail -50 ~/dashboard.error.log
```

### Kick/Ban Not Working
```bash
# Test ServerQuery manually
ssh -p 10022 serveradmin@localhost
# Password: REDACTED_PASSWORD
# Then try: clientlist
# Then try: clientkick clid=X reasonid=5 reasonmsg=test
```

### WAN Connection Fails
```bash
# Check public IP
curl ifconfig.me

# Verify ports are forwarded (test from external network)
nc -vuz YOUR_PUBLIC_IP 9987

# Check server is listening
lsof -i :9987
```

## Summary for Fresh Chat

Everything is operational. The TeamSpeak server is running with:
- Full WAN access for users
- Web-based admin dashboard for management
- Auto-start on boot
- Dynamic IP handling

Main areas to potentially improve:
1. Verify kick/ban functions work with real clients
2. Add more admin features (channels, bans list, permissions)
3. Optimize if performance issues arise
4. Set up DDNS if IP changes frequently

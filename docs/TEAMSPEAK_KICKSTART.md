# TeamSpeak Server Setup - Kickstart Guide

## Context
This is a kickstart document for setting up TeamSpeak 3 Server on the NOC homelab macOS system. Feed this to Claude in a fresh chat to quickly get context and continue the setup.

## Current Status - FULLY OPERATIONAL ✅
- **TeamSpeak Server**: Installed at `/Users/noc/teamspeak3-server_mac/`
- **Version**: TeamSpeak 3 Server 3.13.7
- **License Accepted**: Yes
- **Configuration**: Optimized `ts3server.ini` with all features enabled
- **Auto-Start**: LaunchAgent configured (auto-starts on boot)
- **Main Dashboard**: http://noc-local:8080 - Shows all services
- **Admin Dashboard**: http://noc-local:8080/teamspeak - Full TeamSpeak management
- **WAN Access**: Enabled via UPnP (Dynamic IP: 84.203.17.98:9987)
- **Status**: RUNNING AND ACCESSIBLE

## Important Tokens & Credentials

**ALL CREDENTIALS STORED IN:** `/Users/noc/noc-homelab/configs/teamspeak/CREDENTIALS.txt`

### Server Query Admin Account
```
loginname: serveradmin
password: REDACTED_PASSWORD
apikey: REDACTED_API_KEY
```

### ServerAdmin Privilege Key (Token) - LATEST
```
token: REDACTED_TOKEN
```

**IMPORTANT**: Save these credentials securely. Use the token to gain admin rights in TeamSpeak client.

## Server Configuration

### Default Ports
- **Voice Server**: 9987 (UDP)
- **File Transfer**: 30033 (TCP)
- **ServerQuery**: 10011 (TCP)
- **ServerQuery SSH**: 10022 (TCP)
- **ServerQuery HTTP**: 10080 (TCP)

### Current License
- **Type**: No License (Free/Unlicensed)
- **Max Virtual Servers**: 1
- **Max Slots**: 32
- **Valid Until**: July 1, 2027

## Requirements & Goals

The user wants to set up TeamSpeak with:

1. **Latest Version**: TS 3.13.7 (latest available)
2. **All Features Enabled**:
   - Voice chat ✓
   - File transfer ✓
   - ServerQuery (admin API) ✓
   - Note: Screen share and video are NOT available in TS3 server (those are TS5 client features)
3. **Auto-Updates**: Mechanism to check and install updates automatically
4. **Auto-Start**: LaunchAgent to start server on boot
5. **Dashboard Integration**:
   - Start/Stop/Restart controls
   - View logs
   - View status
   - Admin capabilities
6. **Dashboard Location**: Custom Flask dashboard at `/Users/noc/noc-homelab/dashboard/`

## Existing Homelab Setup

### Directory Structure
```
/Users/noc/noc-homelab/
├── dashboard/          # Flask app on port 8080
├── launchagents/       # macOS LaunchAgent plists
├── configs/            # Service configuration backups
├── scripts/            # Utility scripts
└── docs/               # Documentation
```

### Dashboard Integration Pattern
The dashboard (`/Users/noc/noc-homelab/dashboard/app.py`) manages services via:
- **SERVICES dict**: Configuration for each service (name, port, launchagent, log paths)
- **LaunchAgents**: For auto-start services
- **Control methods**:
  - `launchd` services via `launchctl`
  - Homebrew services via `brew services`
  - PM2 services via `pm2` commands
  - Special services (like Tailscale) with custom handlers

### Example LaunchAgent Pattern
See `/Users/noc/noc-homelab/launchagents/com.noc.dashboard.plist` for reference.

## Completed Setup ✅

1. ✅ **TeamSpeak Configuration File**
   - Created optimized `ts3server.ini` with all features enabled
   - Configured logging, bandwidth, security settings
   - All query protocols enabled (raw, SSH, HTTP)

2. ✅ **Auto-Update Script**
   - Created `/Users/noc/noc-homelab/scripts/teamspeak-update.sh`
   - Automatic backup creation
   - Weekly schedule via LaunchAgent
   - Logs to `/Users/noc/noc-homelab/logs/teamspeak-update.log`

3. ✅ **LaunchAgent Configuration**
   - Created `com.noc.teamspeak.plist` - auto-starts on boot
   - Created `com.noc.teamspeak.update.plist` - weekly update checks
   - Auto-restart on crash enabled
   - Logs to `/Users/noc/noc-homelab/logs/`

4. ✅ **Dashboard Integration**
   - Added to SERVICES dict in `dashboard/app.py`
   - Start/stop/restart controls implemented
   - Log viewing available
   - Status checking via port 10011 (ServerQuery)

5. ✅ **Management Scripts**
   - Created `/Users/noc/noc-homelab/scripts/teamspeak_manager.py`
   - Get server status, player count, channels
   - Full ServerQuery API integration
   - JSON output for easy integration

6. ✅ **Documentation Complete**
   - Created `/Users/noc/noc-homelab/configs/teamspeak/README.md`
   - Comprehensive WAN access guide
   - Port forwarding instructions
   - Security best practices
   - Feature documentation

7. ✅ **Configuration Backup**
   - Automated weekly backups
   - Stored in `/Users/noc/noc-homelab/configs/teamspeak/backups/`
   - Keeps last 5 backups
   - Includes database, config, and logs

## Useful Commands

### Manual Server Control
```bash
# Start server
cd /Users/noc/teamspeak3-server_mac && ./ts3server inifile=ts3server.ini

# Stop server
pkill ts3server

# View logs
tail -f /Users/noc/teamspeak3-server_mac/logs/*_1.log
```

### ServerQuery Access
```bash
# Telnet to ServerQuery
telnet localhost 10011

# SSH to ServerQuery
ssh -p 10022 serveradmin@localhost
# Password: REDACTED_PASSWORD

# HTTP API
curl http://localhost:10080/
```

## TeamSpeak Client Connection

To connect as admin:
1. Open TeamSpeak client
2. Connect to server: `noc-local` or Tailscale IP
3. Port: `9987`
4. Use privilege key (token) to gain admin rights:
   - Permissions -> Use Privilege Key
   - Enter: `zAtotqVflAkAa07Oo9gBFREPzRdUcMqOZQw0OcG7`

## Network Access

The TeamSpeak server is accessible via:
- **WAN (Internet)**: `84.203.17.98:9987` (via UPnP port forwarding)
- **LAN**: `noc-local:9987` or local IP
- **Tailscale**: `noc-local:9987` or `100.111.190.104:9987`

**Note**: WAN IP is dynamic and fetched automatically by the dashboard.

## Resources

- **Server Location**: `/Users/noc/teamspeak3-server_mac/`
- **Documentation**: `/Users/noc/teamspeak3-server_mac/doc/`
- **ServerQuery Docs**: `/Users/noc/teamspeak3-server_mac/serverquerydocs/`
- **Official Docs**: https://teamspeak.com/en/downloads/
- **ServerQuery Reference**: Check serverquerydocs folder

## Notes

- **TS5 vs TS3**: TeamSpeak 5 client has video/screen share, but server is still TS3
- **No Official TS6**: There is no TeamSpeak 6 server yet (user may have meant latest version)
- **Auto-updates**: No official auto-update mechanism, need custom solution
- **License**: Free license allows 32 slots, 1 virtual server - sufficient for homelab

## Tailscale Configuration (Already Completed)

Note: During initial setup, Tailscale was configured with:
- WebClient enabled on port 5252
- Exit node advertising enabled
- Auto-updates enabled
- Dashboard integration added

The Tailscale improvements are separate and should be kept. TeamSpeak is a new addition.

## TeamSpeak Admin Dashboard

A custom web-based admin panel was created at `/Users/noc/noc-homelab/dashboard/teamspeak.html`

**Access**: Click TeamSpeak card on main dashboard OR go to http://noc-local:8080/teamspeak

**Features**:
- **Server Address Display**: Shows dynamic WAN IP (84.203.17.98:9987) with copy button
- **Live Statistics**: Clients online, max slots, channels, uptime
- **Connected Users**: Real-time list of all connected clients
- **Kick Function**: Remove users from server
- **Ban Function**: Permanently ban users with custom reason
- **Auto-Refresh**: Updates every 5 seconds
- **Manual Refresh**: Button to force immediate update

**API Endpoints** (Flask routes in app.py):
- `GET /teamspeak` - Serves admin dashboard
- `GET /api/teamspeak/status` - Returns server status, client list, and WAN IP (JSON)
- `POST /api/teamspeak/kick` - Kicks client by ID
- `POST /api/teamspeak/ban` - Bans client by ID with reason

**Known Issues** (as of 2025-12-12):
- Copy address button may need fallback for some browsers (now has fallback implemented)
- Kick/ban functions may need additional debugging if ServerQuery commands fail
- Script timeout increased from 5s to 15s to accommodate ServerQuery connection time

## Accessing TeamSpeak

**For Users Connecting**:
1. Open TeamSpeak client (download from https://teamspeak.com/)
2. Connect to: `84.203.17.98:9987`
3. First-time admin: Use privilege key from CREDENTIALS.txt

**For Admin Management**:
1. Go to http://noc-local:8080
2. Click TeamSpeak card
3. Admin dashboard opens with full controls
4. Copy server address to share with users
5. Monitor connections and manage users

## Next Steps for Fresh Chat

If continuing in a new chat, the setup is complete. Focus areas:
1. **Debug kick/ban if not working**: Test ServerQuery commands directly
2. **Optimize performance**: If status loading is slow, optimize teamspeak_manager.py
3. **Add features**: Consider adding channel management, permission editing, or ban list viewing
4. **Dynamic DNS**: Set up automatic DDNS updating if WAN IP changes frequently
5. **Monitoring**: Add alerts for when server goes down

## File to Create

After completing setup, create `/Users/noc/noc-homelab/configs/teamspeak/README.md` documenting the final configuration.

# TeamSpeak Server Setup - Kickstart Guide

## Context
This is a kickstart document for setting up TeamSpeak 3 Server on the NOC homelab macOS system. Feed this to Claude in a fresh chat to quickly get context and continue the setup.

## Current Status
- **TeamSpeak Server**: Downloaded and extracted to `/Users/noc/teamspeak3-server_mac/`
- **Version**: TeamSpeak 3 Server 3.13.7 (latest as of 2022-06-20)
- **License Accepted**: Yes (`.ts3server_license_accepted` file created)
- **Initial Run**: Completed once to generate config and admin tokens

## Important Tokens & Credentials

### Server Query Admin Account
```
loginname: serveradmin
password: REDACTED_PASSWORD
apikey: REDACTED_API_KEY
```

### ServerAdmin Privilege Key (Token)
```
token: zAtotqVflAkAa07Oo9gBFREPzRdUcMqOZQw0OcG7
```

**IMPORTANT**: Save these credentials securely. You'll need the token to gain admin rights in the TeamSpeak client.

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

## Tasks to Complete

1. **Create TeamSpeak Configuration File**
   - Set up `ts3server.ini` with optimal settings
   - Configure logging, bandwidth, security settings
   - Enable all available features

2. **Create Auto-Update Script**
   - Script to check for new TeamSpeak versions
   - Download and install updates
   - Backup before update
   - Schedule via LaunchAgent

3. **Create LaunchAgent**
   - File: `/Users/noc/noc-homelab/launchagents/com.noc.teamspeak.plist`
   - Auto-start on boot
   - Restart on crash
   - Proper logging

4. **Add to Dashboard**
   - Add to SERVICES dict in app.py
   - Implement start/stop/restart controls
   - Add log viewing (server logs location: `/Users/noc/teamspeak3-server_mac/logs/`)
   - Add status checking (port 9987 listening check)

5. **Create Management Scripts**
   - Script to get server status
   - Script to get player count
   - Script to view active channels
   - Integration with ServerQuery API

6. **Create Admin Dashboard/Tools**
   - Web interface or scripts to:
     - View connected clients
     - Manage channels
     - Manage permissions
     - View server stats
     - Execute ServerQuery commands

7. **Update README**
   - Add TeamSpeak section
   - Document ports, tokens, admin access
   - Include troubleshooting

8. **Configuration Backup**
   - Backup mechanism for TeamSpeak database and config
   - Include in `/Users/noc/noc-homelab/configs/teamspeak/`

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

The TeamSpeak server should be accessible via:
- **Local**: `localhost:9987`
- **Tailscale**: `noc-local:9987` or `100.111.190.104:9987`
- **LAN**: `<local-ip>:9987` (if configured)

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

## Next Steps

When starting fresh with Claude, ask it to:
1. Create optimized ts3server.ini configuration
2. Set up auto-update mechanism
3. Create LaunchAgent for auto-start
4. Integrate into dashboard with full control
5. Create admin management tools
6. Set up automatic backups
7. Test everything and update documentation

## File to Create

After completing setup, create `/Users/noc/noc-homelab/configs/teamspeak/README.md` documenting the final configuration.

# Tailscale Configuration

## Enabled Features

### Auto-Update
- **Status**: Enabled
- **Command**: `tailscale set --auto-update=true`
- **Description**: Automatically updates Tailscale to the latest version

### WebClient
- **Status**: Enabled
- **Port**: 5252 (accessible via Tailscale IP)
- **URL**: `http://100.111.190.104:5252` (or current Tailscale IP)
- **Command**: `tailscale set --webclient=true`
- **Description**: Web-based admin interface accessible over Tailscale network

### Exit Node
- **Status**: Enabled (advertising as exit node)
- **Command**: `tailscale set --advertise-exit-node=true`
- **Description**: This node can serve as an exit node for other devices on the tailnet

### SSH Server
- **Status**: Not Available
- **Reason**: The macOS GUI version of Tailscale does not support running an SSH server
- **Alternative**: Use standard macOS SSH with Tailscale network

## Additional Features Available

### Tailscale Serve
Share local servers securely within your tailnet:
```bash
# Expose local server on port 3000
tailscale serve 3000

# Expose with background mode
tailscale serve --bg 3000

# View current serve configuration
tailscale serve status

# Reset serve configuration
tailscale serve reset
```

### Tailscale Funnel
Share local servers on the public internet via Tailscale:
```bash
# Expose local server publicly on port 3000
tailscale funnel 3000

# View current funnel configuration
tailscale funnel status

# Reset funnel configuration
tailscale funnel reset
```

### MagicDNS
- Automatically enabled on tailnets
- Allows using machine names instead of IPs (e.g., `http://noc-local/`)

### Taildrop
- File sharing between Tailscale devices
- Send files: Use Tailscale menu bar app
- Receive files: Check `~/Downloads` or Tailscale app

## Network Information

- **Tailnet DNS**: `tail6aa1bb.ts.net`
- **This Machine**:
  - Hostname: `noc-local`
  - Tailscale IP: `100.111.190.104`
  - Full DNS: `noc-local.tail6aa1bb.ts.net`

## Dashboard Integration

Tailscale is integrated into the NOC homelab dashboard at `http://noc-local/`:

- **View Status**: Shows if Tailscale is online/offline
- **View Logs**: Shows recent Tailscale system logs and status summary
- **Restart**: Restarts the Tailscale app
- **WebClient Access**: Click card to open WebClient interface

## Management Commands

### Check Status
```bash
tailscale status
```

### View Current Settings
```bash
tailscale debug prefs
```

### Get Summary (via custom script)
```bash
/opt/homebrew/bin/python3 /Users/noc/noc-homelab/scripts/tailscale_manager.py summary
```

### Enable/Disable Features
```bash
# Enable features
tailscale set --webclient=true
tailscale set --advertise-exit-node=true
tailscale set --auto-update=true

# Disable features
tailscale set --webclient=false
tailscale set --advertise-exit-node=false
```

### Access Control via Admin Console
Visit [Tailscale Admin Console](https://login.tailscale.com/admin/) to:
- Manage devices and users
- Configure ACLs (Access Control Lists)
- Set up subnet routing
- Configure DNS settings
- View audit logs
- Manage sharing and exit nodes

## Troubleshooting

### Tailscale Not Connecting
1. Check if the app is running: `pgrep -f Tailscale.app`
2. Restart the app: Use dashboard or `pkill Tailscale && open -a Tailscale`
3. Check network connectivity
4. Verify in admin console that device is authorized

### WebClient Not Accessible
1. Verify it's enabled: `tailscale debug prefs | grep RunWebClient`
2. Get your Tailscale IP: `tailscale ip -4`
3. Access via: `http://<tailscale-ip>:5252`

### Exit Node Not Working
1. Verify advertising: `tailscale debug prefs | grep AdvertiseRoutes`
2. Check admin console to approve exit node
3. Other devices must enable exit node usage: `tailscale set --exit-node=noc-local`

## Auto-Launch

Tailscale auto-launches on macOS via:
- System Extension (managed by macOS)
- Login Items (Tailscale app in System Preferences > Users & Groups > Login Items)

No LaunchAgent is needed as Tailscale manages this automatically.

## Backup

Tailscale configuration is stored in:
- `/Library/Tailscale/` (system-level, requires sudo)
- `~/Library/Containers/io.tailscale.ipn.macsys/` (app container)

**Note**: Authentication keys and state are managed by Tailscale's servers. Reinstalling the app on the same machine will allow re-authentication to the same tailnet.

## Related Documentation

- [Tailscale Docs](https://tailscale.com/kb/)
- [Tailscale Blog](https://tailscale.com/blog/)
- [Tailscale GitHub](https://github.com/tailscale/tailscale)

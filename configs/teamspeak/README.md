# TeamSpeak Server Configuration

Current deployment: **TeamSpeak 6 Server (beta)** running as a Docker container on noc-local.

- **Image:** `teamspeaksystems/teamspeak6-server:latest`
- **Container name:** `teamspeak6-server`
- **Data directory:** `/Users/noc/noc-homelab/services/teamspeak6/data` (bind-mounted at `/var/tsserver`)
- **Dashboard service key:** `teamspeak-6`

## Credentials

Secrets are stored in `CREDENTIALS.txt` (gitignored).

- **ServerQuery admin password** — set via `TSSERVER_QUERY_ADMIN_PASSWORD` env var on the container.
- **WebAPI key** — used by `scripts/teamspeak_manager.py` to talk to the server.
- **Admin privilege key** — first-use token for claiming server admin in the client (Permissions → Use Privilege Key).

## Network Ports

| Port  | Protocol | Service         | Expose to WAN?                      |
|-------|----------|-----------------|-------------------------------------|
| 9987  | UDP      | Voice           | **YES** — required for voice        |
| 30033 | TCP      | File Transfer   | **YES** — required for file upload  |
| 10011 | TCP      | ServerQuery raw | **NO** — admin API, local only      |
| 10022 | TCP      | ServerQuery SSH | **NO** — admin API, local only      |
| 10080 | TCP      | WebQuery HTTP   | **NO** — admin API, local only      |
| 10443 | TCP      | WebQuery HTTPS  | **NO** — admin API, local only      |

### Connection Addresses

- **WAN:** `<public-ip>:9987`
- **LAN:** `noc-local:9987`
- **Tailscale:** `noc-local:9987`

Use Tailscale to avoid exposing the server publicly when possible.

## Server Management

### Dashboard
`http://noc-local:8080` — start / stop / restart / logs for the `teamspeak-6` service.

### Command line
```bash
docker start teamspeak6-server
docker stop teamspeak6-server
docker restart teamspeak6-server
docker logs -f teamspeak6-server
```

### ServerQuery / WebAPI helper
```bash
/opt/homebrew/bin/python3 scripts/teamspeak_manager.py summary
/opt/homebrew/bin/python3 scripts/teamspeak_manager.py status
/opt/homebrew/bin/python3 scripts/teamspeak_manager.py clients
/opt/homebrew/bin/python3 scripts/teamspeak_manager.py channels
```
See `scripts/teamspeak_manager.py --help` for the full subcommand list (kick, ban, channel management, etc.).

## Updates

```bash
scripts/teamspeak-update.sh
```
- Pulls the latest `teamspeak6-server` image
- Backs up the data directory to `configs/teamspeak/backups/` (5 rotated copies)
- Recreates the container preserving ports, mounts, env, and restart policy

No-ops if the current container is already on the latest image.

## Backups

### Automatic
`teamspeak-update.sh` creates a tarball of the data directory on every update.
- **Location:** `configs/teamspeak/backups/`
- **Retention:** last 5 archives

### Manual
```bash
tar -czf ~/teamspeak-backup-$(date +%Y%m%d).tar.gz \
  -C /Users/noc/noc-homelab/services/teamspeak6 data
```

## Connecting

1. Install a TeamSpeak client (3, 5, or 6 — TS6 server is backward-compatible).
2. **Connections → Connect**, enter:
   - Internet: `<public-ip>:9987`
   - LAN / Tailscale: `noc-local:9987`
3. First time only — **Permissions → Use Privilege Key**, paste the admin token from `CREDENTIALS.txt`.

## Security

- Keep ServerQuery ports (10011/10022/10080/10443) off the WAN.
- Rotate the ServerQuery admin password and WebAPI key if they leak.
- Prefer Tailscale over public port-forwarding where practical.

## Troubleshooting

```bash
# Running?
docker ps --filter name=teamspeak6-server

# Listening ports
lsof -iTCP -sTCP:LISTEN -nP | grep -E ':(9987|10011|10080|30033)'

# Container logs
docker logs --tail=200 teamspeak6-server

# Server logs on disk
tail -n 200 /Users/noc/noc-homelab/services/teamspeak6/data/logs/*_1.log

# Public IP
curl -s ifconfig.me
```

### Container won't start
```bash
docker logs teamspeak6-server
```
Common causes: port already bound, license env var missing (`TSSERVER_LICENSE_ACCEPTED=accept`), corrupt sqlite DB — restore from `configs/teamspeak/backups/`.

### Lost admin token
Grep the container logs for `token=`:
```bash
docker logs teamspeak6-server 2>&1 | grep -i 'token='
```

## Resources

- Official site: https://teamspeak.com/
- Support: https://support.teamspeak.com/
- Community: https://community.teamspeak.com/

# CrowdSec agent (macOS, native)

Runs a native CrowdSec agent under `/opt/homebrew/` on an Apple Silicon
Mac, launched via LaunchAgent, forwarding alerts to the central LAPI on
noc-tux. Observation mode only — no bouncer attached on either side.

This path replaces an earlier Docker/Colima deployment. Native was
chosen for smaller runtime footprint, no container runtime dependency,
and consistency with the rest of the homelab's `/opt/homebrew` + plist
pattern.

## Prerequisites

- Apple Silicon mac (`/opt/homebrew` layout — Intel would need path edits).
- Homebrew installed.
- Tailscale reachability to `noc-tux:8150` (the LAPI listen address).
- Machine credentials issued by the LAPI host, one per mac:
  ```bash
  ssh noc@noc-tux "sudo cscli machines add <hostname>-mac --auto -f -"
  ```
  The command prints a `login` / `password` pair once. Put them into
  this directory's `.env` immediately — they are never regenerated on
  demand and are not stored in the repo.

## Install

```bash
cd services/crowdsec-agent
cp .env.example .env
chmod 600 .env
$EDITOR .env   # fill AGENT_USERNAME, AGENT_PASSWORD

./install-native.sh
```

What `install-native.sh` does, in order:
1. Ensures `go`, `make`, `re2`, `pkg-config` are brew-installed.
2. Clones `github.com/crowdsecurity/crowdsec` at tag `v1.7.7` into
   `~/dev/crowdsec` (skipped on subsequent runs) and builds `crowdsec`
   + `cscli` with `/opt/homebrew/etc/crowdsec` + `/opt/homebrew/var/lib/crowdsec/data`
   baked in as the default config and data dirs.
3. Installs the binaries at `/opt/homebrew/bin/{crowdsec,cscli}`.
4. Lays down the config tree:
   - `/opt/homebrew/etc/crowdsec/config.yaml` (written inline by the script)
   - `/opt/homebrew/etc/crowdsec/acquis.d/system-log.yaml`
   - `/opt/homebrew/etc/crowdsec/{hub,patterns,notifications}/`
   - `/opt/homebrew/var/lib/crowdsec/data/`
5. Renders `/opt/homebrew/etc/crowdsec/local_api_credentials.yaml` (0600)
   from `.env` — **only if the file doesn't already exist**, so re-runs
   never clobber a live password.
6. Runs `cscli hub update` and installs `crowdsecurity/sshd` plus
   `crowdsecurity/base-http-scenarios`.
7. Symlinks `launchagents/com.noc.crowdsec-agent.plist` into
   `~/Library/LaunchAgents/` and loads it.

Total install is ~90s on first run (mostly go build), ~10s on re-runs
because the build step is skipped when the installed binary already
matches `v1.7.7`.

## Verify

On the mac:
```bash
cscli lapi status
# → "You can successfully interact with Local API (LAPI)"
launchctl list | grep com.noc.crowdsec-agent
tail -f ~/Library/Logs/noc-homelab/crowdsec-agent.error.log
```

On noc-tux:
```bash
sudo cscli machines list
# Shows this mac with a recent heartbeat (<1m) and its Tailscale IP.
```

## What this agent watches

Minimal acquisition: `/var/log/system.log` with `type: syslog`. That
catches `sshd-session` auth events, which is the main attack surface on
a mac that isn't serving HTTP/SSH directly to the internet.

Default collections:
- `crowdsecurity/sshd` — SSH brute-force and user-enumeration scenarios.
- `crowdsecurity/base-http-scenarios` — generic HTTP attack shapes.
  `crowdsecurity/http-cve` is pulled in as a dependency; that's fine.

Other CVE / traefik / linux collections are deliberately omitted —
they target Linux server software that isn't running on these macs and
would just add parser noise.

### Optional: unified-log coverage

macOS routes most modern service activity into the unified log, not
`/var/log/system.log`. If we want broader coverage (e.g. full SSH
session logs, app-level auth failures), add a sidecar LaunchAgent that
runs `log stream --style syslog` into a file and tail that file from a
second `acquis.d/*.yaml`. Not enabled by default — keep the agent narrow
until we have a scenario that needs it.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.noc.crowdsec-agent.plist
rm ~/Library/LaunchAgents/com.noc.crowdsec-agent.plist
rm -rf /opt/homebrew/etc/crowdsec /opt/homebrew/var/lib/crowdsec
rm -f /opt/homebrew/bin/crowdsec /opt/homebrew/bin/cscli
```

Then free the name on noc-tux:
```bash
ssh noc@noc-tux "sudo cscli machines delete <hostname>-mac"
```

## Troubleshooting

- **`cscli lapi status` says "connection refused"**: noc-tux's LAPI
  listens on `0.0.0.0:8150`; verify Tailscale is up and the host is
  reachable (`nc -zv noc-tux 8150`).
- **Stale OS/Version in `cscli machines list`**: the LAPI caches the
  first-reported OS per machine row. A mac that was originally
  registered by the Docker agent will continue to show
  `alpine (docker)/3.21.6` until the machine is deleted and re-added.
  The field is cosmetic; heartbeat and alert forwarding work either way.
- **`No matching files for pattern /var/log/system.log`**: transient
  around macOS log rotation. The agent reopens automatically on the
  next write.

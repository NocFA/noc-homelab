# CrowdSec agent (macOS)

Runs a CrowdSec agent in a container on a Mac, forwarding alerts to the
central LAPI on noc-tux. Observation mode only — no bouncer attached on
either side.

## Prerequisites

- Docker runtime (OrbStack, Docker Desktop, Colima, ...).
- Tailscale reachability to `noc-tux:8150`.

### Colima users: extra mount config

OrbStack shares `/private/var/log` out of the box; Colima does not.
Before `docker compose up`, add the log path to Colima's mount list:

```yaml
# ~/.colima/default/colima.yaml
mounts:
  - location: /Users/noc       # keep $HOME writable (Colima default)
    writable: true
  - location: /private/var/log
    writable: false
```

Then `brew services restart colima`. Without this, `/var/log/system.log`
inside the container is an empty directory and the agent warns
`"/var/log/system.log is a directory, ignoring it."`

- Machine credentials issued by the LAPI host:
  ```bash
  ssh noc@noc-tux "sudo cscli machines add <this-host>-mac --auto -f -"
  ```
  The output contains `login` and `password` — paste them into `.env`
  on this machine only. They never go in the repo.

## Install

```bash
cd services/crowdsec-agent
cp .env.example .env
chmod 600 .env
$EDITOR .env   # fill AGENT_USERNAME, AGENT_PASSWORD, HOSTNAME

docker compose up -d
docker compose logs -f --tail=50 crowdsec
```

First boot pulls the image (~120MB) and runs `cscli hub update` +
`cscli collections install crowdsecurity/sshd crowdsecurity/base-http-scenarios`
inside the container. Takes ~30s.

## Verify

From the mac:
```bash
docker exec crowdsec-agent cscli lapi status
# → "You can successfully interact with Local API (LAPI)"
```

From noc-tux:
```bash
sudo cscli machines list
# Should show this mac with recent heartbeat (<1m) and non-127.0.0.1 IP.
```

## What this agent watches

Minimal acquisition: `/var/log/system.log` with `type: syslog` — this
catches `sshd-session` events. macOS routes most traffic into the
unified log nowadays, so this is narrow on purpose.

Collections installed by default:
- `crowdsecurity/sshd` — SSH brute-force scenarios.
- `crowdsecurity/base-http-scenarios` — generic HTTP attack shapes, useful
  if a mac starts serving web UIs directly (unlikely behind Tailscale).

Other CVE collections (`http-cve`, `traefik`, `linux`) are deliberately
omitted — they target Linux server software that isn't running on these
macs and would just add log noise.

## Uninstall

```bash
docker compose down -v   # -v wipes the agent state volumes
```

Then remove the machine from the LAPI host so the name frees up:
```bash
ssh noc@noc-tux "sudo cscli machines delete <this-host>-mac"
```

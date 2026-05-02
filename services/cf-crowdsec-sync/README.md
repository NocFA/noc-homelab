# cf-crowdsec-sync

Pushes the active CrowdSec ban list (IPs only) into a Cloudflare WAF Custom
Rule on the `looney.eu` zone, so attackers are blocked at CF's edge before
they ever hit the cloudflared tunnel + caddy auth chain on `noc-tux`.

This is the free fallback for the paid Cloudflare Worker bouncer. Single
shell script + systemd timer, no daemons.

## Pieces

| File                              | Where it lives                                |
|-----------------------------------|-----------------------------------------------|
| `sync.sh`                         | Repo path (run in-place)                      |
| `cf-crowdsec-sync.env.example`    | Repo template; copy to `/etc/cf-crowdsec-sync.env` |
| `cf-crowdsec-sync.service`        | Symlinked to `/etc/systemd/system/`           |
| `cf-crowdsec-sync.timer`          | Symlinked to `/etc/systemd/system/`           |

## What gets synced

`cscli decisions list -o json` -> filter `type=ban && scope=Ip` -> dedupe ->
build a CF expression like:

```
(http.host eq "love.looney.eu") and (ip.src in {1.2.3.4 5.6.7.0/24 …})
```

…and `PATCH` it into the existing rule (`fe48d0653402416aa4b35ca65d4b9517`)
inside the `http_request_firewall_custom` ruleset on the looney.eu zone.

The rule action is `block`, so banned IPs get a CF block page (1020-style)
with no chance to reach noc-tux.

## CF expression length cap

CF caps custom rule expressions at ~4 KB. Each IPv4 + space is ~16 bytes,
so the script trims to `MAX_IPS` (default 200, set in env) — newest-first.
For the homelab's typical ban size (10-50 active IPs) this is way more than
enough headroom.

## Deploy on noc-tux

```bash
# one-time setup (root)
cd /home/noc/noc-homelab/services/cf-crowdsec-sync
sudo install -m 0600 cf-crowdsec-sync.env.example /etc/cf-crowdsec-sync.env
sudo $EDITOR /etc/cf-crowdsec-sync.env   # paste the real CF token
sudo ln -sf "$PWD/cf-crowdsec-sync.service" /etc/systemd/system/
sudo ln -sf "$PWD/cf-crowdsec-sync.timer"   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cf-crowdsec-sync.timer

# verify
sudo systemctl start cf-crowdsec-sync.service   # one-shot dry run
journalctl -u cf-crowdsec-sync.service -n 20
```

## Token scope

`Zone -> Zone WAF -> Edit` on the `looney.eu` zone is enough. **Account-level
"Account Filter Lists: Edit" is NOT required** because the IPs live inline
inside the rule expression instead of in an account-level IP list — that's
how this avoids needing a token scope the homelab CF token doesn't carry.

## Operating notes

- The CF rule is created once by hand (or by a one-off API call). After
  that, the sync script only PATCHes the `expression` field, never the
  rule id.
- An empty ban list rewrites the expression to `ip.src in {192.0.2.1}`
  (TEST-NET-1, RFC 5737) so the rule remains parseable and matches no real
  traffic.
- The geo allowlist rule (`lovelang: geo allowlist PH+IE+GB`) sits in the
  same ruleset and is **not touched** by this sync.
- Pair this with the in-process `caddy-crowdsec-bouncer` on noc-tux: CF
  blocks at the edge for IPs that have already been banned 5+ minutes,
  caddy blocks newer bans (LAPI poll every 15s) before the JWT verify
  even runs.

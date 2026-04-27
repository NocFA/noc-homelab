#!/usr/bin/env bash
# Mac hardening — applies Lynis 2026-04-22 baseline fixes for noc-local and
# noc-claw (bead noc-homelab-vlo).
#
# Findings addressed:
#   noc-local
#     INSE-8050  — ftp-proxy LaunchDaemon present (binary /usr/libexec/ftp-proxy
#                  loadable on demand). Disable so it cannot be summoned.
#
#   noc-claw
#     FIRE-4590  — Application Firewall (socketfilterfw) is off. Enable.
#                  Application-level filter; signed apps + Tailscale + sshd
#                  remain reachable, no service disruption expected.
#     NETW-2705
#     NAME-4404  — only one responsive nameserver (router 192.168.1.1).
#                  Add a public secondary so DNS keeps working when the
#                  router is rebooted / fails. Tailscale MagicDNS
#                  (100.100.100.100) is split-horizon and not "general".
#                  Also append a `127.0.0.1 noc-claw` entry to /etc/hosts
#                  so the local hostname always resolves even with DNS down.
#
# Runs as: sudo ./mac-hardening.sh
# Idempotent: every action checks current state and skips if already applied.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { echo "[$(date '+%H:%M:%S')] $1"; }
ok()   { echo "[$(date '+%H:%M:%S')] ✓ $1"; }
skip() { echo "[$(date '+%H:%M:%S')] · $1 (already applied)"; }
warn() { echo "[$(date '+%H:%M:%S')] ! $1" >&2; }
err()  { echo "[$(date '+%H:%M:%S')] ✗ $1" >&2; exit 1; }

if [[ $EUID -ne 0 ]]; then
    err "must run as root: sudo $0"
fi

HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
log "running on: $HOST"

# === noc-local: disable com.apple.ftp-proxy (INSE-8050) ============================
harden_noc_local() {
    local ftp_plist="/System/Library/LaunchDaemons/com.apple.ftp-proxy.plist"
    local ftp_label="system/com.apple.ftp-proxy"

    if [[ ! -f "$ftp_plist" ]]; then
        skip "ftp-proxy plist not present on this macOS — nothing to disable"
        return
    fi

    # `print-disabled system` lists everything launchd considers disabled
    # (key in /var/db/com.apple.xpc.launchd/disabled.plist).
    if launchctl print-disabled system 2>/dev/null \
        | grep -q '"com.apple.ftp-proxy" => disabled'; then
        skip "com.apple.ftp-proxy already disabled"
    else
        launchctl disable "$ftp_label"
        ok "disabled $ftp_label"
    fi

    # `launchctl print` exits non-zero if the service isn't loaded — that's
    # the desired state. Only unload if it's currently loaded.
    if launchctl print "$ftp_label" >/dev/null 2>&1; then
        # `bootout` is the modern equivalent of `unload -w`. -w is gone in
        # launchctl 2 (macOS Big Sur+).
        launchctl bootout "$ftp_label" 2>/dev/null \
            || launchctl unload -w "$ftp_plist" 2>/dev/null \
            || warn "bootout failed but service was loaded — investigate manually"
        ok "booted out $ftp_label"
    else
        skip "ftp-proxy not currently loaded"
    fi
}

# === noc-claw: Application Firewall (FIRE-4590) ===================================
harden_noc_claw_firewall() {
    local fw=/usr/libexec/ApplicationFirewall/socketfilterfw

    [[ -x "$fw" ]] || err "$fw not found — skipping FIRE-4590"

    if "$fw" --getglobalstate | grep -q "enabled"; then
        skip "Application Firewall already enabled"
    else
        "$fw" --setglobalstate on >/dev/null
        ok "Application Firewall enabled"
    fi

    # Stealth mode (don't respond to ICMP probes) — opt-in extra.
    # Skipped for now: blocks LAN ping which is useful for diagnostics.
    # Lynis doesn't require stealth, only globalstate=on.

    # Allow signed apps automatically (default behaviour, but make it
    # explicit). This means Tailscale / Homebrew binaries / sshd / mdns etc
    # don't pop "allow incoming?" dialogs.
    #
    # Real output of `socketfilterfw --getallowsigned`:
    #   Automatically allow built-in signed software ENABLED.
    #   Automatically allow downloaded signed software ENABLED.
    local allowsigned
    allowsigned="$("$fw" --getallowsigned 2>&1)"
    if echo "$allowsigned" | grep -q "built-in signed software ENABLED" \
       && echo "$allowsigned" | grep -q "downloaded signed software ENABLED"; then
        skip "allow-signed (built-in + downloaded) already on"
    else
        "$fw" --setallowsigned on >/dev/null 2>&1 || true
        "$fw" --setallowsignedapp on >/dev/null 2>&1 || true
        ok "allow-signed enabled (signed apps reachable without prompts)"
    fi
}

# === noc-claw: secondary DNS (NETW-2705/NAME-4404) ================================
harden_noc_claw_dns() {
    # Lynis sees only `192.168.1.1` (router) as the responsive recursive
    # nameserver. Tailscale's 100.100.100.100 is MagicDNS for ts.net only
    # so doesn't count. Add 1.1.1.1 as a public secondary on every active
    # network service so DNS keeps working when the router reboots.
    #
    # IMPORTANT: networksetup -setdnsservers REPLACES the entire list. We
    # must include 192.168.1.1 in the new list to preserve it. (DHCP-pushed
    # DNS is per-service; once we set explicit servers, DHCP DNS is ignored
    # for that service until we run `-setdnsservers <svc> empty`.)
    local desired_dns=("192.168.1.1" "1.1.1.1")
    local desired_str="192.168.1.1 1.1.1.1"

    # Only touch real Wi-Fi/Ethernet — skip Tailscale (which manages its
    # own resolver via 100.100.100.100 — overriding it would break MagicDNS).
    local services
    services="$(networksetup -listallnetworkservices \
                  | tail -n +2 \
                  | grep -vE "^(Tailscale|\\*)" \
                  | grep -vE "Bridge$")"

    while IFS= read -r svc; do
        [[ -z "$svc" ]] && continue
        local current
        current="$(networksetup -getdnsservers "$svc" 2>&1 | tr '\n' ' ' | sed 's/ *$//')"
        if [[ "$current" == "$desired_str" ]]; then
            skip "DNS on '$svc' already set to: $desired_str"
        elif [[ "$current" == *"There aren't any DNS Servers"* ]]; then
            networksetup -setdnsservers "$svc" "${desired_dns[@]}"
            ok "DNS on '$svc' set to: $desired_str (was DHCP-only, single nameserver)"
        else
            log "DNS on '$svc' currently: $current"
            networksetup -setdnsservers "$svc" "${desired_dns[@]}"
            ok "DNS on '$svc' set to: $desired_str"
        fi
    done <<< "$services"
}

# === noc-claw: /etc/hosts FQDN entry (NAME-4404) ==================================
harden_noc_claw_hosts() {
    local hostsfile=/etc/hosts
    local hostname_short
    hostname_short="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"

    # Lynis NAME-4404 wants the local hostname resolvable from /etc/hosts
    # so it works with DNS off. We add `127.0.0.1 <hostname>` rather than
    # the ts-net or LAN IP — this keeps "ssh <self>" semantics local and
    # never points at a stale interface address.
    if grep -qE "^127\\.0\\.0\\.1[[:space:]].*\\b${hostname_short}\\b" "$hostsfile"; then
        skip "/etc/hosts already maps 127.0.0.1 → $hostname_short"
    else
        # Append after the existing localhost line. Use a backup so a
        # botched edit can be reverted quickly.
        cp -p "$hostsfile" "$hostsfile.pre-vlo.bak"
        # Insert after the first `127.0.0.1 localhost` line (BSD-sed).
        /usr/bin/sed -i '' \
            "/^127\\.0\\.0\\.1[[:space:]]\\{1,\\}localhost/a\\
127.0.0.1	$hostname_short
" "$hostsfile"
        ok "/etc/hosts: added '127.0.0.1 $hostname_short' (backup at $hostsfile.pre-vlo.bak)"
    fi
}

# === Dispatch by hostname ==========================================================
case "$HOST" in
    noc-local)
        harden_noc_local
        ;;
    noc-claw)
        harden_noc_claw_firewall
        harden_noc_claw_dns
        harden_noc_claw_hosts
        ;;
    *)
        err "unknown host '$HOST' — this script only handles noc-local + noc-claw"
        ;;
esac

log "done. Re-run anytime; idempotent."

#!/usr/bin/env bash
# Install external attack-surface scanner tools on noc-baguette (AlmaLinux 9).
#
# Pulls nuclei + notify from ProjectDiscovery, testssl.sh from git,
# ssh-audit from pip. Places binaries in /usr/local/bin.
#
# Idempotent — re-run to refresh versions.

set -euo pipefail

need_root() { [ "$(id -u)" -eq 0 ] || { echo "must run as root"; exit 1; }; }
need_root

# ---------- package deps ----------
echo "=== dnf deps ==="
dnf install -y -q git python3 python3-pip curl tar bsdtar 2>/dev/null || \
  dnf install -y git python3 python3-pip curl tar

# ---------- Go (for nuclei/notify via `go install`) or binary releases ----------
# We fetch prebuilt binaries from GitHub releases for speed.

arch="$(uname -m)"
case "$arch" in
  x86_64) arch_nuclei=amd64 ;;
  aarch64|arm64) arch_nuclei=arm64 ;;
  *) echo "unsupported arch: $arch"; exit 1 ;;
esac

install_pd_binary() {
  # $1 = tool name (nuclei/notify); fetches latest github release archive.
  local tool="$1"
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  local api="https://api.github.com/repos/projectdiscovery/${tool}/releases/latest"
  local url
  url=$(curl -fsSL "$api" | \
    python3 -c "import json,sys,re; r=json.load(sys.stdin);
for a in r['assets']:
    n=a['name']
    if 'linux_${arch_nuclei}' in n and n.endswith('.zip'):
        print(a['browser_download_url']); break")
  if [ -z "$url" ]; then
    echo "  could not locate release for $tool"
    return 1
  fi
  echo "  downloading $tool from $url"
  curl -fsSL "$url" -o "$tmp/$tool.zip"
  (cd "$tmp" && unzip -o -q "$tool.zip")
  install -m 0755 "$tmp/$tool" "/usr/local/bin/$tool"
  "/usr/local/bin/$tool" -version 2>&1 | head -1
}

# unzip dependency
command -v unzip >/dev/null || dnf install -y -q unzip

echo "=== nuclei ==="
install_pd_binary nuclei

echo "=== notify ==="
install_pd_binary notify

# ---------- testssl.sh ----------
echo "=== testssl.sh ==="
if [ ! -d /opt/testssl.sh ]; then
  git clone --depth 1 https://github.com/drwetter/testssl.sh.git /opt/testssl.sh
else
  git -C /opt/testssl.sh pull --quiet --rebase --autostash || true
fi
ln -sfn /opt/testssl.sh/testssl.sh /usr/local/bin/testssl.sh
# Required helper: openssl is almost always present. Bail if not.
command -v openssl >/dev/null || dnf install -y -q openssl

# ---------- ssh-audit ----------
echo "=== ssh-audit ==="
pip3 install --quiet --upgrade ssh-audit
# pip3 on AlmaLinux 9 installs to /usr/local/bin or /root/.local/bin depending
ln -sfn "$(command -v ssh-audit)" /usr/local/bin/ssh-audit 2>/dev/null || true

# ---------- initial nuclei template sync ----------
echo "=== nuclei template sync ==="
/usr/local/bin/nuclei -update-templates -silent 2>&1 | tail -3 || true

# ---------- working dir ----------
install -d -m 0755 /var/lib/hl-scan /var/lib/hl-scan/runs
# Token file (empty scaffold). Real values go in scan.env next to scan.sh.

echo ""
echo "=== install complete ==="
for t in nuclei notify testssl.sh ssh-audit; do
  printf '  %-12s %s\n' "$t" "$(command -v "$t" 2>/dev/null || echo 'MISSING')"
done

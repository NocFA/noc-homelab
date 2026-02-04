"""
Homelab System Tray Application
Monitors and controls Zurg + Rclone mount services
"""

import os
import sys
import subprocess
import psutil
import threading
import time
from pathlib import Path

# pystray for system tray
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

# Paths
HOMELAB_DIR = Path.home() / "homelab-win"
ZURG_EXE = HOMELAB_DIR / "services" / "zurg" / "zurg.exe"
RCLONE_EXE = Path.home() / "scoop" / "apps" / "rclone" / "1.72.1" / "rclone.exe"
CACHE_DIR = HOMELAB_DIR / "cache"
LOG_DIR = HOMELAB_DIR / "logs"
RCLONE_CONF = Path.home() / ".config" / "rclone" / "rclone.conf"

# State
status = {
    "zurg": False,
    "mount": False
}

def is_zurg_running():
    """Check if zurg.exe is running"""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and 'zurg' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def is_mount_active():
    """Check if Z: drive is mounted"""
    return os.path.exists("Z:\\")

def start_zurg():
    """Start Zurg"""
    if not is_zurg_running():
        subprocess.Popen(
            [str(ZURG_EXE)],
            cwd=str(ZURG_EXE.parent),
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        time.sleep(2)
    update_status()

def stop_zurg():
    """Stop Zurg"""
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            if proc.info['name'] and 'zurg' in proc.info['name'].lower():
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    update_status()

def start_mount():
    """Start rclone mount"""
    if not is_mount_active() and is_zurg_running():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(RCLONE_EXE), "mount", "zurg:", "Z:",
            "--dir-cache-time", "10s",
            "--vfs-cache-mode", "full",
            "--vfs-cache-max-age", "24h",
            "--vfs-cache-max-size", "50G",
            "--vfs-cache-min-free-space", "5G",
            "--vfs-read-ahead", "128M",
            "--vfs-read-chunk-size", "4M",
            "--vfs-read-chunk-size-limit", "64M",
            "--vfs-fast-fingerprint",
            "--buffer-size", "64M",
            "--transfers", "8",
            "--checkers", "8",
            "--attr-timeout", "1s",
            "--cache-dir", str(CACHE_DIR),
            "--log-file", str(LOG_DIR / "rclone-mount.log"),
            "--log-level", "INFO",
            "--network-mode"
        ]
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(3)
    update_status()

def stop_mount():
    """Stop rclone mount"""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if proc.info['name'] and 'rclone' in proc.info['name'].lower():
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'mount' in cmdline:
                    proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    update_status()

def start_all():
    """Start all services"""
    start_zurg()
    time.sleep(2)
    start_mount()

def stop_all():
    """Stop all services"""
    stop_mount()
    time.sleep(1)
    stop_zurg()

def restart_all():
    """Restart all services"""
    stop_all()
    time.sleep(2)
    start_all()

def open_emby():
    """Open Emby in browser"""
    import webbrowser
    webbrowser.open("http://localhost:8096")

def open_logs():
    """Open logs folder"""
    os.startfile(str(LOG_DIR))

def update_status():
    """Update status dict"""
    status["zurg"] = is_zurg_running()
    status["mount"] = is_mount_active()

def create_icon_image(running):
    """Create icon based on status"""
    # Green if running, red if not
    color = "#00ff00" if running else "#ff4444"
    bg_color = "#1a1a2e"

    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    draw.ellipse([4, 4, 60, 60], fill=bg_color, outline=color, width=3)

    # Inner status indicator
    if running:
        # Play icon (triangle)
        draw.polygon([(22, 18), (22, 46), (48, 32)], fill=color)
    else:
        # Stop icon (square)
        draw.rectangle([20, 20, 44, 44], fill=color)

    return img

def get_menu():
    """Build menu dynamically based on status"""
    update_status()

    zurg_status = "Running" if status["zurg"] else "Stopped"
    mount_status = "Mounted (Z:)" if status["mount"] else "Not Mounted"

    return Menu(
        MenuItem(f"Zurg: {zurg_status}", None, enabled=False),
        MenuItem(f"Mount: {mount_status}", None, enabled=False),
        Menu.SEPARATOR,
        MenuItem("Start All", lambda: start_all()),
        MenuItem("Stop All", lambda: stop_all()),
        MenuItem("Restart All", lambda: restart_all()),
        Menu.SEPARATOR,
        MenuItem("Start Zurg", lambda: start_zurg(), enabled=not status["zurg"]),
        MenuItem("Stop Zurg", lambda: stop_zurg(), enabled=status["zurg"]),
        MenuItem("Start Mount", lambda: start_mount(), enabled=status["zurg"] and not status["mount"]),
        MenuItem("Stop Mount", lambda: stop_mount(), enabled=status["mount"]),
        Menu.SEPARATOR,
        MenuItem("Open Emby", lambda: open_emby()),
        MenuItem("Open Logs", lambda: open_logs()),
        Menu.SEPARATOR,
        MenuItem("Exit", lambda icon: icon.stop())
    )

def status_monitor(icon):
    """Background thread to monitor and update icon"""
    while icon.visible:
        update_status()
        all_running = status["zurg"] and status["mount"]
        icon.icon = create_icon_image(all_running)
        icon.menu = get_menu()
        time.sleep(5)

def main():
    # Ensure dirs exist
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Initial status
    update_status()
    all_running = status["zurg"] and status["mount"]

    # Create tray icon
    icon = Icon(
        "Homelab",
        create_icon_image(all_running),
        "Homelab Services",
        menu=get_menu()
    )

    # Start monitor thread
    monitor = threading.Thread(target=status_monitor, args=(icon,), daemon=True)
    monitor.start()

    # Run icon
    icon.run()

if __name__ == "__main__":
    main()

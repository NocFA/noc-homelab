SERVICES = {
    "Emby": {
        "port": 8096,
        "url": "http://noc-local:8096",
        "launchagent": None,  # Managed by system login items
        "description": "Media Server",
        "log_path": "~/.config/emby-server/logs"
    },
    "copyparty": {
        "port": 8081,
        "url": "http://noc-local:8081",
        "launchagent": "com.noc.copyparty",  # Fixed: was com.copyparty.service
        "description": "File Server",
        "log_path": "~/copyparty.log"
    },
    "NZBHydra2": {
        "port": 5076,
        "url": "http://noc-local:5076",
        "launchagent": "com.noc.nzbhydra2",  # Fixed: was com.nzbhydra2.service
        "description": "Indexer Manager",
        "log_path": "~/nzbhydra2"
    },
    "NZBGet": {
        "port": 6789,
        "url": "http://noc-local:6789",
        "launchagent": "homebrew.mxcl.nzbget",  # Fixed: was com.nzbget.service
        "description": "Usenet Client",
        "log_path": "~/Library/Application Support/NZBGet"
    },
    "Maloja": {
        "port": 42010,
        "url": "http://noc-local:42010",
        "launchagent": "com.maloja.service",
        "description": "Music Scrobbler",
        "log_path": "~/maloja.log"
    },
    "Multi-Scrobbler": {
        "port": 9078,
        "url": "http://noc-local:9078",
        "launchagent": "com.multiscrobbler.service",
        "description": "Scrobbler Hub",
        "log_path": "~/multi-scrobbler.log"
    },
    "Uptime Kuma": {
        "port": 3001,
        "url": "http://noc-local:3001",
        "launchagent": None,  # Managed by PM2
        "pm2_name": "uptime-kuma",  # Add PM2 support
        "description": "Monitoring",
        "log_path": "~/uptime-kuma.log"
    }
}

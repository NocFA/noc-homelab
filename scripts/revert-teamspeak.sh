#!/bin/bash
# Revert from TeamSpeak 6 (Docker) back to TeamSpeak 3 (Native)

echo "Stopping TeamSpeak 6 Docker container..."
cd /Users/noc/noc-homelab/services/teamspeak6 && docker-compose down

echo "Starting TeamSpeak 3 native server..."
launchctl start com.noc.teamspeak

echo "Verification:"
launchctl list | grep com.noc.teamspeak
ps aux | grep ts3server | grep -v grep

echo "Revert complete."

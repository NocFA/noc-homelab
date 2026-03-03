#!/usr/bin/env python3
"""
TeamSpeak 6 WebAPI Manager
Provides programmatic access to TeamSpeak 6 server information via WebAPI (HTTP)
"""

import sys
import json
import requests
import os


class TeamSpeakQuery:
    """TeamSpeak 6 WebAPI client"""

    def __init__(self, host='127.0.0.1', port=10080):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/1"
        self.api_key = self._load_api_key()
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

    def _load_api_key(self):
        """Load WebAPI key from credentials file"""
        creds_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'configs', 'teamspeak', 'CREDENTIALS.txt'
        )
        try:
            with open(creds_file, 'r') as f:
                for line in f:
                    if line.startswith('apikey:'):
                        return line.split(':', 1)[1].strip()
        except Exception as e:
            print(f"Error loading credentials: {e}", file=sys.stderr)
        return ''

    def _get(self, endpoint):
        try:
            resp = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text}
        except Exception as e:
            return {"error": str(e)}

    def _post(self, endpoint, data=None):
        try:
            resp = requests.post(f"{self.base_url}/{endpoint}", headers=self.headers, json=data or {}, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text}
        except Exception as e:
            return {"error": str(e)}

    def get_server_info(self):
        data = self._get("serverinfo")
        return data.get("body", [{}])[0] if "body" in data else {}

    def get_client_list(self):
        data = self._get("clientlist")
        return data.get("body", []) if "body" in data else []

    def get_channel_list(self):
        data = self._get("channellist")
        return data.get("body", []) if "body" in data else []

    def kick_client(self, clid, reason='Kicked by admin'):
        # reasonid 5 = kick from server
        data = self._post("clientkick", {"clid": int(clid), "reasonid": 5, "reasonmsg": reason})
        return data.get("status", {}).get("code") == 0

    def ban_client(self, clid, reason='Banned by admin', duration=0):
        data = self._post("banclient", {"clid": int(clid), "time": int(duration), "banreason": reason})
        return data.get("status", {}).get("code") == 0

    def get_ban_list(self):
        data = self._get("banlist")
        return data.get("body", []) if "body" in data else []

    def delete_ban(self, banid):
        data = self._post("bandel", {"banid": int(banid)})
        return data.get("status", {}).get("code") == 0

    def create_channel(self, name, parent_cid=0):
        payload = {"channel_name": name, "channel_flag_permanent": 1}
        if parent_cid > 0:
            payload["cpid"] = int(parent_cid)
        data = self._post("channelcreate", payload)
        return data.get("status", {}).get("code") == 0

    def delete_channel(self, cid, force=1):
        data = self._post("channeldelete", {"cid": int(cid), "force": int(force)})
        return data.get("status", {}).get("code") == 0

    def rename_channel(self, cid, new_name):
        data = self._post("channeledit", {"cid": int(cid), "channel_name": new_name})
        return data.get("status", {}).get("code") == 0


def get_status():
    """Get TeamSpeak server status"""
    ts = TeamSpeakQuery()
    
    info = ts.get_server_info()
    if not info:
        return {'online': False, 'error': 'Could not connect to TeamSpeak WebAPI'}

    clients = ts.get_client_list()
    channels = ts.get_channel_list()

    # Filter out query clients (client_type 1)
    real_clients = [c for c in clients if c.get('client_type') != '1']

    return {
        'online': True,
        'server_name': info.get('virtualserver_name', 'TeamSpeak Server'),
        'version': info.get('virtualserver_version', 'Unknown'),
        'uptime': int(info.get('virtualserver_uptime', 0)),
        'clients_online': len(real_clients),
        'max_clients': int(info.get('virtualserver_maxclients', 32)),
        'channels': len(channels),
        'clients': real_clients[:10],
        'platform': info.get('virtualserver_platform', 'Unknown')
    }


def get_summary():
    """Get brief status summary"""
    status = get_status()
    if not status.get('online'):
        return {'status': 'offline', 'error': status.get('error', 'Server is offline')}

    return {
        'status': 'online',
        'name': status['server_name'],
        'clients': f"{status['clients_online']}/{status['max_clients']}",
        'uptime_hours': round(status['uptime'] / 3600, 1),
        'version': status['version']
    }


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: teamspeak_manager.py [status|summary|clients|channels|kick|ban|banlist|unban|createchannel|deletechannel|renamechannel]")
        sys.exit(1)

    command = sys.argv[1]
    ts = TeamSpeakQuery()

    if command == 'status':
        print(json.dumps(get_status(), indent=2))
    elif command == 'summary':
        print(json.dumps(get_summary(), indent=2))
    elif command == 'clients':
        clients = ts.get_client_list()
        real_clients = [c for c in clients if c.get('client_type') != '1']
        print(json.dumps(real_clients, indent=2))
    elif command == 'channels':
        print(json.dumps(ts.get_channel_list(), indent=2))
    elif command == 'kick':
        clid = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else 'Kicked by admin'
        print(json.dumps({'success': ts.kick_client(clid, reason)}, indent=2))
    elif command == 'ban':
        clid = sys.argv[2]
        duration = sys.argv[3] if len(sys.argv) > 3 else 0
        reason = sys.argv[4] if len(sys.argv) > 4 else 'Banned by admin'
        print(json.dumps({'success': ts.ban_client(clid, reason, duration)}, indent=2))
    elif command == 'banlist':
        print(json.dumps(ts.get_ban_list(), indent=2))
    elif command == 'unban':
        banid = sys.argv[2]
        print(json.dumps({'success': ts.delete_ban(banid)}, indent=2))
    elif command == 'createchannel':
        name = sys.argv[2]
        parent_cid = sys.argv[3] if len(sys.argv) > 3 else 0
        print(json.dumps({'success': ts.create_channel(name, parent_cid)}, indent=2))
    elif command == 'deletechannel':
        cid = sys.argv[2]
        print(json.dumps({'success': ts.delete_channel(cid)}, indent=2))
    elif command == 'renamechannel':
        cid = sys.argv[2]
        new_name = sys.argv[3]
        print(json.dumps({'success': ts.rename_channel(cid, new_name)}, indent=2))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()

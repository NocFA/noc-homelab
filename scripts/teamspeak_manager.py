#!/usr/bin/env python3
"""
TeamSpeak ServerQuery Manager
Provides programmatic access to TeamSpeak server information via ServerQuery
"""

import socket
import sys
import json
import time


class TeamSpeakQuery:
    """Simple TeamSpeak ServerQuery client"""

    def __init__(self, host='127.0.0.1', port=10011):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False

    def connect(self):
        """Connect to ServerQuery"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)  # Increased from 5 to 10 seconds
            self.socket.connect((self.host, self.port))

            # Read welcome message
            self._read_response()
            self.connected = True
            return True
        except Exception as e:
            print(f"Error connecting to TeamSpeak: {e}", file=sys.stderr)
            return False

    def disconnect(self):
        """Disconnect from ServerQuery"""
        if self.socket:
            try:
                self.send_command('quit')
            except:
                pass
            self.socket.close()
            self.connected = False

    def _read_response(self):
        """Read response from server"""
        response = b''
        while True:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b'error id=' in response:
                    break
            except socket.timeout:
                break

        return response.decode('utf-8', errors='ignore')

    def send_command(self, command):
        """Send command to ServerQuery"""
        if not self.connected:
            return None

        try:
            self.socket.send(f"{command}\n".encode())
            response = self._read_response()
            return response
        except Exception as e:
            print(f"Error sending command: {e}", file=sys.stderr)
            return None

    def login(self, username='serveradmin', password='REDACTED_PASSWORD'):
        """Login to ServerQuery"""
        response = self.send_command(f'login {username} {password}')
        return 'error id=0' in response if response else False

    def use_server(self, sid=None):
        """Select virtual server"""
        # If no SID specified, get the first running server
        if sid is None:
            serverlist = self.send_command('serverlist')
            if serverlist:
                # Parse to find first online server
                for line in serverlist.split('\n'):
                    if 'virtualserver_status=online' in line:
                        for part in line.split(' '):
                            if part.startswith('virtualserver_id='):
                                sid = part.split('=')[1]
                                break
                        break

        if sid is None:
            sid = 1  # Fallback to 1

        response = self.send_command(f'use sid={sid}')
        return 'error id=0' in response if response else False

    def get_server_info(self):
        """Get server information"""
        response = self.send_command('serverinfo')
        if not response:
            return {}

        info = {}
        # Parse key=value pairs from response
        for line in response.split('\n'):
            if 'error id=' in line:
                continue
            parts = line.strip().split(' ')
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    info[key] = self._unescape(value)

        return info

    def get_client_list(self):
        """Get list of connected clients"""
        response = self.send_command('clientlist')
        if not response:
            return []

        clients = []
        for line in response.split('\n'):
            if 'error id=' in line or not line.strip():
                continue

            # Split by pipe to handle multiple clients on one line
            for item in line.strip().split('|'):
                if not item.strip():
                    continue

                client = {}
                parts = item.strip().split(' ')
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        client[key] = self._unescape(value)

                if client:
                    clients.append(client)

        return clients

    def get_channel_list(self):
        """Get list of channels"""
        response = self.send_command('channellist')
        if not response:
            return []

        channels = []
        for line in response.split('\n'):
            if 'error id=' in line or not line.strip():
                continue

            # Split by pipe to handle multiple channels on one line
            for item in line.strip().split('|'):
                if not item.strip():
                    continue

                channel = {}
                parts = item.strip().split(' ')
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        channel[key] = self._unescape(value)

                if channel:
                    channels.append(channel)

        return channels

    def _unescape(self, text):
        """Unescape TeamSpeak string"""
        text = text.replace('\\\\', '\x00')  # Temporarily replace escaped backslash
        text = text.replace('\\s', ' ')
        text = text.replace('\\p', '|')
        text = text.replace('\\/', '/')
        text = text.replace('\\n', '\n')
        text = text.replace('\\r', '\r')
        text = text.replace('\\t', '\t')
        text = text.replace('\x00', '\\')  # Restore actual backslashes
        return text

    def _escape(self, text):
        """Escape TeamSpeak string"""
        text = text.replace('\\', '\\\\')
        text = text.replace(' ', '\\s')
        text = text.replace('|', '\\p')
        text = text.replace('/', '\\/')
        text = text.replace('\n', '\\n')
        text = text.replace('\r', '\\r')
        text = text.replace('\t', '\\t')
        return text

    def kick_client(self, clid, reason='Kicked by admin'):
        """Kick a client from the server"""
        escaped_reason = self._escape(reason)
        response = self.send_command(f'clientkick clid={clid} reasonid=5 reasonmsg={escaped_reason}')
        return 'error id=0' in response if response else False

    def ban_client(self, clid, reason='Banned by admin', duration=0):
        """Ban a client (duration in seconds, 0 = permanent)"""
        escaped_reason = self._escape(reason)
        response = self.send_command(f'banclient clid={clid} time={duration} banreason={escaped_reason}')
        return 'error id=0' in response if response else False

    def get_ban_list(self):
        """Get list of all bans"""
        response = self.send_command('banlist')
        if not response:
            return []

        bans = []
        for line in response.split('\n'):
            if 'error id=' in line or not line.strip():
                continue

            # Split by pipe to handle multiple bans on one line
            for item in line.strip().split('|'):
                if not item.strip():
                    continue

                ban = {}
                parts = item.strip().split(' ')
                for part in parts:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        ban[key] = self._unescape(value)

                if ban:
                    bans.append(ban)

        return bans

    def delete_ban(self, banid):
        """Delete a ban by ID"""
        response = self.send_command(f'bandel banid={banid}')
        return 'error id=0' in response if response else False

    def create_channel(self, name, parent_cid=0):
        """Create a new channel"""
        escaped_name = self._escape(name)
        # channel_flag_permanent=1 makes the channel permanent (not deleted when empty)
        cmd = f'channelcreate channel_name={escaped_name} channel_flag_permanent=1'
        if parent_cid > 0:
            cmd += f' cpid={parent_cid}'
        response = self.send_command(cmd)
        return 'error id=0' in response if response else False

    def delete_channel(self, cid, force=1):
        """Delete a channel"""
        response = self.send_command(f'channeldelete cid={cid} force={force}')
        return 'error id=0' in response if response else False

    def rename_channel(self, cid, new_name):
        """Rename a channel"""
        escaped_name = self._escape(new_name)
        response = self.send_command(f'channeledit cid={cid} channel_name={escaped_name}')
        return 'error id=0' in response if response else False


def get_status():
    """Get TeamSpeak server status"""
    ts = TeamSpeakQuery()

    if not ts.connect():
        return {
            'online': False,
            'error': 'Could not connect to TeamSpeak server'
        }

    if not ts.login():
        ts.disconnect()
        return {
            'online': False,
            'error': 'Could not login to ServerQuery'
        }

    if not ts.use_server():
        ts.disconnect()
        return {
            'online': False,
            'error': 'Could not select virtual server'
        }

    # Get server info
    info = ts.get_server_info()
    clients = ts.get_client_list()
    channels = ts.get_channel_list()

    ts.disconnect()

    # Filter out query clients
    real_clients = [c for c in clients if c.get('client_type') != '1']

    return {
        'online': True,
        'server_name': info.get('virtualserver_name', 'TeamSpeak Server'),
        'version': info.get('virtualserver_version', 'Unknown'),
        'uptime': int(info.get('virtualserver_uptime', 0)),
        'clients_online': len(real_clients),
        'max_clients': int(info.get('virtualserver_maxclients', 32)),
        'channels': len(channels),
        'clients': real_clients[:10],  # Limit to 10 clients for display
        'platform': info.get('virtualserver_platform', 'Unknown')
    }


def get_summary():
    """Get brief status summary"""
    status = get_status()

    if not status.get('online'):
        return {
            'status': 'offline',
            'error': status.get('error', 'Server is offline')
        }

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

    if command == 'status':
        status = get_status()
        print(json.dumps(status, indent=2))

    elif command == 'summary':
        summary = get_summary()
        print(json.dumps(summary, indent=2))

    elif command == 'clients':
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            clients = ts.get_client_list()
            real_clients = [c for c in clients if c.get('client_type') != '1']
            print(json.dumps(real_clients, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    elif command == 'channels':
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            channels = ts.get_channel_list()
            print(json.dumps(channels, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    elif command == 'kick':
        if len(sys.argv) < 3:
            print(json.dumps({'error': 'Usage: teamspeak_manager.py kick <clid> [reason]'}, indent=2))
            sys.exit(1)
        clid = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else 'Kicked by admin'
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            success = ts.kick_client(clid, reason)
            print(json.dumps({'success': success}, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    elif command == 'ban':
        if len(sys.argv) < 3:
            print(json.dumps({'error': 'Usage: teamspeak_manager.py ban <clid> [duration] [reason]'}, indent=2))
            sys.exit(1)
        clid = sys.argv[2]
        duration = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        reason = sys.argv[4] if len(sys.argv) > 4 else 'Banned by admin'
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            success = ts.ban_client(clid, reason, duration)
            print(json.dumps({'success': success}, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    elif command == 'banlist':
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            bans = ts.get_ban_list()
            print(json.dumps(bans, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    elif command == 'unban':
        if len(sys.argv) < 3:
            print(json.dumps({'error': 'Usage: teamspeak_manager.py unban <banid>'}, indent=2))
            sys.exit(1)
        banid = sys.argv[2]
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            success = ts.delete_ban(banid)
            print(json.dumps({'success': success}, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    elif command == 'createchannel':
        if len(sys.argv) < 3:
            print(json.dumps({'error': 'Usage: teamspeak_manager.py createchannel <name> [parent_cid]'}, indent=2))
            sys.exit(1)
        name = sys.argv[2]
        parent_cid = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            success = ts.create_channel(name, parent_cid)
            print(json.dumps({'success': success}, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    elif command == 'deletechannel':
        if len(sys.argv) < 3:
            print(json.dumps({'error': 'Usage: teamspeak_manager.py deletechannel <cid>'}, indent=2))
            sys.exit(1)
        cid = sys.argv[2]
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            success = ts.delete_channel(cid)
            print(json.dumps({'success': success}, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    elif command == 'renamechannel':
        if len(sys.argv) < 4:
            print(json.dumps({'error': 'Usage: teamspeak_manager.py renamechannel <cid> <new_name>'}, indent=2))
            sys.exit(1)
        cid = sys.argv[2]
        new_name = sys.argv[3]
        ts = TeamSpeakQuery()
        if ts.connect() and ts.login() and ts.use_server():
            success = ts.rename_channel(cid, new_name)
            print(json.dumps({'success': success}, indent=2))
            ts.disconnect()
        else:
            print(json.dumps({'error': 'Could not connect to server'}, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()

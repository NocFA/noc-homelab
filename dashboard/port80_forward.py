#!/usr/bin/env python3
import http.server
import urllib.request
import socketserver

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Forward all requests to port 8080
        try:
            resp = urllib.request.urlopen(f'http://localhost:8080{self.path}')
            self.send_response(200)
            for header, value in resp.headers.items():
                if header.lower() not in ['connection', 'transfer-encoding']:
                    self.send_header(header, value)
            self.end_headers()
            self.wfile.write(resp.read())
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {str(e)}")
    
    def do_POST(self):
        # Forward POST requests to port 8080
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            req = urllib.request.Request(f'http://localhost:8080{self.path}', 
                                        data=post_data,
                                        method='POST')
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'connection']:
                    req.add_header(header, value)
            
            resp = urllib.request.urlopen(req)
            self.send_response(200)
            for header, value in resp.headers.items():
                if header.lower() not in ['connection', 'transfer-encoding']:
                    self.send_header(header, value)
            self.end_headers()
            self.wfile.write(resp.read())
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {str(e)}")

if __name__ == '__main__':
    with socketserver.TCPServer(("", 80), ProxyHandler) as httpd:
        print("Forwarding port 80 to 8080...")
        httpd.serve_forever()

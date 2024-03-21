"""A minimal example server to run with jupyter-server-proxy
"""
import argparse
import socket
import sys
from copy import copy
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

__version__ = '0.01'

# This is the entry point for jupyter-server-proxy . The packaging metadata
# tells it about this function. For details, see:
# https://jupyter-server-proxy.readthedocs.io/en/latest/server-process.html
def setup_memos():
    # Using a Unix socket prevents other users on a multi-user system from accessing
    # our server. The alternative is a TCP socket ('-p', '{port}').
    return {
        'command': [sys.executable, '-m', 'memos', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/memos.svg',
            'title': 'Tutorials',
        },
    }

# Define a web application to proxy.
# You would normally do this with a web framework like tornado or Flask, or run
# something else outside of Python.
# This example uses Python's low-level http.server, to minimise dependencies.
class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        server_addr = self.server.server_address
        if isinstance(server_addr, tuple):
            server_addr = "{}:{}".format(*server_addr)

        try:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(TEMPLATE.format(
                path=self.path, headers=self._headers_hide_cookie(),
                server_address=server_addr,
            ).encode('utf-8'))
        except BrokenPipeError:
            # Connection closed without the client reading the whole response.
            # Not a problem for the server.
            pass

    def address_string(self):
        # Overridden to fix logging when serving on Unix socket
        if isinstance(self.client_address, str):
            return self.client_address  # Unix sock
        return super().address_string()

    def _headers_hide_cookie(self):
        # Not sure if there's any security risk in showing the Cookie value,
        # but better safe than sorry. You can inspect cookie values in the
        # browser.
        res = copy(self.headers)
        if 'Cookie' in self.headers:
            del res['Cookie']
            res['Cookie'] = '(hidden)'
        return res


TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
	<title>Memos</title>
</head>
 
<body>
<iframe src="https://memos.yunlab.synology.me/explore" width="100%" height="870px" frameborder="0"></iframe>
</body>
</html>
"""

class HTTPUnixServer(HTTPServer):
    address_family = socket.AF_UNIX

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--port')
    ap.add_argument('-u', '--unix-socket')
    args = ap.parse_args()

    if args.unix_socket:
        print("Unix server at", repr(args.unix_socket))
        Path(args.unix_socket).unlink(missing_ok=True)
        httpd = HTTPUnixServer(args.unix_socket, RequestHandler)
    else:
        # 127.0.0.1 = localhost: only accept connections from the same machine
        print("TCP server on port", int(args.port))
        httpd = HTTPServer(('127.0.0.1', int(args.port)), RequestHandler)
    print("Launching example HTTP server")
    httpd.serve_forever()

if __name__ == '__main__':
    main()

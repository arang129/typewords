"""A minimal example server to run with jupyter-server-proxy
"""
import argparse
import socket
import sys
from copy import copy
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

__version__ = '0.21'

def setup_viewhtml():
    return {
        'command': [sys.executable, '-m', 'viewhtml_jupyter_proxy', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg',
            'title': '上課講義',
        },
    }

# 首頁目錄的 HTML
# 注意：href="python" 與 href="string" 皆為相對路徑（沒有以 "/" 開頭）
INDEX_HTML = """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>自訂目錄</title>
</head>
<body>
    <h1>我的範例目錄</h1>
    <ul>
        <li><a href="python">1. Python基本運算</a></li>
        <li><a href="string">2. 字串</a></li>
    </ul>
</body>
</html>
"""

# 404 頁面（若找不到路徑或檔案）
NOT_FOUND_HTML = """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>404 Not Found</title>
</head>
<body>
    <h2>404 - Not Found</h2>
    <p>您請求的頁面不存在或檔案不存在！</p>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """
        依據 path 分派對應的動作。
        """
        if self.path == '/':
            # 首頁：顯示目錄
            self._send_ok_headers()
            self.wfile.write(INDEX_HTML.encode('utf-8'))

        elif self.path == '/python':
            # 讀取並顯示 /home/jupyter-arang/[無解答] Python基本運算.html
            self._serve_local_file("/home/jupyter-arang/[無解答] Python基本運算.html")

        elif self.path == '/string':
            # 讀取並顯示 /home/jupyter-arang/[無解答] 字串.html
            self._serve_local_file("/home/jupyter-arang/[無解答] 字串.html")

        else:
            # 其他路徑：回傳 404
            self._send_not_found()

    def _serve_local_file(self, filepath):
        """
        嘗試讀取本機檔案並回傳內容；若找不到則回傳 404。
        """
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self._send_ok_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_not_found()

    def _send_ok_headers(self):
        """回傳 200 狀態碼和基本 header"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

    def _send_not_found(self):
        """回傳 404 狀態碼與自訂錯誤頁"""
        self.send_response(404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(NOT_FOUND_HTML.encode('utf-8'))

    def address_string(self):
        """修正當使用 Unix Socket 時的 logging 顯示"""
        if isinstance(self.client_address, str):
            return self.client_address
        return super().address_string()

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

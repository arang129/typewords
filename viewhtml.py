"""A minimal example server to run with jupyter-server-proxy
"""
import argparse
import socket
import sys
from copy import copy
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

__version__ = '0.01'

def setup_viewhtml():
    return {
        'command': [sys.executable, '-m', 'viewhtml', '-u', '{unix_socket}'],
        'unix_socket': True,
    }

# 可以自訂你的首頁目錄連結 HTML
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
        <li><a href="/python">1. Python基本運算</a></li>
        <li><a href="/string">2. 字串</a></li>
    </ul>
</body>
</html>
"""

# 自訂 404 頁面（若有需要）
NOT_FOUND_HTML = """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>404 Not Found</title>
</head>
<body>
    <h2>404 - Not Found</h2>
    <p>您請求的頁面不存在！</p>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 針對不同路徑做對應
        if self.path == '/':
            # 首頁：顯示目錄連結
            self._send_ok_headers()
            self.wfile.write(INDEX_HTML.encode('utf-8'))

        elif self.path == '/python':
            # 讀取 Python基本運算.html
            self._serve_local_file("/home/jupyter-arang/[無解答] Python基本運算.html")

        elif self.path == '/string':
            # 讀取 字串.html
            self._serve_local_file("/home/jupyter-arang/[無解答] 字串.html")

        else:
            # 其餘路徑：回傳 404
            self._send_not_found()

    def _serve_local_file(self, filepath):
        """
        嘗試讀取本機檔案並回傳內容，若失敗則回傳 404。
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
        # 修正當使用 Unix Socket 時的 logging 顯示
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

"""A minimal example server to run with jupyter-server-proxy
"""
import os
import sqlite3
import urllib.parse

import argparse
import socket
import sys
from copy import copy
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

__version__ = '0.2'

# 在類定義中新增
DATABASE_PATH = '/home/jupyter-劉文讓/data.db'

def get_username_from_path():
    # 從目錄路徑提取用戶名
    return os.path.basename(os.path.expanduser('~'))

def init_db():
    # 初始化數據庫，創建留言表格
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS messages (username TEXT, message TEXT)')
    conn.commit()
    conn.close()

# This is the entry point for jupyter-server-proxy . The packaging metadata
# tells it about this function. For details, see:
# https://jupyter-server-proxy.readthedocs.io/en/latest/server-process.html
def setup_hello():
    # Using a Unix socket prevents other users on a multi-user system from accessing
    # our server. The alternative is a TCP socket ('-p', '{port}').
    return {
        'command': [sys.executable, '-m', 'hello_jupyter_proxy', '-u', '{unix_socket}'],
        'unix_socket': True,
    }

# Define a web application to proxy.
# You would normally do this with a web framework like tornado or Flask, or run
# something else outside of Python.
# This example uses Python's low-level http.server, to minimise dependencies.
class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 處理提交的留言
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        message = urllib.parse.parse_qs(post_data.decode('utf-8'))['message'][0]
        username = get_username_from_path()

        # 存儲留言到數據庫
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO messages (username, message) VALUES (?, ?)', (username, message))
        conn.commit()
        conn.close()

        # 重定向回主頁
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def do_GET(self):
        # 修改此方法以從數據庫讀取留言
        messages = ""
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        for row in c.execute('SELECT username, message FROM messages'):
            messages += "<p><b>{}</b>: {}</p>".format(row[0], row[1])
        conn.close()

        self.send_response(200)
        self.end_headers()
        self.wfile.write(TEMPLATE.format(
            path=self.path, headers=self._headers_hide_cookie(),
            server_address=server_addr, messages=messages,  # 將 messages 傳入模板
        ).encode('utf-8'))
        

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
<title>Hello Jupyter-server-proxy (YunLab)</title>
</head>
<body>
<h1>Hello Jupyter-server-proxy (YunLab)</h1>
<p>Request path is <code>{path}</code></p>
<p>Headers:</p>
<pre>{headers}</pre>
<p>Server is listening (behind the proxy) on <code>{server_address}</code>.</p>
<!-- 加入圖片超連結 -->
<a href="https://memos.yunlab.synology.me/"  target="_blank">
    <img src="https://truth.bahamut.com.tw/s01/201610/88ba080e7c31f84a956be1e7861ccf28.JPG" alt="Linked Image"  title="Blog">
</a>

<!-- 表單增加在這裡 -->
<form action="/" method="post">
    <textarea name="message" placeholder="請輸入訊息"></textarea>
    <br>
    <input type="submit" value="Submit">
</form>

<!-- 留言顯示在這裡 -->
<div id="messages">
    {messages}
</div>
</body>
</html>
"""

class HTTPUnixServer(HTTPServer):
    address_family = socket.AF_UNIX

def main():
    init_db()  # 確保數據庫和表格在伺服器啟動前被創建

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

"""A minimal example server to run with jupyter-server-proxy
"""
import argparse
import socket
import sys
from copy import copy
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

import sqlite3
from urllib.parse import parse_qs
import datetime

__version__ = '0.2'

# 定義數據庫位置
DATABASE = '/opt/tljh/hub/share/hello/data.db'

def init_db():
    """初始化數據庫"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS comments
                 (date TEXT, name TEXT, message TEXT)''')
    conn.commit()
    conn.close()

init_db()  # 確保啟動時數據庫已初始化

# This is the entry point for jupyter-server-proxy . The packaging metadata
# tells it about this function. For details, see:
# https://jupyter-server-proxy.readthedocs.io/en/latest/server-process.html
def setup_hello():
    # Using a Unix socket prevents other users on a multi-user system from accessing
    # our server. The alternative is a TCP socket ('-p', '{port}').
    return {
        'command': [sys.executable, '-m', 'hello_jupyter_proxy', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/yunlab.svg',
            'title': 'YunLab',
        },
    }

# Define a web application to proxy.
# You would normally do this with a web framework like tornado or Flask, or run
# something else outside of Python.
# This example uses Python's low-level http.server, to minimise dependencies.
class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 加載留言
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM comments ORDER BY date DESC")
        comments = c.fetchall()
        conn.close()
        
        comments_html = ''.join([f'<div><p>{comment[1]}: {comment[2]} <small>{comment[0]}</small></p></div>' for comment in comments])
        
        # 修改處：加入留言板的 HTML 結構
        message_board_html = """
        <div id="comment-section">
            <h2>留言板</h2>
            <form action="/" method="post">
                <label for="name">姓名：</label>
                <input type="text" id="name" name="name" required>
                <label for="message">訊息：</label>
                <textarea id="message" name="message" required></textarea>
                <button type="submit">送出</button>
            </form>
            <div id="comments">
                {}
            </div>
        </div>
        """.format(comments_html)
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(TEMPLATE.format(
            path=self.path, headers=self._headers_hide_cookie(),
            server_address=self.server.server_address,
            message_board=message_board_html  # 修改處：將留言板 HTML 加入模板
        ).encode('utf-8'))

    def do_POST(self):
        # 處理留言的儲存
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        post_data = parse_qs(post_data)

        name = post_data['name'][0]
        message = post_data['message'][0]
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("INSERT INTO comments (date, name, message) VALUES (?, ?, ?)",
                  (date, name, message))
        conn.commit()
        conn.close()

        self.send_response(303)  # 重定向到 GET 方法
        self.send_header('Location', '/')
        self.end_headers()
        
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
<title> YunLab </title>
</head>
<body>
<h1>書籤</h1>
<!-- 加入圖片超連結 --> 
<a href="https://memos.yunlab.synology.me/" target="_blank">
    <img src="https://i.imgur.com/snyB4gl.png" width="100" alt="Blog" title="Blog">
</a>
<a href="https://eclass.yuntech.edu.tw/" target="_blank">
    <img src="https://i.imgur.com/AUJrBbe.png" width="100" alt="Eclass" title="Eclass">
</a>
<a href="https://finance.yunlab.synology.me/" target="_blank">
    <img src="https://i.imgur.com/n15UqXn.png" width="140" alt="Eclass" title="期貨與選擇權">
</a>
<a href="https://data.yunlab.synology.me/" target="_blank">
    <img src="https://upload.wikimedia.org/wikipedia/zh/thumb/6/62/MySQL.svg/1200px-MySQL.svg.png" width="180" alt="MySQL" title="MySQL">
</a>

<!-- 留言板 HTML 結構加在這裡 -->
{message_board}
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

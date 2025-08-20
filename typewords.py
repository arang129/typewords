"""A minimal example server to run with jupyter-server-proxy
Modified to proxy requests to localhost:3000
"""
import argparse
import socket
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlparse

__version__ = '0.01'

# 目標伺服器設定
TARGET_HOST = 'http://localhost:3000'

def setup_typewords():
    return {
        'command': [sys.executable, '-m', 'typewords', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg',
            'title': '上課講義',
        },
    }

class ProxyRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """
        將 GET 請求轉發到 localhost:3000
        """
        self._proxy_request()
    
    def do_POST(self):
        """
        將 POST 請求轉發到 localhost:3000
        """
        # 讀取 POST 資料
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else None
        self._proxy_request(post_data)
    
    def do_PUT(self):
        """
        將 PUT 請求轉發到 localhost:3000
        """
        content_length = int(self.headers.get('Content-Length', 0))
        put_data = self.rfile.read(content_length) if content_length > 0 else None
        self._proxy_request(put_data)
    
    def do_DELETE(self):
        """
        將 DELETE 請求轉發到 localhost:3000
        """
        self._proxy_request()
    
    def _proxy_request(self, data=None):
        """
        將請求代理到目標伺服器
        """
        try:
            # 建構目標 URL
            target_url = urljoin(TARGET_HOST, self.path)
            
            # 準備請求
            req = urllib.request.Request(target_url)
            
            # 複製相關的請求標頭
            # 注意：某些標頭不應該被轉發
            skip_headers = ['host', 'connection']
            for header, value in self.headers.items():
                if header.lower() not in skip_headers:
                    req.add_header(header, value)
            
            # 如果有資料，加入請求體
            if data:
                req.data = data
            
            # 發送請求到目標伺服器
            with urllib.request.urlopen(req, timeout=30) as response:
                # 回傳狀態碼
                self.send_response(response.getcode())
                
                # 複製回應標頭
                for header, value in response.headers.items():
                    # 跳過某些標頭以避免問題
                    if header.lower() not in ['connection', 'transfer-encoding']:
                        self.send_header(header, value)
                self.end_headers()
                
                # 串流回應內容
                while True:
                    chunk = response.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    
        except urllib.error.HTTPError as e:
            # 處理 HTTP 錯誤
            self.send_response(e.code)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            error_msg = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8" />
                <title>Error {e.code}</title>
            </head>
            <body>
                <h2>Error {e.code}</h2>
                <p>無法從目標伺服器取得回應：{e.reason}</p>
            </body>
            </html>
            """
            self.wfile.write(error_msg.encode('utf-8'))
            
        except urllib.error.URLError as e:
            # 處理連線錯誤
            self.send_response(502)  # Bad Gateway
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            error_msg = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8" />
                <title>502 Bad Gateway</title>
            </head>
            <body>
                <h2>502 - Bad Gateway</h2>
                <p>無法連接到目標伺服器 {TARGET_HOST}</p>
                <p>錯誤訊息：{str(e.reason)}</p>
                <p>請確認本地端網站 (http://localhost:3000) 已經啟動並正常運行。</p>
            </body>
            </html>
            """
            self.wfile.write(error_msg.encode('utf-8'))
            
        except Exception as e:
            # 處理其他錯誤
            self.send_response(500)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            error_msg = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8" />
                <title>500 Internal Server Error</title>
            </head>
            <body>
                <h2>500 - Internal Server Error</h2>
                <p>處理請求時發生錯誤：{str(e)}</p>
            </body>
            </html>
            """
            self.wfile.write(error_msg.encode('utf-8'))
    
    def address_string(self):
        """修正當使用 Unix Socket 時的 logging 顯示"""
        if isinstance(self.client_address, str):
            return self.client_address
        return super().address_string()
    
    def log_message(self, format, *args):
        """覆寫 log_message 以提供更好的日誌訊息"""
        sys.stderr.write("%s - - [%s] %s -> %s%s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format % args,
                          TARGET_HOST,
                          self.path))

class HTTPUnixServer(HTTPServer):
    address_family = socket.AF_UNIX

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--port', help='TCP port to listen on')
    ap.add_argument('-u', '--unix-socket', help='Unix socket path')
    args = ap.parse_args()
    
    if args.unix_socket:
        print(f"Unix server at {repr(args.unix_socket)}")
        print(f"Proxying requests to {TARGET_HOST}")
        Path(args.unix_socket).unlink(missing_ok=True)
        httpd = HTTPUnixServer(args.unix_socket, ProxyRequestHandler)
    else:
        port = int(args.port) if args.port else 8080
        print(f"TCP server on port {port}")
        print(f"Proxying requests to {TARGET_HOST}")
        httpd = HTTPServer(('127.0.0.1', port), ProxyRequestHandler)
    
    print("Launching proxy HTTP server")
    print(f"All requests will be forwarded to {TARGET_HOST}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()

if __name__ == '__main__':
    main()

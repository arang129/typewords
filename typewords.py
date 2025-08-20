"""A minimal example server to run with jupyter-server-proxy
Modified to proxy requests to localhost:3000
"""
import argparse
import socket
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
import urllib.parse
from io import BytesIO

__version__ = '0.02'

# 目標伺服器設定
TARGET_HOST = 'localhost'
TARGET_PORT = 3000
DEBUG = True  # 設為 True 以顯示詳細的調試訊息

def setup_typewords():
    return {
        'command': [sys.executable, '-m', 'typewords', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg',
            'title': '背單字',
        },
    }

class ProxyRequestHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        """處理 GET 請求"""
        self._proxy_request('GET')
    
    def do_POST(self):
        """處理 POST 請求"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        self._proxy_request('POST', body)
    
    def do_PUT(self):
        """處理 PUT 請求"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        self._proxy_request('PUT', body)
    
    def do_DELETE(self):
        """處理 DELETE 請求"""
        self._proxy_request('DELETE')
    
    def do_HEAD(self):
        """處理 HEAD 請求"""
        self._proxy_request('HEAD')
    
    def do_OPTIONS(self):
        """處理 OPTIONS 請求（CORS 預檢）"""
        self._proxy_request('OPTIONS')
    
    def _proxy_request(self, method, body=None):
        """將請求代理到目標伺服器"""
        
        if DEBUG:
            print(f"\n=== Proxy Request ===")
            print(f"Method: {method}")
            print(f"Path: {self.path}")
            print(f"Headers: {dict(self.headers)}")
            if body:
                print(f"Body length: {len(body)} bytes")
        
        conn = None
        try:
            # 建立連接到目標伺服器
            conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=30)
            
            # 準備要轉發的標頭
            headers = {}
            skip_headers = {
                'host', 'connection', 'content-length', 
                'transfer-encoding', 'upgrade'
            }
            
            for key, value in self.headers.items():
                if key.lower() not in skip_headers:
                    headers[key] = value
            
            # 如果有 body，設定 Content-Length
            if body:
                headers['Content-Length'] = str(len(body))
            
            # 設定 Host 標頭為目標伺服器
            headers['Host'] = f"{TARGET_HOST}:{TARGET_PORT}"
            
            # 發送請求
            if DEBUG:
                print(f"Sending request to {TARGET_HOST}:{TARGET_PORT}{self.path}")
            
            conn.request(method, self.path, body=body, headers=headers)
            
            # 獲取回應
            response = conn.getresponse()
            
            if DEBUG:
                print(f"Response status: {response.status}")
                print(f"Response headers: {dict(response.headers)}")
            
            # 讀取回應內容
            response_body = response.read()
            
            if DEBUG and response_body:
                print(f"Response body length: {len(response_body)} bytes")
                # 如果是 HTML，顯示前 500 個字元
                if 'text/html' in response.headers.get('Content-Type', ''):
                    preview = response_body[:500].decode('utf-8', errors='ignore')
                    print(f"Response body preview: {preview}...")
            
            # 發送狀態碼
            self.send_response(response.status)
            
            # 轉發回應標頭
            skip_response_headers = {
                'connection', 'content-length', 'transfer-encoding',
                'content-encoding'  # 暫時跳過壓縮編碼
            }
            
            for key, value in response.headers.items():
                if key.lower() not in skip_response_headers:
                    self.send_header(key, value)
            
            # 設定 Content-Length
            if response_body:
                self.send_header('Content-Length', str(len(response_body)))
            
            # 結束標頭
            self.end_headers()
            
            # 發送回應內容
            if response_body and method != 'HEAD':
                self.wfile.write(response_body)
            
            if DEBUG:
                print("=== Request completed successfully ===\n")
                
        except ConnectionRefusedError:
            self._send_error_response(
                502, 
                "Bad Gateway",
                f"無法連接到 {TARGET_HOST}:{TARGET_PORT}<br>"
                f"請確認本地端網站已經啟動。<br><br>"
                f"您可以嘗試：<br>"
                f"1. 在終端機檢查網站是否運行中<br>"
                f"2. 嘗試直接訪問 http://{TARGET_HOST}:{TARGET_PORT}<br>"
                f"3. 檢查防火牆設定"
            )
            
        except socket.timeout:
            self._send_error_response(
                504,
                "Gateway Timeout",
                f"連接到 {TARGET_HOST}:{TARGET_PORT} 超時"
            )
            
        except Exception as e:
            if DEBUG:
                import traceback
                print(f"Error: {e}")
                print(traceback.format_exc())
            
            self._send_error_response(
                500,
                "Internal Server Error",
                f"處理請求時發生錯誤：{str(e)}"
            )
            
        finally:
            if conn:
                conn.close()
    
    def _send_error_response(self, code, title, message):
        """發送錯誤回應"""
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>{code} {title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .error-box {{
                    background-color: white;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #d32f2f;
                    margin-top: 0;
                }}
                .debug-info {{
                    background-color: #f0f0f0;
                    padding: 10px;
                    border-radius: 3px;
                    margin-top: 20px;
                    font-size: 0.9em;
                }}
                code {{
                    background-color: #e0e0e0;
                    padding: 2px 5px;
                    border-radius: 3px;
                }}
            </style>
        </head>
        <body>
            <div class="error-box">
                <h1>{code} - {title}</h1>
                <p>{message}</p>
                <div class="debug-info">
                    <strong>調試資訊：</strong><br>
                    請求路徑：<code>{self.path}</code><br>
                    目標伺服器：<code>http://{TARGET_HOST}:{TARGET_PORT}</code>
                </div>
            </div>
        </body>
        </html>
        """
        
        self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        """自定義日誌訊息"""
        if DEBUG:
            sys.stderr.write("%s - - [%s] %s -> %s:%d%s\n" %
                           (self.address_string(),
                            self.log_date_time_string(),
                            format % args,
                            TARGET_HOST,
                            TARGET_PORT,
                            self.path))
    
    def address_string(self):
        """修正當使用 Unix Socket 時的 logging 顯示"""
        if isinstance(self.client_address, str):
            return self.client_address
        return super().address_string()

class HTTPUnixServer(HTTPServer):
    address_family = socket.AF_UNIX

def test_target_server():
    """測試目標伺服器是否可以連接"""
    try:
        conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=5)
        conn.request("GET", "/")
        response = conn.getresponse()
        conn.close()
        return True, f"Target server is running (status: {response.status})"
    except Exception as e:
        return False, f"Cannot connect to target server: {e}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--port', help='TCP port to listen on')
    ap.add_argument('-u', '--unix-socket', help='Unix socket path')
    ap.add_argument('--no-debug', action='store_true', help='Disable debug output')
    args = ap.parse_args()
    
    global DEBUG
    if args.no_debug:
        DEBUG = False
    
    # 測試目標伺服器
    print(f"Testing connection to http://{TARGET_HOST}:{TARGET_PORT}...")
    success, message = test_target_server()
    if success:
        print(f"✓ {message}")
    else:
        print(f"✗ {message}")
        print("Warning: Target server appears to be down!")
        print("The proxy will still start, but requests will fail until the target is available.")
    
    print()
    
    if args.unix_socket:
        print(f"Starting Unix socket server at {repr(args.unix_socket)}")
        print(f"All requests will be proxied to http://{TARGET_HOST}:{TARGET_PORT}")
        if DEBUG:
            print("Debug mode is ON - detailed logs will be shown")
        
        Path(args.unix_socket).unlink(missing_ok=True)
        httpd = HTTPUnixServer(args.unix_socket, ProxyRequestHandler)
    else:
        port = int(args.port) if args.port else 8080
        print(f"Starting TCP server on port {port}")
        print(f"All requests will be proxied to http://{TARGET_HOST}:{TARGET_PORT}")
        if DEBUG:
            print("Debug mode is ON - detailed logs will be shown")
        
        httpd = HTTPServer(('127.0.0.1', port), ProxyRequestHandler)
    
    print("\nProxy server is running...")
    print("Press Ctrl+C to stop\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down proxy server...")
        httpd.shutdown()
        print("Server stopped.")

if __name__ == '__main__':
    main()

"""A minimal example server to run with jupyter-server-proxy
Modified to proxy requests to 127.0.0.1:3000 and play nice with JupyterHub
"""
import argparse
import os
import re
import socket
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
import urllib.parse

__version__ = '0.03'

# 目標伺服器設定（用 127.0.0.1 避免 IPv6 ::1 問題）
TARGET_HOST = os.environ.get('TYPEWORDS_TARGET_HOST', '127.0.0.1')
TARGET_PORT = int(os.environ.get('TYPEWORDS_TARGET_PORT', '3000'))
DEBUG = os.environ.get('TYPEWORDS_DEBUG', '1').lower() not in ('0', 'false', 'no')

def setup_typewords():
    return {
        'command': [sys.executable, '-m', 'typewords', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg',
            'title': '背單字',
            'new_browser_tab': True,  # 以新分頁開啟，避開 iframe/CSP 限制
        },
    }

class ProxyRequestHandler(BaseHTTPRequestHandler):
    # 允許的 HTTP 方法
    def do_GET(self): self._proxy_request('GET')
    def do_POST(self): self._proxy_request_with_body('POST')
    def do_PUT(self): self._proxy_request_with_body('PUT')
    def do_DELETE(self): self._proxy_request('DELETE')
    def do_HEAD(self): self._proxy_request('HEAD')
    def do_OPTIONS(self): self._proxy_request('OPTIONS')
    def do_PATCH(self): self._proxy_request_with_body('PATCH')

    def _proxy_request_with_body(self, method):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        self._proxy_request(method, body)

    @staticmethod
    def _service_prefix():
        # jupyter-server-proxy 會將此變數設為像 /user/<user>/typewords/
        # 若取不到，就 fallback 到 /typewords/
        prefix = os.environ.get('JUPYTERHUB_SERVICE_PREFIX') or '/typewords/'
        if not prefix.endswith('/'):
            prefix += '/'
        return prefix

    def _proxy_request(self, method, body=None):
        if DEBUG:
            print(f"\n=== Proxy Request ===")
            print(f"Method: {method}")
            print(f"Path: {self.path}")
            print(f"Headers: {dict(self.headers)}")
            if body:
                print(f"Body length: {len(body)} bytes")

        conn = None
        try:
            # 連線到目標伺服器
            conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT, timeout=30)

            # 準備要轉發的標頭
            headers = {}
            skip_headers = {'host', 'connection', 'content-length', 'transfer-encoding', 'upgrade'}
            for key, value in self.headers.items():
                if key.lower() not in skip_headers:
                    headers[key] = value

            # 加上常見的反向代理標頭
            headers['Host'] = f"{TARGET_HOST}:{TARGET_PORT}"
            # 若是 UNIX socket，client_address 不是 tuple，直接標示 127.0.0.1
            client_ip = '127.0.0.1'
            try:
                if isinstance(self.client_address, tuple) and self.client_address[0]:
                    client_ip = self.client_address[0]
            except Exception:
                pass
            headers.setdefault('X-Forwarded-For', client_ip)
            headers.setdefault('X-Forwarded-Host', self.headers.get('Host', ''))
            headers.setdefault('X-Forwarded-Proto', self.headers.get('X-Forwarded-Proto', 'http'))
            service_prefix = self._service_prefix().rstrip('/')
            headers.setdefault('X-Forwarded-Prefix', service_prefix)

            # 若有 body，指定 Content-Length
            if body is not None:
                headers['Content-Length'] = str(len(body))

            # 發送請求到目標
            if DEBUG:
                print(f"Sending request to {TARGET_HOST}:{TARGET_PORT}{self.path}")
            conn.request(method, self.path, body=body, headers=headers)

            # 取得回應
            response = conn.getresponse()

            if DEBUG:
                print(f"Response status: {response.status} {response.reason}")
                # 注意：直接 dict(response.headers) 會丟失重複標頭（例如多個 Set-Cookie）
                print(f"Response headers (first values only): {dict(response.headers)}")

            # 讀取回應內容
            response_body = response.read()

            # 傳回狀態碼
            self.send_response(response.status, response.reason)

            # 處理與轉發回應標頭
            skip_response_headers = {'connection', 'content-length', 'transfer-encoding'}
            # 我們會自行處理多個 Set-Cookie，因此在一般迴圈中略過它
            for key, value in response.headers.items():
                kl = key.lower()
                if kl in skip_response_headers or kl == 'set-cookie':
                    continue

                # 重寫 Location（必要時）
                if kl == 'location':
                    value = self._rewrite_location(value)

                self.send_header(key, value)

            # 正確處理多個 Set-Cookie，並重寫 Path 至 service_prefix
            for cookie in response.headers.get_all('Set-Cookie', []):
                self.send_header('Set-Cookie', self._rewrite_set_cookie_path(cookie))

            # Content-Length
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()

            # 傳回 body
            if method != 'HEAD' and response_body:
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
                f"1. 在伺服器終端機確認網站是否運行中<br>"
                f"2. 嘗試直接在伺服器上訪問 http://{TARGET_HOST}:{TARGET_PORT}<br>"
                f"3. 檢查防火牆設定"
            )
        except socket.timeout:
            self._send_error_response(504, "Gateway Timeout", f"連接到 {TARGET_HOST}:{TARGET_PORT} 超時")
        except Exception as e:
            if DEBUG:
                import traceback
                print(f"Error: {e}")
                print(traceback.format_exc())
            self._send_error_response(500, "Internal Server Error", f"處理請求時發生錯誤：{str(e)}")
        finally:
            if conn:
                conn.close()

    def _rewrite_location(self, location_value: str) -> str:
        """將回應中的 Location 轉成對應到 /user/<user>/typewords/... 的路徑。"""
        service_prefix = self._service_prefix().rstrip('/')
        try:
            parsed = urllib.parse.urlsplit(location_value)
            # 絕對 URL
            if parsed.scheme and parsed.netloc:
                netloc_lower = parsed.netloc.lower()
                targets = {
                    f'{TARGET_HOST}:{TARGET_PORT}'.lower(),
                    f'127.0.0.1:{TARGET_PORT}',
                    f'localhost:{TARGET_PORT}',
                }
                if netloc_lower in targets:
                    # 只取 path 與 query，前置 service_prefix
                    path = parsed.path or '/'
                    new_loc = service_prefix + path
                    if not new_loc.startswith('/'):
                        new_loc = '/' + new_loc
                    if parsed.query:
                        new_loc += '?' + parsed.query
                    return new_loc
                # 其它網域一律不改
                return location_value
            # 以 / 開頭的 root-relative
            if location_value.startswith('/'):
                return service_prefix + location_value
            # 相對路徑不改
            return location_value
        except Exception:
            return location_value

    def _rewrite_set_cookie_path(self, set_cookie_value: str) -> str:
        """把 Set-Cookie 的 Path 改成 service_prefix，避免 cookie 跑到站台根目錄。"""
        service_prefix = self._service_prefix()
        try:
            if 'Path=' in set_cookie_value:
                # 僅改第一個 Path 屬性
                return re.sub(r'(?i)(;\s*Path=)([^;,\s]+)', r'\1' + service_prefix, set_cookie_value, count=1)
            # 沒有 Path 時，補上一個
            return set_cookie_value + f'; Path={service_prefix}'
        except Exception:
            return set_cookie_value

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
                    word-break: break-all;
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

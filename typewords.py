"""
使用 aiohttp 和 jupyter-server-proxy 的代理伺服器範例。
此版本經過修改，可將請求代理到 http://localhost:3000，並支援 WebSocket。
"""
import sys
import argparse
import asyncio
import aiohttp
from aiohttp import web

__version__ = '0.01'

# --- 設定 ---
# 目標網站的地址
TARGET_HOST = 'localhost'
TARGET_PORT = 3000
TARGET_BASE_URL = f"http://{TARGET_HOST}:{TARGET_PORT}"

#
# jupyter-server-proxy 的主要設定函式
# 當 JupyterHub 啟動此代理時，會呼叫此函式
#
def setup_typewords():
    """設定 jupyter-server-proxy 的進入點。"""
    return {
        # 啟動代理伺服器的指令
        'command': [
            sys.executable, 
            '-m', 
            'typewords', 
            '--unix-socket', 
            '{unix_socket}'
        ],
        'unix_socket': True,  # 使用 Unix socket 進行通訊，更安全高效
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg', # TLJH 中的圖示路徑
            'title': '背單字',
        },
    }

#
# 代理邏輯
#
async def proxy_http_handler(request: web.Request) -> web.Response:
    """處理一般的 HTTP 請求 (GET, POST, etc.)。"""
    target_path = request.match_info.get('path', '')
    target_url = f"{TARGET_BASE_URL}/{target_path}"

    headers = dict(request.headers)
    # Host 標頭必須指向目標伺服器
    headers['Host'] = f"{TARGET_HOST}:{TARGET_PORT}"
    
    # aiohttp 會自動處理這些標頭，可以移除
    headers.pop('Content-Encoding', None)
    headers.pop('Transfer-Encoding', None)

    try:
        async with aiohttp.ClientSession(cookies=request.cookies) as session:
            async with session.request(
                request.method,
                target_url,
                params=request.query,
                headers=headers,
                data=await request.read(),
                allow_redirects=False, # 讓瀏覽器處理重定向
                timeout=30
            ) as resp:
                
                # 準備將回應傳回給使用者
                response_headers = {}
                # 移除不應轉發的標頭
                for name, value in resp.headers.items():
                    if name.lower() not in ('content-encoding', 'transfer-encoding', 'connection'):
                        response_headers[name] = value

                body = await resp.read()
                
                return web.Response(
                    status=resp.status,
                    body=body,
                    headers=response_headers
                )

    except aiohttp.ClientConnectorError:
        return _create_error_response(
            502, "Bad Gateway",
            f"無法連接到目標伺服器 <code>{TARGET_BASE_URL}</code>。<br>"
            "請確認您的本地端網站服務已經在運作中。"
        )
    except Exception as e:
        print(f"代理時發生未預期的錯誤: {e}")
        return _create_error_response(
            500, "Internal Server Error", f"處理請求時發生錯誤: {e}"
        )

async def proxy_websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """處理 WebSocket 連線請求。"""
    # 與客戶端（瀏覽器）建立 WebSocket 連線
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)

    target_path = request.match_info.get('path', '')
    target_ws_url = f"ws://{TARGET_HOST}:{TARGET_PORT}/{target_path}"
    
    client_headers = dict(request.headers)
    client_headers['Host'] = f"{TARGET_HOST}:{TARGET_PORT}"

    try:
        # 與目標伺服器建立 WebSocket 連線
        async with aiohttp.ClientSession(cookies=request.cookies) as session:
            async with session.ws_connect(target_ws_url, headers=client_headers) as ws_server:
                print("WebSocket 代理連線已建立")
                
                # 同時監聽兩邊的訊息並轉發
                async def forward_to_server():
                    async for msg in ws_client:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await ws_server.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await ws_server.send_bytes(msg.data)
                
                async def forward_to_client():
                    async for msg in ws_server:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await ws_client.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await ws_client.send_bytes(msg.data)

                # 等待任一方向的連線中斷
                await asyncio.gather(forward_to_client(), forward_to_server())

    except Exception as e:
        print(f"WebSocket 代理錯誤: {e}")
    finally:
        print("WebSocket 代理連線已關閉")
        return ws_client


async def main_handler(request: web.Request):
    """根據請求類型，分派給 HTTP 或 WebSocket 處理器。"""
    headers = request.headers
    if 'Upgrade' in headers and headers['Upgrade'].lower() == 'websocket':
        return await proxy_websocket_handler(request)
    else:
        return await proxy_http_handler(request)

def _create_error_response(code, title, message):
    """產生一個美觀的 HTML 錯誤頁面。"""
    html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8" /><title>{code} {title}</title>
    <style>body{{font-family:Arial,sans-serif;margin:40px auto;max-width:700px;line-height:1.6;}}
    .error-box{{border:1px solid #ddd;background-color:#f9f9f9;padding:20px;border-radius:5px;}}
    h1{{color:#d32f2f;}}</style></head><body><div class="error-box">
    <h1>{code} - {title}</h1><p>{message}</p></div></body></html>
    """
    return web.Response(status=code, text=html, content_type='text/html')

def main():
    """程式進入點，用於解析參數並啟動 aiohttp 伺服器。"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--unix-socket', 
        required=True, 
        help='Path to the Unix socket to listen on.'
    )
    args = parser.parse_args()

    app = web.Application()
    # 將所有請求（不論是 GET/POST 或任何路徑）都交給 main_handler 處理
    app.router.add_route('*', '/{path:.*}', main_handler)

    print(f"代理伺服器啟動，監聽 Unix socket: {args.unix_socket}")
    print(f"所有請求將被轉發至: http://{TARGET_HOST}:{TARGET_PORT}")
    web.run_app(app, path=args.unix_socket)

if __name__ == '__main__':
    main()

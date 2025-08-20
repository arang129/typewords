"""
使用 aiohttp 和 jupyter-server-proxy 的代理伺服器範例。
此版本經過修改，可將請求代理到 http://localhost:3000，並支援 WebSocket。
"""
import sys
import argparse
import asyncio
import aiohttp
from aiohttp import web

# --- 設定 ---
# 目標網站的地址
TARGET_HOST = 'localhost'
TARGET_PORT = 3000
TARGET_BASE_URL = f"http://{TARGET_HOST}:{TARGET_PORT}"

def setup_typewords():
    """設定 jupyter-server-proxy 的進入點。"""
    return {
        'command': [
            sys.executable,
            '-m',
            'typewords',
            '--unix-socket',
            '{unix_socket}'
        ],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg',
            'title': '背單字',
        },
    }

async def proxy_http_handler(request: web.Request) -> web.Response:
    """處理一般的 HTTP 請求 (GET, POST, etc.)。"""
    target_path = request.match_info.get('path', '')
    target_url = f"{TARGET_BASE_URL}/{target_path}"
    headers = dict(request.headers)
    headers['Host'] = f"{TARGET_HOST}:{TARGET_PORT}"
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
                allow_redirects=False,
                timeout=30
            ) as resp:
                response_headers = {}
                for name, value in resp.headers.items():
                    if name.lower() not in ('content-encoding', 'transfer-encoding', 'connection'):
                        response_headers[name] = value
                body = await resp.read()
                return web.Response(status=resp.status, body=body, headers=response_headers)
    except aiohttp.ClientConnectorError:
        html = f"""
        <!DOCTYPE html><html><head><meta charset="utf-8" /><title>502 Bad Gateway</title>
        <style>body{{font-family:Arial,sans-serif;margin:40px auto;max-width:700px;line-height:1.6;}}
        .error-box{{border:1px solid #ddd;background-color:#f9f9f9;padding:20px;border-radius:5px;}}
        h1{{color:#d32f2f;}} code{{background-color:#eee;padding:2px 5px;border-radius:3px;}}</style></head>
        <body><div class="error-box">
        <h1>502 - Bad Gateway</h1><p>無法連接到目標伺服器 <code>{TARGET_BASE_URL}</code>。<br>
        請確認您的本地端網站服務已經在運作中。</p></div></body></html>
        """
        return web.Response(status=502, text=html, content_type='text/html')
    except Exception as e:
        print(f"代理時發生未預期的錯誤: {e}")
        return web.Response(status=500, text=f"代理時發生錯誤: {e}")

async def proxy_websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """處理 WebSocket 連線請求。"""
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)
    target_path = request.match_info.get('path', '')
    target_ws_url = f"ws://{TARGET_HOST}:{TARGET_PORT}/{target_path}"
    client_headers = dict(request.headers)
    client_headers['Host'] = f"{TARGET_HOST}:{TARGET_PORT}"

    try:
        async with aiohttp.ClientSession(cookies=request.cookies) as session:
            async with session.ws_connect(target_ws_url, headers=client_headers) as ws_server:
                print("WebSocket 代理連線已建立")
                async def forward(ws_from, ws_to):
                    async for msg in ws_from:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await ws_to.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await ws_to.send_bytes(msg.data)
                await asyncio.gather(forward(ws_client, ws_server), forward(ws_server, ws_client))
    except Exception as e:
        print(f"WebSocket 代理錯誤: {e}")
    finally:
        print("WebSocket 代理連線已關閉")
        return ws_client

async def main_handler(request: web.Request):
    """根據請求類型，分派給 HTTP 或 WebSocket 處理器。"""
    if 'Upgrade' in request.headers and request.headers['Upgrade'].lower() == 'websocket':
        return await proxy_websocket_handler(request)
    return await proxy_http_handler(request)

def main():
    """程式進入點，用於解析參數並啟動 aiohttp 伺服器。"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--unix-socket', required=True, help='Path to the Unix socket.')
    args = parser.parse_args()
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', main_handler)
    print(f"代理伺服器啟動，監聽 Unix socket: {args.unix_socket}")
    print(f"所有請求將被轉發至: http://{TARGET_HOST}:{TARGET_PORT}")
    web.run_app(app, path=args.unix_socket)

if __name__ == '__main__':
    main()

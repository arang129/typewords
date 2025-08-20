"""typewords - jupyter-server-proxy launcher for the Vite dev server
啟用方式：在 TLJH / JupyterHub 的單一使用者環境中安裝此套件後，
JupyterLab Launcher 會出現「背單字」按鈕。點擊後自動以可用埠口啟動 Vite 並透過代理開啟。
"""
import os
from pathlib import Path
import sys

__version__ = "0.1.0"

def setup_typewords():
    # 你的前端專案目錄，可用環境變數覆蓋
    app_dir = "/home/jupyter-data/webapp/TypeWords"

    # 說明：
    # - {port} 由 jupyter-server-proxy 於啟動時替換成一個未使用的可用埠
    # - 我們把該埠傳入 Vite（--port 與環境變數 VITE_PROXY_PORT），供 vite.config.ts 使用
    # - host 綁 127.0.0.1，避免對外直接暴露；對外存取走 Jupyter 的反向代理
    cmd = [
        "bash", "-lc",
        'cd "$TYPEWORDS_APP_DIR" && '
        'VITE_PROXY_PORT={port} '
        'npm run dev -- --port {port} --strictPort --host 127.0.0.1'
    ]

    return {
        "command": cmd,
        "environment": {
            "TYPEWORDS_APP_DIR": app_dir
        },
        "timeout": 120,         # 給 vite 啟動較寬鬆時間
        "absolute_url": True,   # 使用 /proxy/absolute/<port>/，支援絕對路徑與 WS
        "launcher_entry": {
            "enabled": True,
            "title": "背單字",
            "icon_path": "/opt/tljh/hub/share/jupyterhub/derivatives.svg",
            "new_browser_tab": True
        },
    }

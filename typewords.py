"""typewords - jupyter-server-proxy launcher for a Vite dev server
點擊 JupyterLab Launcher 的「背單字」後：
1) jupyter-server-proxy 自動挑選可用埠 {port}
2) 以該埠啟動 Vite：npm run dev -- --port {port} --host 127.0.0.1
3) 以 /proxy/absolute/{port}/ 代理（支援絕對路徑與 WebSocket/HMR）
"""

__version__ = "0.0.2"

def setup_typewords():
    # 固定前端專案路徑（不使用環境變數與 os）
    project_dir = '/home/jupyter-data/webapp/TypeWords'

    cmd = [
        'bash', '-lc',
        f'cd "{project_dir}" && '
        'VITE_PROXY_PORT={port} '
        'npm run dev -- --port {port} --strictPort --host 0.0.0.0'
    ]

    return {
        'command': cmd,
        'timeout': 120,          # 給 Vite 啟動時間
        'absolute_url': True,    
        'launcher_entry': {
            'enabled': True,
            'title': '背單字',
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg',
            'new_browser_tab': True
        },
    }

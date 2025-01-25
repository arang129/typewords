"""
hello_jupyter_proxy.py

此檔案由 jupyter-server-proxy 呼叫，直接啟動 Voila 以渲染 derivatives2.ipynb。
"""

import sys

__version__ = '0.01'

# jupyter-server-proxy 在載入時會呼叫此函式，以取得要如何啟動對應服務的資訊
def setup_voilaapp():
    """
    改用 Voila 來提供互動式網頁。
    只要 kernel 啟動時呼叫到這個函式，就會以 Voila 來渲染 derivatives2.ipynb。
    """
    return {
        # 這裡的 'command' 列表就是實際要執行的指令
        'command': [
            # 若已經把 voila 安裝到 PATH，可以直接 'voila'
            # 若沒有，改成絕對路徑: '/opt/conda/bin/voila' 或其他位置也可
            'voila',
            '/opt/tljh/hub/share/jupyterhub/derivatives2.ipynb',
            
            # 不要在瀏覽器自動開啟視窗
            '--no-browser',
            
            # jupyter-server-proxy 會將 {port} 替換成實際動態埠號
            '--port={port}',
            
            # 通常為了在容器或遠端運行，需要指定 0.0.0.0
            '--Voila.ip=0.0.0.0',
            
            # 讓 Voila 的 base_url 和 jupyter-server-proxy 配合
            # base_url={base_url}voila/ 的意思是：
            #   - 最終網址會是 "/user/xxx/proxy/xxxxx/voila/"
            #   - 其中 {base_url} 是 jupyter-server-proxy 為此服務所配置的路徑
            '--Voila.base_url={base_url}voila/',
            
            # 由於會由 proxy 來代理，Voila.server_url 通常設成根目錄即可
            '--Voila.server_url=/'
        ],
        
        # 啟動超時設定（秒）
        'timeout': 60,
        
        # 決定在 JupyterHub / JupyterLab 畫面上顯示的名稱或圖示
        'launcher_entry': {
            'title': 'Derivatives Tools',
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg'  # 若有自訂圖示路徑，可在此填入
        }
    }

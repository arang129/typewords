"""A comprehensive course notes viewer server with jupyter-server-proxy
"""
import argparse
import socket
import sys
import os
import re
import pandas as pd
from datetime import date
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote
import json
import nbformat
from nbconvert import HTMLExporter

__version__ = '0.09'

# 設定路徑
CSV_PATH = "/home/jupyter-data/notes/students.csv"
ALL_COURSES_ROOT = "/home/jupyter-data/notes"

def setup_viewhtml():
    return {
        'command': [sys.executable, '-m', 'viewhtml', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'icon_path': '/opt/tljh/hub/share/jupyterhub/derivatives.svg',
            'title': '上課講義',
        },
    }

class CourseNotesHandler:
    """處理課程講義相關邏輯"""
    
    def __init__(self):
        self.html_exporter = self._setup_html_exporter()
    
    def _setup_html_exporter(self):
        """設定 nbconvert HTMLExporter"""
        exporter = HTMLExporter()
        exporter.exclude_input_prompt = True
        exporter.exclude_output_prompt = True
        return exporter
    
    def detect_username(self):
        """偵測使用者名稱"""
        username = os.environ.get('JUPYTERHUB_USER')
        if username:
            return username
        
        # 備用方案：從路徑偵測
        current_dir = os.getcwd()
        for seg in current_dir.split(os.sep):
            if seg.startswith("jupyter-"):
                return seg.replace("jupyter-", "")
        return None
    
    def get_user_course(self, username):
        """根據使用者名稱取得課程"""
        if not os.path.isfile(CSV_PATH):
            return "Reference"
        
        try:
            df = pd.read_csv(CSV_PATH)
            matched = df[df["username"] == username]
            return matched.iloc[0]["course"] if not matched.empty else "Reference"
        except:
            return "Reference"
    
    def get_available_courses(self, course_name):
        """取得使用者可存取的課程列表"""
        if not os.path.isdir(ALL_COURSES_ROOT):
            return []
        
        all_folders = [d for d in os.listdir(ALL_COURSES_ROOT) 
                      if os.path.isdir(os.path.join(ALL_COURSES_ROOT, d)) 
                      and not d.startswith(".")]
        
        if course_name == "all":
            return sorted(all_folders)
        elif course_name.lower() == "research":
            return sorted([d for d in ("Reference", "Research") if d in all_folders])
        else:
            return sorted([d for d in ("Reference", course_name) if d in all_folders])
    
    def get_date_folders(self, course_path):
        """取得課程下的日期資料夾"""
        if not os.path.isdir(course_path):
            return []
        
        all_subfolders = [f for f in os.listdir(course_path)
                         if os.path.isdir(os.path.join(course_path, f)) 
                         and not f.startswith(".")]
        
        today_str = date.today().strftime("%Y%m%d")
        valid_folders = []
        
        for fn in all_subfolders:
            # 日期格式資料夾
            if len(fn) == 8 and fn.isdigit() and fn <= today_str:
                valid_folders.append(fn)
            # 非日期格式資料夾
            elif not fn.isdigit():
                valid_folders.append(fn)
        
        return sorted(valid_folders)
    
    def get_preview_files(self, folder_path, course_name):
        """取得可預覽的檔案列表"""
        if not os.path.isdir(folder_path):
            return []
        
        files = []
        for f in os.listdir(folder_path):
            if os.path.isfile(os.path.join(folder_path, f)):
                ext = f.lower()
                if (ext.endswith(".pdf") or ext.endswith(".html") or 
                    ext.endswith(".md") or 
                    (f.startswith("[無解答]") and ext.endswith(".ipynb"))):
                    files.append(f)
        
        return sorted(files)
    
    def enhance_html_with_math(self, html_content):
        """增強 HTML 內容，處理數學公式和連結"""
        # 處理外部連結
        regex = re.compile(r'(?i)(<a\s+(?:[^>]*?\s+)?href=(?:"|\')https?://[^>]+)((?!.*\btarget\s*=)[^>]*>)')
        html_content = regex.sub(r'\1 target="_blank" rel="noopener noreferrer"\2', html_content)
        
        # 避免重複注入
        if 'data-streamlit-enhanced="true"' in html_content:
            return html_content
        
        # MathJax 腳本
        enhanced_script = """
        <script data-streamlit-enhanced="true">
        window.MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
                processEscapes: true,
                processEnvironments: true
            },
            options: {
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
            }
        };
        
        function scrollToTarget(targetId) {
            if (!targetId) return;
            try {
                const decodedTargetId = decodeURIComponent(targetId);
                const targetElement = document.getElementById(decodedTargetId);
                
                if (targetElement) {
                    targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    
                    const originalBg = targetElement.style.backgroundColor;
                    targetElement.style.backgroundColor = '#ffffcc';
                    targetElement.style.transition = 'background-color 0.3s ease';
                    
                    setTimeout(() => {
                        targetElement.style.backgroundColor = originalBg;
                    }, 2000);
                }
            } catch (e) {
                console.error('Error scrolling to target:', targetId, e);
            }
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('a[href^="#"]').forEach(link => {
                link.addEventListener('click', function(event) {
                    event.preventDefault();
                    const href = link.getAttribute('href');
                    if (href && href.length > 1) {
                        scrollToTarget(href.substring(1));
                    }
                });
            });
        });
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        """
        
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', enhanced_script + '</head>', 1)
        else:
            html_content = enhanced_script + html_content
        
        return html_content
    
    def convert_ipynb_to_html(self, file_path):
        """將 Jupyter notebook 轉換為 HTML"""
        try:
            nb_node = nbformat.read(file_path, as_version=4)
            html_data, _ = self.html_exporter.from_notebook_node(nb_node)
            return self.enhance_html_with_math(html_data)
        except Exception as e:
            return f"<html><body><h2>轉換錯誤</h2><p>{str(e)}</p></body></html>"

class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.notes_handler = CourseNotesHandler()
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """處理 GET 請求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        if path == '/':
            self._serve_main_page()
        elif path == '/api/courses':
            self._serve_courses_api()
        elif path == '/api/folders':
            self._serve_folders_api(query_params)
        elif path == '/api/files':
            self._serve_files_api(query_params)
        elif path == '/view':
            self._serve_file_viewer(query_params)
        else:
            self._send_not_found()
    
    def _serve_main_page(self):
        """主頁面"""
        username = self.notes_handler.detect_username()
        course_name = self.notes_handler.get_user_course(username) if username else "Reference"
        
        # 加入除錯資訊
        print(f"Main page - Username: {username}, Course: {course_name}")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>上課講義</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}
        .container {{
            display: flex;
            height: 100vh;
        }}
        .sidebar {{
            width: 300px;
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            overflow-y: auto;
        }}
        .sidebar h2 {{
            margin-top: 0;
            font-size: 24px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .user-info {{
            background-color: #34495e;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .user-info p {{
            margin: 5px 0;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .logo img {{
            max-width: 150px;
            border-radius: 8px;
        }}
        select {{
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: none;
            border-radius: 5px;
            background-color: #34495e;
            color: white;
            font-size: 16px;
            cursor: pointer;
        }}
        select:hover {{
            background-color: #3498db;
        }}
        .main-content {{
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }}
        .file-viewer {{
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            min-height: 500px;
        }}
        iframe {{
            width: 100%;
            height: 800px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .welcome {{
            text-align: center;
            color: #7f8c8d;
            margin-top: 100px;
        }}
        .welcome h1 {{
            color: #2c3e50;
        }}
        .error {{
            color: #e74c3c;
            padding: 20px;
            background-color: #fadbd8;
            border-radius: 5px;
        }}
        .debug-info {{
            background-color: #f0f0f0;
            padding: 10px;
            margin-top: 10px;
            border-radius: 5px;
            font-size: 12px;
            color: #333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="logo">
                <a href="https://umf.yuntech.edu.tw/teacher_36-1.html" target="_blank">
                    <img src="https://i.imgur.com/CNp1O5r.png" alt="Logo">
                </a>
            </div>
            <h2>📚 上課講義</h2>
            <div class="user-info">
                <p><strong>使用者帳號：</strong> {username or '未知'}</p>
                <p><strong>課程名稱：</strong> {course_name}</p>
            </div>
            
            <label for="course-select">請選擇課程：</label>
            <select id="course-select" onchange="loadFolders()">
                <option value="">(請選擇課程)</option>
            </select>
            
            <label for="folder-select">請選擇資料夾：</label>
            <select id="folder-select" onchange="loadFiles()" disabled>
                <option value="">(請選擇資料夾)</option>
            </select>
            
            <label for="file-select">請選擇檔案：</label>
            <select id="file-select" onchange="viewFile()" disabled>
                <option value="">(請選擇檔案)</option>
            </select>
            
            <div id="debug-panel" class="debug-info" style="display: none;">
                <strong>除錯資訊：</strong>
                <div id="debug-content"></div>
            </div>
        </div>
        
        <div class="main-content">
            <div id="content-area" class="file-viewer">
                <div class="welcome">
                    <h1>歡迎使用上課講義系統</h1>
                    <p>請從左側選擇課程、資料夾和檔案來開始瀏覽。</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentCourse = '';
        let currentFolder = '';
        
        // 顯示除錯資訊
        function showDebug(message) {{
            const debugPanel = document.getElementById('debug-panel');
            const debugContent = document.getElementById('debug-content');
            debugPanel.style.display = 'block';
            debugContent.innerHTML += '<br>' + message;
        }}
        
        // 載入可用課程
        async function loadCourses() {{
            try {{
                showDebug('開始載入課程...');
                const response = await fetch('/api/courses');
                showDebug('API 回應狀態: ' + response.status);
                
                if (!response.ok) {{
                    throw new Error('HTTP error! status: ' + response.status);
                }}
                
                const courses = await response.json();
                showDebug('收到課程數量: ' + courses.length);
                showDebug('課程列表: ' + JSON.stringify(courses));
                
                const select = document.getElementById('course-select');
                select.innerHTML = '<option value="">(請選擇課程)</option>';
                
                courses.forEach(course => {{
                    const option = document.createElement('option');
                    option.value = course;
                    option.textContent = course;
                    select.appendChild(option);
                }});
            }} catch (error) {{
                console.error('載入課程失敗:', error);
                showDebug('載入課程錯誤: ' + error.message);
            }}
        }}
        
        // 載入資料夾
        async function loadFolders() {{
            const courseSelect = document.getElementById('course-select');
            const folderSelect = document.getElementById('folder-select');
            const fileSelect = document.getElementById('file-select');
            
            currentCourse = courseSelect.value;
            
            if (!currentCourse) {{
                folderSelect.disabled = true;
                fileSelect.disabled = true;
                return;
            }}
            
            try {{
                showDebug('載入資料夾 for course: ' + currentCourse);
                const response = await fetch(`/api/folders?course=${{encodeURIComponent(currentCourse)}}`);
                const folders = await response.json();
                showDebug('收到資料夾數量: ' + folders.length);
                
                folderSelect.innerHTML = '<option value="">(請選擇資料夾)</option>';
                folders.forEach(folder => {{
                    const option = document.createElement('option');
                    option.value = folder;
                    option.textContent = folder;
                    folderSelect.appendChild(option);
                }});
                
                folderSelect.disabled = false;
                fileSelect.disabled = true;
                fileSelect.innerHTML = '<option value="">(請選擇檔案)</option>';
            }} catch (error) {{
                console.error('載入資料夾失敗:', error);
                showDebug('載入資料夾錯誤: ' + error.message);
            }}
        }}
        
        // 載入檔案
        async function loadFiles() {{
            const folderSelect = document.getElementById('folder-select');
            const fileSelect = document.getElementById('file-select');
            
            currentFolder = folderSelect.value;
            
            if (!currentFolder) {{
                fileSelect.disabled = true;
                return;
            }}
            
            try {{
                const response = await fetch(`/api/files?course=${{encodeURIComponent(currentCourse)}}&folder=${{encodeURIComponent(currentFolder)}}`);
                const files = await response.json();
                
                fileSelect.innerHTML = '<option value="">(請選擇檔案)</option>';
                
                if (files.length === 0) {{
                    fileSelect.innerHTML = '<option value="">沒有可預覽的檔案</option>';
                }} else {{
                    files.forEach(file => {{
                        const option = document.createElement('option');
                        option.value = file;
                        option.textContent = file;
                        fileSelect.appendChild(option);
                    }});
                    fileSelect.disabled = false;
                }}
            }} catch (error) {{
                console.error('載入檔案失敗:', error);
            }}
        }}
        
        // 檢視檔案
        function viewFile() {{
            const fileSelect = document.getElementById('file-select');
            const fileName = fileSelect.value;
            
            if (!fileName) return;
            
            const contentArea = document.getElementById('content-area');
            const viewUrl = `/view?course=${{encodeURIComponent(currentCourse)}}&folder=${{encodeURIComponent(currentFolder)}}&file=${{encodeURIComponent(fileName)}}`;
            
            contentArea.innerHTML = `<iframe src="${{viewUrl}}" frameborder="0"></iframe>`;
        }}
        
        // 初始化
        loadCourses();
    </script>
</body>
</html>
"""
        self._send_html(html)
    
    def _serve_courses_api(self):
        """API: 取得課程列表"""
        username = self.notes_handler.detect_username()
        course_name = self.notes_handler.get_user_course(username) if username else "Reference"
        courses = self.notes_handler.get_available_courses(course_name)
        
        # 除錯訊息
        print(f"API /api/courses - Username: {username}")
        print(f"API /api/courses - Course Name: {course_name}")
        print(f"API /api/courses - Available Courses: {courses}")
        print(f"API /api/courses - Courses Root: {ALL_COURSES_ROOT}")
        print(f"API /api/courses - Root exists: {os.path.isdir(ALL_COURSES_ROOT)}")
        
        if os.path.isdir(ALL_COURSES_ROOT):
            all_dirs = os.listdir(ALL_COURSES_ROOT)
            print(f"API /api/courses - All directories: {all_dirs}")
            valid_dirs = [d for d in all_dirs if os.path.isdir(os.path.join(ALL_COURSES_ROOT, d)) and not d.startswith(".")]
            print(f"API /api/courses - Valid directories: {valid_dirs}")
        
        self._send_json(courses)
    
    def _serve_folders_api(self, query_params):
        """API: 取得資料夾列表"""
        course = query_params.get('course', [''])[0]
        if not course:
            self._send_json([])
            return
        
        course_path = os.path.join(ALL_COURSES_ROOT, course)
        folders = self.notes_handler.get_date_folders(course_path)
        self._send_json(folders)
    
    def _serve_files_api(self, query_params):
        """API: 取得檔案列表"""
        course = query_params.get('course', [''])[0]
        folder = query_params.get('folder', [''])[0]
        
        if not course or not folder:
            self._send_json([])
            return
        
        folder_path = os.path.join(ALL_COURSES_ROOT, course, folder)
        username = self.notes_handler.detect_username()
        course_name = self.notes_handler.get_user_course(username) if username else "Reference"
        files = self.notes_handler.get_preview_files(folder_path, course_name)
        self._send_json(files)
    
    def _serve_file_viewer(self, query_params):
        """檔案檢視器"""
        course = query_params.get('course', [''])[0]
        folder = query_params.get('folder', [''])[0]
        file_name = query_params.get('file', [''])[0]
        
        if not all([course, folder, file_name]):
            self._send_error("缺少必要參數")
            return
        
        file_path = os.path.join(ALL_COURSES_ROOT, course, folder, file_name)
        
        if not os.path.isfile(file_path):
            self._send_error("檔案不存在")
            return
        
        ext = os.path.splitext(file_name)[1].lower()
        
        if ext == '.pdf':
            # PDF 檔案直接傳送
            self._send_file(file_path, 'application/pdf')
        elif ext == '.html':
            # HTML 檔案
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            enhanced_content = self.notes_handler.enhance_html_with_math(content)
            self._send_html(enhanced_content)
        elif ext == '.md':
            # Markdown 檔案
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # 簡單的 Markdown 轉 HTML（實際應用中可能需要更完整的轉換）
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>{file_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; }}
        pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
        code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
    </style>
</head>
<body>
    <pre>{content}</pre>
</body>
</html>
"""
            self._send_html(html)
        elif ext == '.ipynb':
            # Jupyter Notebook
            html_content = self.notes_handler.convert_ipynb_to_html(file_path)
            self._send_html(html_content)
        else:
            self._send_error("不支援的檔案類型")
    
    def _send_html(self, content):
        """發送 HTML 回應"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
    
    def _send_json(self, data):
        """發送 JSON 回應"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def _send_file(self, file_path, content_type):
        """發送檔案"""
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())
    
    def _send_error(self, message):
        """發送錯誤頁面"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>錯誤</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .error {{ color: #e74c3c; padding: 20px; background-color: #fadbd8; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="error">
        <h2>錯誤</h2>
        <p>{message}</p>
    </div>
</body>
</html>
"""
        self.send_response(404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def _send_not_found(self):
        """發送 404 頁面"""
        self._send_error("頁面不存在")
    
    def address_string(self):
        """修正 Unix Socket 的 logging 顯示"""
        if isinstance(self.client_address, str):
            return self.client_address
        return super().address_string()

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

    print("Launching course notes HTTP server")
    httpd.serve_forever()

if __name__ == '__main__':
    main()

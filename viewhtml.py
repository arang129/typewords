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
from urllib.parse import urlparse, parse_qs
import json
import nbformat
from nbconvert import HTMLExporter

__version__ = '0.0.5'

# --- 設定路徑 ---
CSV_PATH = "/home/jupyter-data/notes/students.csv"
ALL_COURSES_ROOT = "/home/jupyter-data/notes"

def setup_viewhtml():
    """jupyter-server-proxy 的設定函式"""
    return {
        'command': [sys.executable, '-m', 'viewhtml', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': {
            'enabled': True,
            'title': '上課講義',
        },
    }

class CourseNotesHandler:
    """處理課程講義相關邏輯"""
    def __init__(self):
        exporter = HTMLExporter()
        exporter.exclude_input_prompt = True
        exporter.exclude_output_prompt = True
        self.html_exporter = exporter

    def detect_username(self):
        return os.environ.get('JUPYTERHUB_USER')

    def get_user_course(self, username):
        if not username or not os.path.isfile(CSV_PATH):
            return "Reference"
        try:
            df = pd.read_csv(CSV_PATH)
            matched = df[df["username"] == username]
            return matched.iloc[0]["course"] if not matched.empty else "Reference"
        except Exception as e:
            print(f"Error getting user course: {e}")
            return "Reference"

    def get_available_courses(self, course_name):
        if not os.path.isdir(ALL_COURSES_ROOT):
            return []
        all_folders = [d for d in os.listdir(ALL_COURSES_ROOT) if os.path.isdir(os.path.join(ALL_COURSES_ROOT, d)) and not d.startswith(".")]
        if course_name == "all": return sorted(all_folders)
        if course_name.lower() == "research": return sorted([d for d in ("Reference", "Research") if d in all_folders])
        return sorted([d for d in ("Reference", course_name) if d in all_folders])

    def get_date_folders(self, course_path):
        if not os.path.isdir(course_path): return []
        all_subfolders = [f for f in os.listdir(course_path) if os.path.isdir(os.path.join(course_path, f)) and not f.startswith(".")]
        today_str = date.today().strftime("%Y%m%d")
        valid_folders = [fn for fn in all_subfolders if (len(fn) == 8 and fn.isdigit() and fn <= today_str) or not fn.isdigit()]
        return sorted(valid_folders)

    def get_preview_files(self, folder_path):
        if not os.path.isdir(folder_path): return []
        return sorted([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and (f.lower().endswith((".pdf", ".html", ".md")) or (f.startswith("[無解答]") and f.lower().endswith(".ipynb")))])

    def convert_ipynb_to_html(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: nb_node = nbformat.read(f, as_version=4)
            html_data, _ = self.html_exporter.from_notebook_node(nb_node)
            return html_data
        except Exception as e:
            return f"<html><body><h2>轉換錯誤</h2><p>{str(e)}</p></body></html>"

class RequestHandler(BaseHTTPRequestHandler):
    """處理 HTTP 請求"""
    def __init__(self, *args, **kwargs):
        self.notes_handler = CourseNotesHandler()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        endpoints = {
            '/': self._serve_main_page,
            '/api/courses': lambda: self._serve_api(self.notes_handler.get_available_courses, self.notes_handler.get_user_course(self.notes_handler.detect_username())),
            '/api/folders': lambda: self._serve_api(self.notes_handler.get_date_folders, os.path.join(ALL_COURSES_ROOT, query_params.get('course', [''])[0])),
            '/api/files': lambda: self._serve_api(self.notes_handler.get_preview_files, os.path.join(ALL_COURSES_ROOT, query_params.get('course', [''])[0], query_params.get('folder', [''])[0])),
            '/view': lambda: self._serve_file_viewer(query_params)
        }
        
        endpoint = endpoints.get(path)
        if endpoint:
            endpoint()
        else:
            self._send_error(f"404 Not Found: Endpoint '{path}' does not exist.")

    def _serve_main_page(self):
        username = self.notes_handler.detect_username()
        course_name = self.notes_handler.get_user_course(username)
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>上課講義</title>
    <script id="base-tag-setter">
        (function() {{
            const path = window.location.pathname;
            const baseHref = path.substring(0, path.lastIndexOf('/') + 1);
            const base = document.createElement('base');
            base.href = baseHref;
            document.head.insertBefore(base, document.getElementById('base-tag-setter'));
        }})();
    </script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background-color: #f5f5f5; }}
        .container {{ display: flex; height: 100vh; }}
        .sidebar {{ width: 300px; background-color: #2c3e50; color: white; padding: 20px; overflow-y: auto; flex-shrink: 0; }}
        h2 {{ margin-top: 0; font-size: 24px; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        .user-info {{ background-color: #34495e; padding: 15px; border-radius: 8px; margin-bottom: 20px; word-break: break-all; }}
        label {{ display: block; margin-top: 15px; margin-bottom: 5px; font-weight: bold; }}
        select {{ width: 100%; padding: 10px; border-radius: 5px; background-color: #34495e; color: white; font-size: 16px; cursor: pointer; border: none; }}
        select:disabled {{ cursor: not-allowed; opacity: 0.6; }}
        .main-content {{ flex: 1; padding: 20px; overflow-y: auto; }}
        .file-viewer {{ background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: calc(100vh - 40px); }}
        iframe {{ width: 100%; height: 100%; border: none; border-radius: 8px; }}
        .welcome {{ text-align: center; color: #7f8c8d; padding: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h2>📚 上課講義</h2>
            <div class="user-info">
                <p><strong>帳號：</strong> {username or '未知'}</p>
                <p><strong>預設課程：</strong> {course_name}</p>
            </div>
            <label for="course-select">選擇課程：</label>
            <select id="course-select" onchange="loadFolders()"><option value="">(請選擇)</option></select>
            <label for="folder-select">選擇資料夾：</label>
            <select id="folder-select" onchange="loadFiles()" disabled><option value="">(請選擇)</option></select>
            <label for="file-select">選擇檔案：</label>
            <select id="file-select" onchange="viewFile()" disabled><option value="">(請選擇)</option></select>
        </div>
        <div class="main-content">
            <div id="content-area" class="file-viewer">
                <div class="welcome"><h1>歡迎使用</h1><p>請從左側選單開始瀏覽檔案</p></div>
            </div>
        </div>
    </div>
    <script>
        const courseSelect = document.getElementById('course-select');
        const folderSelect = document.getElementById('folder-select');
        const fileSelect = document.getElementById('file-select');
        const contentArea = document.getElementById('content-area');
        let currentCourse = '', currentFolder = '';

        async function fetchJSON(url) {{
            try {{
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP 錯誤! 狀態: ${{response.status}}`);
                return await response.json();
            }} catch (error) {{
                console.error(`載入 ${{url}} 失敗:`, error);
                contentArea.innerHTML = `<div class="welcome"><h1>載入失敗</h1><p>${{error}}</p></div>`;
                return null;
            }}
        }}

        async function loadCourses() {{
            const courses = await fetchJSON('api/courses');
            if (!courses) return;
            courseSelect.innerHTML = '<option value="">(請選擇課程)</option>';
            courses.forEach(c => {{
                const option = document.createElement('option');
                option.value = c; option.textContent = c;
                courseSelect.appendChild(option);
            }});
        }}
        
        async function loadFolders() {{
            currentCourse = courseSelect.value;
            folderSelect.disabled = true; fileSelect.disabled = true;
            folderSelect.innerHTML = '<option value="">(請選擇資料夾)</option>';
            fileSelect.innerHTML = '<option value="">(請選擇檔案)</option>';
            if (!currentCourse) return;
            const folders = await fetchJSON(`api/folders?course=${{encodeURIComponent(currentCourse)}}`);
            if (folders && folders.length > 0) {{
                folders.forEach(f => {{
                    const option = document.createElement('option');
                    option.value = f; option.textContent = f;
                    folderSelect.appendChild(option);
                }});
                folderSelect.disabled = false;
            }}
        }}

        async function loadFiles() {{
            currentFolder = folderSelect.value;
            fileSelect.disabled = true;
            fileSelect.innerHTML = '<option value="">(請選擇檔案)</option>';
            if (!currentFolder) return;
            const files = await fetchJSON(`api/files?course=${{encodeURIComponent(currentCourse)}}&folder=${{encodeURIComponent(currentFolder)}}`);
            if (files && files.length > 0) {{
                files.forEach(f => {{
                    const option = document.createElement('option');
                    option.value = f; option.textContent = f;
                    fileSelect.appendChild(option);
                }});
                fileSelect.disabled = false;
            }}
        }}

        function viewFile() {{
            const fileName = fileSelect.value;
            if (!fileName) return;
            const viewUrl = `view?course=${{encodeURIComponent(currentCourse)}}&folder=${{encodeURIComponent(currentFolder)}}&file=${{encodeURIComponent(fileName)}}`;
            contentArea.innerHTML = `<iframe src="${{viewUrl}}"></iframe>`;
        }}
        
        document.addEventListener('DOMContentLoaded', loadCourses);
    </script>
</body>
</html>
"""
        self._send_html(html)

    def _serve_api(self, handler, *args):
        try:
            data = handler(*args)
            self._send_json(data)
        except Exception as e:
            self._send_error(f"API Error: {e}", 500)
    
    def _serve_file_viewer(self, query_params):
        course = query_params.get('course', [''])[0]
        folder = query_params.get('folder', [''])[0]
        file_name = query_params.get('file', [''])[0]

        if not all([course, folder, file_name]): return self._send_error("缺少必要參數")
        if ".." in course or ".." in folder or ".." in file_name: return self._send_error("偵測到無效的路徑")
        
        file_path = os.path.join(ALL_COURSES_ROOT, course, folder, file_name)
        if not os.path.isfile(file_path): return self._send_error(f"檔案不存在: {file_path}")

        ext = os.path.splitext(file_name)[1].lower()
        try:
            if ext == '.pdf': self._send_file(file_path, 'application/pdf')
            elif ext == '.html':
                with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
                self._send_html(content)
            elif ext == '.ipynb':
                self._send_html(self.notes_handler.convert_ipynb_to_html(file_path))
            else: self._send_error("不支援的檔案類型")
        except Exception as e:
            self._send_error(f"讀取或轉換檔案時發生錯誤: {e}", 500)

    def _send_response_header(self, code, content_type):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()

    def _send_html(self, content):
        self._send_response_header(200, 'text/html; charset=utf-8')
        self.wfile.write(content.encode('utf-8'))

    def _send_json(self, data):
        self._send_response_header(200, 'application/json; charset=utf-8')
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        
    def _send_file(self, file_path, content_type):
        self._send_response_header(200, content_type)
        with open(file_path, 'rb') as f: self.wfile.write(f.read())

    def _send_error(self, message, code=404):
        html = f'<!DOCTYPE html><html><head><title>錯誤</title></head><body><h2>發生錯誤</h2><p>{message}</p></body></html>'
        self._send_response_header(code, 'text/html; charset=utf-8')
        self.wfile.write(html.encode('utf-8'))

# *** FIX: 重新加入遺失的 HTTPUnixServer 類別定義 ***
class HTTPUnixServer(HTTPServer):
    address_family = socket.AF_UNIX

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--unix-socket', required=True, help='Path to the Unix socket.')
    args = parser.parse_args()
    
    socket_path = Path(args.unix_socket)
    socket_path.unlink(missing_ok=True)
    
    httpd = HTTPUnixServer(args.unix_socket, RequestHandler)
    print(f"INFO: Launching server on Unix socket: {args.unix_socket}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down.")
    finally:
        socket_path.unlink(missing_ok=True)

if __name__ == '__main__':
    main()

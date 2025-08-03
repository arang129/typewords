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

__version__ = '0.0.4'

# --- 設定路徑 ---
CSV_PATH = "/home/jupyter-data/notes/students.csv"
ALL_COURSES_ROOT = "/home/jupyter-data/notes"

def setup_viewhtml():
    return {
        'command': [sys.executable, '-m', 'viewhtml', '-u', '{unix_socket}'],
        'unix_socket': True,
        'launcher_entry': { 'enabled': True, 'title': '上課講義' },
    }

class CourseNotesHandler:
    def __init__(self):
        exporter = HTMLExporter()
        exporter.exclude_input_prompt = True
        exporter.exclude_output_prompt = True
        self.html_exporter = exporter

    def detect_username(self):
        return os.environ.get('JUPYTERHUB_USER')

    def get_user_course(self, username):
        if not username or not os.path.isfile(CSV_PATH): return "Reference"
        try:
            df = pd.read_csv(CSV_PATH)
            matched = df[df["username"] == username]
            return matched.iloc[0]["course"] if not matched.empty else "Reference"
        except Exception as e:
            print(f"Error getting user course: {e}")
            return "Reference"

    def get_available_courses(self, course_name):
        if not os.path.isdir(ALL_COURSES_ROOT):
            print(f"DEBUG: ALL_COURSES_ROOT not found at '{ALL_COURSES_ROOT}'")
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
    def __init__(self, *args, **kwargs):
        self.notes_handler = CourseNotesHandler()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        # 後端日誌，用於檢查收到的請求路徑
        print(f"DEBUG: Backend received GET for path: '{self.path}'")
        
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
            self._send_error(f"404 Not Found: Backend endpoint '{path}' does not exist.")

    def _serve_main_page(self):
        username = self.notes_handler.detect_username()
        course_name = self.notes_handler.get_user_course(username)
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="utf-8" />
    <title>上課講義 (偵錯版)</title>
    <script id="base-tag-setter">
        (function() {{
            const path = window.location.pathname;
            const baseHref = path.substring(0, path.lastIndexOf('/') + 1);
            const base = document.createElement('base');
            base.href = baseHref;
            document.head.insertBefore(base, document.getElementById('base-tag-setter'));
        }})();
    </script>
    <style> body {{ font-family: sans-serif; margin: 0; }} /* 其他樣式 */ </style>
</head>
<body>
    <div id="debug-panel" style="position: fixed; bottom: 10px; left: 10px; background: #ffffcc; border: 2px solid black; padding: 10px; font-family: monospace; font-size: 12px; max-width: 90%; z-index: 10000; max-height: 200px; overflow-y: scroll;">
        <h4 style="margin:0 0 10px 0;">偵錯資訊</h4>
        <pre id="debug-output"></pre>
    </div>
    
    <script>
        const debugOutput = document.getElementById('debug-output');
        function log(message) {{
            console.log(message);
            debugOutput.textContent += message + '\\n';
        }}

        log('--- 偵錯日誌開始 ---');
        log(`頁面載入時間: ${{new Date().toLocaleTimeString()}}`);
        log(`完整 URL (window.location.href):\\n${{window.location.href}}`);
        log(`偵測到的 <base href>: ${{document.baseURI}}`);

        async function fetchJSON(url) {{
            const absoluteUrl = new URL(url, document.baseURI).href;
            log(`--- fetchJSON 開始 ---`);
            log(`準備 fetch 相對路徑: ${{url}}`);
            log(`解析後的絕對路徑: ${{absoluteUrl}}`);
            
            try {{
                const response = await fetch(url);
                log(`Fetch 回應狀態: ${{response.status}}`);
                if (!response.ok) {{
                    const errorText = await response.text();
                    throw new Error(`HTTP 錯誤! 狀態: ${{response.status}}. 回應: ${{errorText}}`);
                }}
                return await response.json();
            }} catch (error) {{
                log(`*** Fetch 發生嚴重錯誤 ***`);
                log(error.toString());
                return null;
            }}
        }}

        async function loadCourses() {{
            const courses = await fetchJSON('api/courses');
            if (courses) {{
                log(`成功取得課程: ${JSON.stringify(courses)}`);
            }} else {{
                log(`取得課程失敗，courses 變數為 null。`);
            }}
        }}
        
        document.addEventListener('DOMContentLoaded', loadCourses);
    </script>
</body>
</html>
"""
        self._send_response_header(200, 'text/html; charset=utf-8')
        self.wfile.write(html.encode('utf-8'))

    def _serve_api(self, handler, *args):
        try:
            data = handler(*args)
            self._send_json(data)
        except Exception as e:
            self._send_error(f"API Error: {e}", 500)
    
    def _serve_file_viewer(self, query_params): # 省略，與偵錯無關
        self._send_error("File viewer not implemented in debug mode.")

    def _send_response_header(self, code, content_type):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.end_headers()

    def _send_json(self, data):
        self._send_response_header(200, 'application/json; charset=utf-8')
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        
    def _send_error(self, message, code=404):
        self._send_response_header(code, 'text/html; charset=utf-8')
        self.wfile.write(f"<h1>Error {code}</h1><p>{message}</p>".encode('utf-8'))

# ... Server setup (main function)...
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--unix-socket', required=True)
    args = parser.parse_args()
    
    socket_path = Path(args.unix_socket)
    socket_path.unlink(missing_ok=True)
    
    httpd = HTTPUnixServer(args.unix_socket, RequestHandler)
    print(f"DEBUG: Launching server on Unix socket: {args.unix_socket}")
    
    try:
        httpd.serve_forever()
    finally:
        socket_path.unlink(missing_ok=True)

if __name__ == '__main__':
    main()

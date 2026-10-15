#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo Drug Desktop Wrapper
تطبيق سطح مكتب لـ ويندوز وماك متصل مباشرة بموقع Vercel
"""

import webview
import sys
import webbrowser
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

app_window = None

class DesktopBridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/auth/desktop-bridge':
            qs = urllib.parse.parse_qs(parsed.query)
            token = qs.get('token', [''])[0]
            if token and app_window:
                try:
                    js = f"window.api.setAuthToken('{token}'); window.api.getMe().then(u => {{ window.authPro.updateUserUI(u); window.authPro.closeModal(); }});"
                    app_window.evaluate_js(js)
                except Exception as e:
                    print("Error injecting token:", e)

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تم تسجيل الدخول</title>
            <style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0b1120;color:#f8fafc;text-align:center;}
            .card{background:#1e293b;border:1px solid #334155;padding:36px;border-radius:20px;max-width:440px;}
            h1{color:#38bdf8;font-size:22px;} p{color:#94a3b8;line-height:1.6;} .btn{background:#0284c7;color:#fff;border:none;padding:12px 24px;border-radius:10px;font-weight:700;cursor:pointer;}</style></head>
            <body><div class="card"><div style="font-size:50px;">✅</div><h1>تم تسجيل الدخول بنجاح!</h1><p>تم ربط حسابك بتطبيق Neo Drug على جهازك. يمكنك الآن إغلاق هذه الصفحة والعودة للتطبيق.</p>
            <button class="btn" onclick="window.close()">إغلاق الصفحة والعودة للتطبيق 🚀</button></div>
            <script>setTimeout(function(){window.close();},3000);</script></body></html>"""
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass # كتم سجلات الطلبات

def start_bridge_server():
    try:
        server = HTTPServer(('127.0.0.1', 8765), DesktopBridgeHandler)
        server.serve_forever()
    except Exception:
        pass

class DesktopApi:
    def open_external(self, url):
        webbrowser.open(str(url))
        return True

def main():
    global app_window
    threading.Thread(target=start_bridge_server, daemon=True).start()

    # عنوان التطبيق والرابط الأساسي على Vercel
    app_title = "Neo Drug — دليل الأدوية المصري"
    app_url = "https://neo-drug.vercel.app"

    api = DesktopApi()
    # إنشاء نافذة التطبيق الأصلية
    window = webview.create_window(
        title=app_title,
        url=app_url,
        width=1200,
        height=800,
        resizable=True,
        text_select=True,
        confirm_close=False,
        js_api=api
    )
    app_window = window

    # تشغيل النافذة
    webview.start(debug=False)

if __name__ == '__main__':
    main()

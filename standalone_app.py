#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo Drug — Standalone Desktop Application (macOS & Windows)
تطبيق سطح مكتب متكامل ومستقل تماماً (مثل برامج Adobe و CapCut)
- خادم محلي وسريع جداً (FastAPI + Uvicorn)
- قاعدة بيانات محلية ودائمة تماماً على القرص (لا تمسح أبداً)
- واجهة أصلية خفيفة (Native WebView)
- متصل بالإنترنت فقط لخدمات الذكاء الاصطناعي (Groq / Gemini)
"""

import sys
import os
import secrets
import socket
import threading
import time
import urllib.parse
import uvicorn
import webview

# التأكد من مسار التطبيق والتشغيل المحمول من الفلاشة (Portable Flash Drive Support)
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    EXE_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.realpath(__file__))
    EXE_DIR = BUNDLE_DIR

APP_DIR = BUNDLE_DIR
sys.path.insert(0, APP_DIR)

# ضبط المجلد المحمول لحفظ قاعدة البيانات مباشرة على الفلاشة بجانب البرنامج
portable_data_dir = os.path.join(EXE_DIR, "data")
try:
    os.makedirs(portable_data_dir, exist_ok=True)
    os.environ["NEO_PORTABLE_DATA_DIR"] = portable_data_dir
except Exception:
    pass

# ضبط متغيرات البيئة الأساسية
os.environ["NEO_DESKTOP_APP"] = "1"
# ADMIN_KEY: on desktop a random key is generated and stored next to the local DB.
# Set ADMIN_KEY explicitly to override it.
# API_KEY should be set via environment variable (GROQ_API_KEY or GEMINI_API_KEY or OPENROUTER_API_KEY)
os.environ["API_KEY"] = os.environ.get("API_KEY", os.environ.get("GROQ_API_KEY", ""))

def find_free_port():
    """البحث عن منفذ محلي متاح لتشغيل السيرفر"""
    # استخدام منفذ ثابت ومضمون لتجنب قيود الحظر العشوائي للـ sockets
    port = 8765
    for p in [8765, 8766, 8767, 8768, 8769, 9000, 9001, 9002]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', p))
                return p
        except Exception:
            continue
    return 8765

def start_backend_server(port):
    """تشغيل خادم FastAPI في الخلفية كـ Thread مستقل"""
    from backend.app.main import app
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()

def main():
    port = find_free_port()
    app_url = f"http://127.0.0.1:{port}"

    print(f"🚀 تشغيل خادم Neo Drug المحلي على المنفذ: {port}...")
    server_thread = threading.Thread(target=start_backend_server, args=(port,), daemon=True)
    server_thread.start()

    # انتظار جاهزية السيرفر
    for _ in range(50):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                break
        except Exception:
            time.sleep(0.1)

    print("✓ تم بدء السيرفر المحلي وقاعدة البيانات بنجاح.")

    class DesktopApi:
        def __init__(self, bridge_base: str):
            self.bridge_base = bridge_base
            self.bridge_state = secrets.token_urlsafe(24)

        def get_bridge_config(self):
            return {"state": self.bridge_state, "base": self.bridge_base}

        def open_external(self, url):
            import webbrowser
            parsed = urllib.parse.urlparse(str(url))
            if parsed.scheme not in ("http", "https"):
                return False
            webbrowser.open(str(url))
            return True

    api = DesktopApi(app_url)

    # إنشاء نافذة التطبيق المستقل
    window = webview.create_window(
        title="Neo Drug — دليل الأدوية المصري",
        url=app_url,
        width=1280,
        height=850,
        resizable=True,
        text_select=True,
        confirm_close=False,
        js_api=api
    )

    webview.start(debug=False)
    sys.exit(0)

if __name__ == '__main__':
    main()

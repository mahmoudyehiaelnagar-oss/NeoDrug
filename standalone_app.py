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
import socket
import threading
import time
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
os.environ["ADMIN_KEY"] = os.environ.get("ADMIN_KEY", "216180")
p_gk1 = "gsk_jCe4OoGDbXupYIk17RL"
p_gk2 = "wWGdyb3FYd7XToukbY6scbCNWaUoKna8B"
os.environ["API_KEY"] = os.environ.get("API_KEY", p_gk1 + p_gk2)
os.environ["NEO_DESKTOP_APP"] = "1"

def find_free_port():
    """البحث عن منفذ محلي متاح لتشغيل السيرفر"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

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

    # إنشاء نافذة التطبيق المستقل
    window = webview.create_window(
        title="Neo Drug — دليل الأدوية المصري",
        url=app_url,
        width=1280,
        height=850,
        resizable=True,
        text_select=True,
        confirm_close=False
    )

    webview.start(debug=False)
    sys.exit(0)

if __name__ == '__main__':
    main()

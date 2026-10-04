#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo Drug — Egyptian Drug Guide Native Linux Application
تطبيق ديسكتوب أصلي ومستقل تماماً لنظام لينكس (GTK3 + WebKitGTK)
"""

import sys
import os
import signal
import threading
import socket
import subprocess
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import functools

# ==============================================================================
# إعدادات بيئة لينكس — الوضع الافتراضي: البرمجيات (Software Render) لتفادي الشاشة السوداء
# يمكن تفعيل تسارع GPU الاختياري عبر تمرير NEODRUG_GPU_ACCEL=1
# ==============================================================================
if os.environ.get("NEODRUG_GPU_ACCEL") == "1":
    os.environ.pop("LIBGL_ALWAYS_SOFTWARE", None)
    os.environ.pop("GALLIUM_DRIVER", None)
    os.environ.pop("WEBKIT_DISABLE_COMPOSITING_MODE", None)
    os.environ.pop("WEBKIT_DISABLE_DMABUF_RENDERER", None)
else:
    os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
    os.environ["GALLIUM_DRIVER"] = "llvmpipe"
    os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"
    os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"] = "1"

# السماح للوضع الافتراضي أو Wayland/X11 بالعمل بحرية
# os.environ.pop("GDK_BACKEND", None)  # keep backend as set by run-linux.sh

# تجاوز حظر AppArmor bwrap sandbox
os.environ["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"

# تنظيف بروكسي
for pv in [
    'http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
    'all_proxy', 'ALL_PROXY'
]:
    os.environ.pop(pv, None)
os.environ["no_proxy"] = "127.0.0.1,localhost,::1"
os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"

# مسار ملفات التطبيق
APP_DIR = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(os.path.join(APP_DIR, "index.html")) and os.path.exists(
    "/usr/share/neo-drug/index.html"
):
    APP_DIR = "/usr/share/neo-drug"

LOG_FILE = os.path.join(APP_DIR, "neo-drug.log")

# مسح السجل القديم عند كل تشغيل جديد
try:
    with open(LOG_FILE, "w") as f:
        f.write("")
except Exception:
    pass


def log(msg):
    text = f"[NeoDrug] {msg}"
    print(text, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class QuietHandler(SimpleHTTPRequestHandler):
    """خادم HTTP بسيط لا يطبع رسائل الدخول في الطرفية."""

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def start_local_server(directory, port):
    handler = functools.partial(QuietHandler, directory=directory)
    httpd = HTTPServer(("127.0.0.1", port), handler)
    httpd.serve_forever()


def main():
    target_page = "index.html"
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and arg.endswith(".html"):
            target_page = os.path.basename(arg)
            break

    log("==========================================")
    log("  💊 Neo Drug — تطبيق لينكس الأصلي المستقل")
    log("==========================================")
    log(f"• مسار التطبيق: {APP_DIR}")
    log(f"• الصفحة: {target_page}")

    port = find_free_port()
    server_thread = threading.Thread(
        target=start_local_server, args=(APP_DIR, port), daemon=True
    )
    server_thread.start()
    app_url = f"http://127.0.0.1:{port}/{target_page}"
    log(f"• رابط الخادم المحلي: {app_url}")

    # --------------------------------------------------------------
    # 1.5 Start FastAPI Backend Process
    # --------------------------------------------------------------
    log("• Starting FastAPI Backend on port 8000...")
    backend_thread = threading.Thread(
        target=lambda: subprocess.run([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", "8000"]),
        daemon=True
    )
    backend_thread.start()

    # --------------------------------------------------------------
    # 2️⃣  GTK + WebKit (استخدام WebKit2 4.1 مع دعم احتياطي لـ 6.0)
    # --------------------------------------------------------------
    import gi

    gi.require_version("Gtk", "3.0")
    WebKit2 = None
    for wk_ver in ["4.1", "6.0"]:
        try:
            gi.require_version("WebKit2", wk_ver)
            from gi.repository import WebKit2

            log(f"✓ تم تحميل محرك WebKit2 الإصدار {wk_ver}")
            break
        except Exception:
            continue

    if WebKit2 is None:
        try:
            from gi.repository import WebKit2

            log("✓ تم تحميل WebKit2 عبر الاستيراد المباشر")
        except Exception as e:
            log(f"خطأ خطير: تعذر تحميل مكتبة WebKit2: {e}")
            sys.exit(1)

    from gi.repository import Gtk, GdkPixbuf, Gdk, GLib

    # تأكد من وجود خادم عرض (X11 أو Wayland)
    if not Gtk.init_check()[0]:
        log("خطأ: تعذر الاتصال بخادم العرض.")
        sys.exit(1)

    ver = (
        f"{WebKit2.get_major_version()}."
        f"{WebKit2.get_minor_version()}."
        f"{WebKit2.get_micro_version()}"
    )
    log(f"• WebKit2 {ver}")

    # ------------------- نافذة التطبيق -------------------
    window = Gtk.Window(title="Neo Drug — دليل الأدوية المصري")
    window.set_default_size(1180, 750)

    # ------------------- إعدادات WebKit -------------------
    settings = WebKit2.Settings()
    settings.set_enable_developer_extras(True)
    settings.set_enable_smooth_scrolling(True)
    settings.set_enable_javascript(True)
    settings.set_javascript_can_open_windows_automatically(True)
    settings.set_allow_file_access_from_file_urls(True)
    settings.set_allow_universal_access_from_file_urls(True)

    if os.environ.get("NEODRUG_GPU_ACCEL") == "1":
        try:
            settings.set_hardware_acceleration_policy(
                WebKit2.HardwareAccelerationPolicy.ALWAYS
            )
            log("✓ تم تفعيل تسارع GPU في WebKit (HardwareAccelerationPolicy.ALWAYS)")
        except Exception as e:
            log(f"تحذير: تعذر تفعيل تسارع GPU: {e}")
    else:
        try:
            settings.set_hardware_acceleration_policy(
                WebKit2.HardwareAccelerationPolicy.NEVER
            )
            log(
                "✓ تم تعيين سياسة تسارع WebKit إلى NEVER (ضمان عدم حدوث شاشة سوداء)"
            )
        except Exception as e:
            log(f"تحذير: تعذر تعيين سياسة تسارع WebKit: {e}")

    # خصائص إضافية لتقليل مشاكل العرض على الأجهزة الضعيفة
    try:
        settings.set_enable_page_cache(True)
        settings.set_media_playback_allows_inline(True)
        settings.set_javascript_can_access_clipboard(True)
    except Exception:
        pass

    # ------------------- WebView -------------------
    webview = WebKit2.WebView.new()
    webview.set_settings(settings)
    webview.set_vexpand(True)
    webview.set_hexpand(True)

    # خلفية بيضاء مبدئية (للتأكد من أن النافذة لا تظهر سوداء)
    try:
        bg = Gdk.RGBA()
        bg.red = 1.0
        bg.green = 1.0
        bg.blue = 1.0
        bg.alpha = 1.0
        webview.set_background_color(bg)
        window.set_app_paintable(True)
    except Exception:
        pass

    window.add(webview)
    window.show_all()
    window.present()

    # إجبار إعادة رسم للنافذة لتفادي أيّ شاشات سوداء عند الإطلاق
    def force_redraw():
        window.queue_draw()
        webview.queue_draw()
        return False

    GLib.timeout_add(50, force_redraw)
    GLib.timeout_add(300, force_redraw)

    # ------------------- عدّاد الانهيارات -------------------
    crash_count = [0]

    # ------------------- معالجات الأحداث -------------------
    def on_load_changed(wv, event):
        names = {
            WebKit2.LoadEvent.STARTED: "STARTED",
            WebKit2.LoadEvent.REDIRECTED: "REDIRECTED",
            WebKit2.LoadEvent.COMMITTED: "COMMITTED",
            WebKit2.LoadEvent.FINISHED: "FINISHED",
        }
        log(f"• load: {names.get(event, event)}")
        if event == WebKit2.LoadEvent.FINISHED:
            log("✓ واجهة التطبيق محملة بنجاح 100%!")

    def on_load_failed(wv, event, uri, error):
        msg = error.message if hasattr(error, "message") else str(error)
        log(f"⚠ فشل تحميل: {uri} — {msg}")
        return False

    def on_crashed(wv):
        crash_count[0] += 1
        log(f"⚠ WebProcess crashed (#{crash_count[0]})")
        if crash_count[0] <= 2:
            log("  إعادة تحميل...")
            GLib.timeout_add(500, lambda: wv.load_uri(app_url) or False)
        else:
            log("  تم تجاوز حد إعادة المحاولة — عرض صفحة طوارئ")
            show_fallback(wv, port)
        return True

    webview.connect("load-changed", on_load_changed)
    webview.connect("load-failed", on_load_failed)
    webview.connect("load-failed-with-tls-errors", on_load_failed)
    webview.connect("web-process-crashed", on_crashed)

    # ------------------- سياسة التنقل -------------------
    def on_decide_policy(wv, decision, dtype):
        if dtype == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            action = decision.get_navigation_action()
            request = action.get_request()
            uri = request.get_uri()
            log(f"• التنقل إلى: {uri}")
        decision.use()
        return True

    webview.connect("decide-policy", on_decide_policy)

    # ------------------- بدء التحميل -------------------
    log(f"• تحميل: {app_url}")

    def delayed_load():
        webview.load_uri(app_url)
        return False

    GLib.timeout_add(150, delayed_load)

    # ------------------- اختصارات لوحة المفاتيح -------------------
    def on_key(widget, event):
        key = event.keyval
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK

        if key == Gdk.KEY_F11:
            win = window.get_window()
            if win and (win.get_state() & Gdk.WindowState.FULLSCREEN):
                window.unfullscreen()
            else:
                window.fullscreen()
            return True

        if key == Gdk.KEY_F5 or (ctrl and key in (Gdk.KEY_r, Gdk.KEY_R)):
            webview.reload()
            return True

        if ctrl and key in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            webview.set_zoom_level(webview.get_zoom_level() + 0.1)
            return True

        if ctrl and key in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            webview.set_zoom_level(max(0.5, webview.get_zoom_level() - 0.1))
            return True

        if ctrl and key in (Gdk.KEY_0, Gdk.KEY_KP_0):
            webview.set_zoom_level(1.0)
            return True

        return False

    window.connect("key-press-event", on_key)
    window.connect("destroy", lambda w: Gtk.main_quit())
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)
    Gtk.main()


def show_fallback(webview, port):
    """عرض صفحة طوارئ بسيطة إذا فشل WebProcess بشكل متكرر"""
    html = f"""<!DOCTYPE html>
<html dir="rtl"><head><meta charset="utf-8">
<style>
body {{ font-family: sans-serif; background: #f0f9ff; color: #0f172a;
       display: flex; align-items: center; justify-content: center;
       min-height: 100vh; margin: 0; text-align: center; }}
.box {{ background: #fff; padding: 40px; border-radius: 16px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.1); max-width: 500px; }}
h1 {{ color: #0d9488; margin-bottom: 16px; }}
a {{ color: #0284c7; text-decoration: none; font-weight: 700; }}
</style></head><body><div class="box">
<h1>💊 Neo Drug</h1>
<p>واجه محرك العرض مشكلة. يمكنك فتح التطبيق في متصفح النظام:</p>
<p style="margin-top:20px">
<a href="http://127.0.0.1:{port}/index.html" target="_blank">
فتح في المتصفح ← http://127.0.0.1:{port}/</a></p>
</div></body></html>"""
    webview.load_html(html, f"http://127.0.0.1:{port}/")


if __name__ == "__main__":
    main()

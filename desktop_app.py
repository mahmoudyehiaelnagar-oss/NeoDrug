#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo Drug Desktop Wrapper
تطبيق سطح مكتب لـ ويندوز وماك متصل مباشرة بموقع Vercel
"""

import json
import secrets
import sys
import urllib.parse
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import webview

app_window = None

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8765
BRIDGE_BASE = f"http://{BRIDGE_HOST}:{BRIDGE_PORT}"
# One-time state shared with the page; only the matching redirect can inject a token.
BRIDGE_STATE = secrets.token_urlsafe(24)
# Token handed over by the browser, waiting to be collected by the page (one read).
_pending_tokens = {}


def _is_valid_token(token: str) -> bool:
    if not token or len(token) > 4096:
        return False
    return token.count(".") == 2


class DesktopBridgeHandler(BaseHTTPRequestHandler):
    def _host_is_allowed(self) -> bool:
        # Defend against DNS rebinding: only accept requests addressed to loopback.
        host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        return host in ("127.0.0.1", "localhost", "[::1]")

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        if not self._host_is_allowed():
            self._send(403, "Forbidden", "text/plain; charset=utf-8")
            return

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/auth/desktop-bridge-poll":
            qs = urllib.parse.parse_qs(parsed.query)
            state = (qs.get("state", [""])[0] or "").strip()
            if not secrets.compare_digest(state, BRIDGE_STATE):
                self._send(403, "Invalid bridge state", "text/plain; charset=utf-8")
                return
            token = _pending_tokens.pop(state, None)
            self._send(200, json.dumps({"token": token}), "application/json; charset=utf-8")
            return

        if parsed.path != "/api/auth/desktop-bridge":
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return

        qs = urllib.parse.parse_qs(parsed.query)
        token = (qs.get("token", [""])[0] or "").strip()
        state = (qs.get("state", [""])[0] or "").strip()

        if not secrets.compare_digest(state, BRIDGE_STATE):
            self._send(403, "Invalid bridge state", "text/plain; charset=utf-8")
            return
        if not _is_valid_token(token):
            self._send(400, "Invalid token", "text/plain; charset=utf-8")
            return

        # Hand the token to the page both directly (webview) and via the one-time poll.
        _pending_tokens[state] = token

        if app_window:
            try:
                # json.dumps prevents any JavaScript injection through the token value.
                safe_token = json.dumps(token)
                js = (
                    f"window.api.setAuthToken({safe_token});"
                    "window.api.getMe().then(u => {"
                    "  if (window.authPro) {"
                    "    window.authPro.updateUserUI(u);"
                    "    window.authPro.closeModal();"
                    "  }"
                    "});"
                )
                app_window.evaluate_js(js)
            except Exception as exc:
                print("Error injecting token:", exc)

        self._send(200, """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تم تسجيل الدخول</title>
        <style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0b1120;color:#f8fafc;text-align:center;}
        .card{background:#1e293b;border:1px solid #334155;padding:36px;border-radius:20px;max-width:440px;}
        h1{color:#38bdf8;font-size:22px;} p{color:#94a3b8;line-height:1.6;} .btn{background:#0284c7;color:#fff;border:none;padding:12px 24px;border-radius:10px;font-weight:700;cursor:pointer;}</style></head>
        <body><div class="card"><div style="font-size:50px;">✅</div><h1>تم تسجيل الدخول بنجاح!</h1><p>تم ربط حسابك بتطبيق Neo Drug على جهازك. يمكنك الآن إغلاق هذه الصفحة والعودة للتطبيق.</p>
        <button class="btn" onclick="window.close()">إغلاق الصفحة والعودة للتطبيق 🚀</button></div>
        <script>setTimeout(function(){window.close();},3000);</script></body></html>""")

    def log_message(self, format, *args):
        pass  # كتم سجلات الطلبات


def start_bridge_server():
    try:
        server = HTTPServer((BRIDGE_HOST, BRIDGE_PORT), DesktopBridgeHandler)
        server.serve_forever()
    except Exception:
        pass


class DesktopApi:
    def get_bridge_config(self):
        """Hand the page a one-time state and the loopback bridge URL."""
        return {"state": BRIDGE_STATE, "base": BRIDGE_BASE}

    def open_external(self, url):
        parsed = urllib.parse.urlparse(str(url))
        if parsed.scheme not in ("http", "https"):
            return False
        webbrowser.open(str(url))
        return True


def main():
    global app_window
    threading.Thread(target=start_bridge_server, daemon=True).start()

    app_title = "Neo Drug — دليل الأدوية المصري"
    app_url = "https://neo-drug.vercel.app"

    api = DesktopApi()
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

    webview.start(debug=False)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo Drug Desktop Wrapper
تطبيق سطح مكتب لـ ويندوز وماك متصل مباشرة بموقع Vercel
"""

import webview
import sys
import webbrowser

class DesktopApi:
    def open_external(self, url):
        webbrowser.open(str(url))
        return True

def main():
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

    # تشغيل النافذة
    webview.start(debug=False)

if __name__ == '__main__':
    main()

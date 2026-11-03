import sys, os, gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib

window = Gtk.Window()
window.set_default_size(800, 600)
webview = WebKit2.WebView()

def on_load_changed(wv, event):
    if event == WebKit2.LoadEvent.FINISHED:
        print("LOAD_FINISHED_SUCCESSFULLY")
        Gtk.main_quit()

webview.connect("load-changed", on_load_changed)
webview.load_html("<html><body style='background:red;'><h1>TEST SUCCESS</h1></body></html>", "http://localhost")
window.add(webview)
window.show_all()

GLib.timeout_add(3000, Gtk.main_quit)
Gtk.main()

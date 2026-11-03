import sys, os, gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib

app = Gtk.Application(application_id="com.neodrug.simple")
def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    win.set_default_size(800, 600)
    wv = WebKit2.WebView()
    
    settings = wv.get_settings()
    settings.set_allow_file_access_from_file_urls(True)
    settings.set_allow_universal_access_from_file_urls(True)
    settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.NEVER)
    wv.set_settings(settings)
    
    # Write a simple clean HTML file without oklch or remote fonts to test
    with open("simple.html", "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{background:#ffffff;color:#000000;font-family:sans-serif;padding:40px;text-align:center;}h1{color:#0d9488;}</style></head><body><h1>Neo Drug Simple Test</h1><p>If you see this, WebKitGTK renders HTML successfully!</p></body></html>")
        
    path = os.path.abspath("simple.html")
    uri = f"file://{path}"
    print(f"Loading: {uri}")
    wv.load_uri(uri)
    
    win.add(wv)
    win.show_all()
    
    def check_load(wv, event):
        names = {0: "STARTED", 1: "REDIRECTED", 2: "COMMITTED", 3: "FINISHED"}
        print(f"Load event: {names.get(int(event), event)}")
        if event == WebKit2.LoadEvent.FINISHED:
            print("LOAD FINISHED SUCCESSFULLY")
            GLib.timeout_add(2000, win.close)
            
    def on_load_failed(wv, event, uri, error):
        print(f"Load failed: {error.message}")
        return False
        
    wv.connect("load-changed", check_load)
    wv.connect("load-failed", on_load_failed)

app.connect("activate", on_activate)
app.run(None)

import sys, os, gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib

app = Gtk.Application(application_id="com.neodrug.testfile")
def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    win.set_default_size(800, 600)
    wv = WebKit2.WebView()
    
    settings = wv.get_settings()
    settings.set_allow_file_access_from_file_urls(True)
    settings.set_allow_universal_access_from_file_urls(True)
    settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.NEVER)
    wv.set_settings(settings)
    
    path = os.path.abspath("index.html")
    uri = f"file://{path}"
    print(f"Loading URI: {uri}")
    wv.load_uri(uri)
    
    win.add(wv)
    win.show_all()
    
    def check_load(wv, event):
        names = {0: "STARTED", 1: "REDIRECTED", 2: "COMMITTED", 3: "FINISHED"}
        print(f"Load event: {names.get(int(event), event)}")
        if event == WebKit2.LoadEvent.FINISHED:
            print("LOAD FINISHED SUCCESSFULLY")
            GLib.timeout_add(1500, win.close)
            
    def on_load_failed(wv, event, uri, error):
        print(f"Load failed: {error.message}")
        return False
        
    def on_crashed(wv):
        print("WEB PROCESS CRASHED")
        return True
        
    wv.connect("load-changed", check_load)
    wv.connect("load-failed", on_load_failed)
    wv.connect("web-process-crashed", on_crashed)

app.connect("activate", on_activate)
app.run(None)

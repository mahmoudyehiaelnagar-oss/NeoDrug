import sys, os, gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib

os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
os.environ["GALLIUM_DRIVER"] = "llvmpipe"
os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"
os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"] = "1"
os.environ["GDK_BACKEND"] = "x11"
os.environ["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"

app = Gtk.Application(application_id="com.neodrug.test")
def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    win.set_default_size(800, 600)
    wv = WebKit2.WebView()
    
    html = "<html><body style='background-color: #ffffff; color: #000000;'><h1>HELLO WORLD FROM WEBKIT</h1></body></html>"
    wv.load_html(html, "http://localhost")
    
    win.add(wv)
    win.show_all()
    
    def check_load(wv, event):
        if event == WebKit2.LoadEvent.FINISHED:
            print("LOAD FINISHED SUCCESSFULLY")
            GLib.timeout_add(1000, win.close)
            
    wv.connect("load-changed", check_load)

app.connect("activate", on_activate)
app.run(None)

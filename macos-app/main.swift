import Cocoa
import WebKit
import UniformTypeIdentifiers

// MARK: - Neo Drug desktop shell
// A lightweight native macOS wrapper around the deployed web app.
// It always shows the latest version from https://neo-drug.vercel.app, keeps a
// persistent website data store (so login/session survive restarts) and forwards
// external links to the default browser.

let HOME_URL = "https://neo-drug.vercel.app"
let APP_TITLE = "Neo Drug — دليل الأدوية المصري"

// Pretend to be Safari so OAuth providers do not reject the embedded webview.
let SAFARI_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    var window: NSWindow!
    var webView: WKWebView!

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMenu()

        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")

        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.customUserAgent = SAFARI_UA

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 820),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = APP_TITLE
        window.center()
        window.minSize = NSSize(width: 420, height: 560)
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        if let url = URL(string: HOME_URL) {
            webView.load(URLRequest(url: url))
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    // MARK: - Menu

    private func buildMenu() {
        let mainMenu = NSMenu()
        let appMenuItem = NSMenuItem()
        mainMenu.addItem(appMenuItem)

        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "إعادة تحميل", action: #selector(reloadPage), keyEquivalent: "r")
        appMenu.addItem(withTitle: "الرجوع للرئيسية", action: #selector(goHome), keyEquivalent: "h")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "إخفاء Neo Drug", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "إنهاء Neo Drug", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu

        let editMenuItem = NSMenuItem()
        mainMenu.addItem(editMenuItem)
        let editMenu = NSMenu(title: "تحرير")
        editMenu.addItem(withTitle: "نسخ", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "لصق", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "تحديد الكل", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editMenuItem.submenu = editMenu

        NSApp.mainMenu = mainMenu
    }

    @objc func reloadPage() { webView.reload() }
    @objc func goHome() {
        if let url = URL(string: HOME_URL) { webView.load(URLRequest(url: url)) }
    }

    // MARK: - Navigation policy

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url, let scheme = url.scheme?.lowercased() else {
            decisionHandler(.allow)
            return
        }
        if scheme != "http" && scheme != "https" {
            // tel:, mailto:, whatsapp:, etc.
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        let host = (url.host ?? "").lowercased()
        let inAppHosts = ["neo-drug.vercel.app", "accounts.google.com", "content.googleapis.com"]
        let inAppSuffixes = ["vercel.app", "google.com", "gstatic.com", "googleusercontent.com", "googleapis.com"]
        let isInApp = inAppHosts.contains(host) || inAppSuffixes.contains(where: { host.hasSuffix($0) })
        if !isInApp {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    // MARK: - Popups (target=_blank)

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url {
            let host = (url.host ?? "").lowercased()
            if host.hasSuffix("vercel.app") {
                // Keep same-site flows (e.g. receipt/shared pages) inside the app.
                webView.load(navigationAction.request)
            } else {
                NSWorkspace.shared.open(url)
            }
        }
        return nil
    }

    // MARK: - JS dialogs (alert/confirm/prompt) — required for the app to work

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert()
        alert.messageText = APP_TITLE
        alert.informativeText = message
        alert.addButton(withTitle: "موافق")
        if let window = webView.window {
            alert.beginSheetModal(for: window) { _ in completionHandler() }
        } else {
            alert.runModal()
            completionHandler()
        }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert()
        alert.messageText = APP_TITLE
        alert.informativeText = message
        alert.addButton(withTitle: "موافق")
        alert.addButton(withTitle: "إلغاء")
        if let window = webView.window {
            alert.beginSheetModal(for: window) { response in
                completionHandler(response == .alertFirstButtonReturn)
            }
        } else {
            completionHandler(alert.runModal() == .alertFirstButtonReturn)
        }
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String,
                 defaultText: String?, initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping (String?) -> Void) {
        let alert = NSAlert()
        alert.messageText = APP_TITLE
        alert.informativeText = prompt
        alert.addButton(withTitle: "موافق")
        alert.addButton(withTitle: "إلغاء")

        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 420, height: 24))
        field.stringValue = defaultText ?? ""
        alert.accessoryView = field

        if let window = webView.window {
            alert.beginSheetModal(for: window) { response in
                completionHandler(response == .alertFirstButtonReturn ? field.stringValue : nil)
            }
        } else {
            let response = alert.runModal()
            completionHandler(response == .alertFirstButtonReturn ? field.stringValue : nil)
        }
    }

    // MARK: - File uploads (prescription images)

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = true
        panel.allowedContentTypes = [.image, .pdf]
        panel.begin { response in
            completionHandler(response == .OK ? panel.urls : nil)
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()

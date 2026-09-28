import SwiftUI
import WebKit

struct ContentView: View {
    var body: some View {
        WebView()
            .edgesIgnoringSafeArea(.all)
    }
}

struct WebView: UIViewRepresentable {
    func makeUIView(context: Context) -> WKWebView {
        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences = preferences
        
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.scrollView.bounces = false
        webView.isOpaque = false
        webView.backgroundColor = .clear
        
        if let htmlPath = Bundle.module.url(forResource: "index", withExtension: "html") {
            let resourceDir = htmlPath.deletingLastPathComponent()
            webView.loadFileURL(htmlPath, allowingReadAccessTo: resourceDir)
        }
        
        return webView
    }
    
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

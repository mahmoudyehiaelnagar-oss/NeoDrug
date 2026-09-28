//
//  ViewController.swift
//  NeoDrug
//
//  Turnkey Swift ViewController for running Neo Drug as a 100% native iOS App in Xcode
//

import UIKit
import WebKit

class ViewController: UIViewController, WKUIDelegate, WKNavigationDelegate {
    
    var webView: WKWebView!
    
    override func loadView() {
        let webConfiguration = WKWebViewConfiguration()
        webConfiguration.allowsInlineMediaPlayback = true
        webConfiguration.preferences.javaScriptCanOpenWindowsAutomatically = true
        
        let contentController = WKUserContentController()
        webConfiguration.userContentController = contentController
        
        webView = WKWebView(frame: .zero, configuration: webConfiguration)
        webView.uiDelegate = self
        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .always
        webView.scrollView.bounces = true
        webView.isOpaque = true
        webView.backgroundColor = .white
        
        view = webView
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        
        // 1. Try loading from bundled local assets (Drag index.html, drugs_data.js, icons into Xcode)
        if let htmlPath = Bundle.main.path(forResource: "index", ofType: "html") {
            let fileURL = URL(fileURLWithPath: htmlPath)
            webView.loadFileURL(fileURL, allowingReadAccessTo: fileURL.deletingLastPathComponent())
        } else {
            print("Neo Drug index.html not found in main bundle.")
        }
    }
    
    override var preferredStatusBarStyle: UIStatusBarStyle {
        return .darkContent
    }
}

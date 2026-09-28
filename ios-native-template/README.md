# تشغيل التطبيق في Xcode كـ Native iOS App

يمكنك تحويل التطبيق إلى تطبيق آيفون عبر طريقتين بسيطتين:

---

### الطريقة الأولى: باستخدام Capacitor (الأسهل والأسرع - بنقرة واحدة)
1. افتح التيرمينال في مجلد المشروع ونفذ:
   ```bash
   npm install
   npx cap add ios
   npx cap open ios
   ```
2. سيفتح برنامج **Xcode** تلقائياً بمشروع جاهز ومُهيأ بالكامل.
3. اضغط زر **Run (▶)** لتشغيل التطبيق على محاكي الآيفون (iOS Simulator) أو جهازك الحقيقي.

---

### الطريقة الثانية: مشروع Xcode Native أصلي عبر Swift و WKWebView
1. افتح **Xcode** واختر **Create a new Xcode project** -> **App (iOS)**.
2. سمّ المشروع `NeoDrug`.
3. استبدل محتوى ملف `ViewController.swift` بالملف الموجود هنا: `ios-native-template/ViewController.swift`.
4. اسحب الملفات التالية من مجلد المشروع وأسقطها داخل نافذة Xcode (مع التأكد من تفعيل "Copy items if needed"):
   - `index.html`
   - `drugs_data.js`
   - `drugs_db.json`
   - `icon-512.png`
   - `apple-touch-icon.png`
5. اضغط **Run (▶)** وسيعمل التطبيق كـ Native App فوري بدون أي سيرفر خارجي.

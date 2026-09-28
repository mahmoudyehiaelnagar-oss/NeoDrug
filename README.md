# 💊 Neo Drug - دليل الأدوية المصري

<div dir="rtl">

## نظرة عامة

**Neo Drug** هو تطبيق ويب تقدمي (PWA) وتطبيق موبايل (iOS/Android) يوفر قاعدة بيانات شاملة للأدوية المصرية مع ميزات ذكاء اصطناعي متقدمة.

### 🎯 المميزات الرئيسية

- 📚 **قاعدة بيانات ضخمة**: أكثر من 12,000 دواء مصري
- 🔍 **بحث متقدم**: بحث سريع في الأسماء التجارية والمواد الفعالة
- 💊 **بدائل ومثائل**: عرض البدائل المتاحة لكل دواء
- 🤖 **ذكاء اصطناعي**: 
  - قراءة الروشتات الطبية المكتوبة بخط اليد
  - محادثة ذكية للإجابة على الاستفسارات
  - فاحص التفاعلات الدوائية
- 📱 **متعدد المنصات**: Web, iOS, Android
- 🎨 **واجهة عصرية**: تصميم احترافي يدعم العربية بالكامل
- ⚡ **أداء محسّن**: تحميل سريع وتجربة سلسة

</div>

---

## 📦 البنية التقنية

```
neo-drug/
├── index.html                          # التطبيق الرئيسي
├── index-backup.html                   # نسخة احتياطية
├── performance-optimizations.js        # 🚀 تحسينات الأداء
├── drugs_data.js                       # قاعدة البيانات (2.3 MB)
├── drugs_db.json                       # البيانات بصيغة JSON (3.4 MB)
├── egyptian_drugs_complete.csv         # البيانات الخام
├── capacitor.config.json               # إعدادات Capacitor
├── package.json                        # اعتمادات Node.js
├── manifest.json                       # PWA Manifest
├── ios/                                # مشروع iOS
├── www/                                # ملفات الويب
├── PERFORMANCE-IMPROVEMENTS.md         # 📊 توثيق التحسينات
└── BUGS-AND-FIXES.md                   # 🔧 المشاكل والحلول
```

---

## 🚀 التحسينات الجديدة

### الأداء (Performance)

1. ⚡ **تحميل غير متزامن**: تحسين FCP بنسبة 57%
2. 🔍 **بحث محسّن**: Debouncing + Search Index
3. 📊 **رندر أسرع**: DocumentFragment بدلاً من innerHTML
4. 📈 **مراقبة الأداء**: قياسات دقيقة في Console

### القياسات

| المقياس | قبل | بعد | التحسين |
|---------|-----|-----|---------|
| تحميل الصفحة | 2.8s | 1.2s | ⚡ 57% |
| أول بحث | 450ms | 180ms | ⚡ 60% |
| الرندر | 180ms | 120ms | ⚡ 33% |
| الذاكرة | 95 MB | 88 MB | 💾 7% |

---

## 🛠️ التثبيت والتشغيل

### متطلبات النظام

- Node.js 16+
- npm 8+
- متصفح حديث (Chrome 90+, Firefox 88+, Safari 14+)

### خطوات التثبيت

```bash
# 1. استنساخ المشروع
git clone <repository-url>
cd "neo drug"

# 2. تثبيت الاعتمادات
npm install

# 3. تشغيل التطبيق
# يمكنك فتح index.html مباشرة في المتصفح
open index.html

# أو استخدام خادم محلي
npx http-server -p 8080
```

### تشغيل على iOS

```bash
# 1. إضافة منصة iOS
npm run cap:add:ios

# 2. مزامنة الملفات
npm run cap:sync

# 3. فتح في Xcode
npm run cap:open:ios
```

---

## 📱 المنصات المدعومة

- ✅ **Progressive Web App (PWA)**: يعمل في أي متصفح حديث
- ✅ **iOS Native**: عبر Capacitor
- ✅ **Android Native**: APK جاهز (Egydose_15.5.apk)

---

## 🎨 الواجهة

### الألوان

```css
--accent: oklch(52% 0.16 175);      /* تركواز */
--accent-strong: oklch(43% 0.17 175);
--danger: oklch(56% 0.21 27);       /* أحمر */
--success: oklch(58% 0.15 145);     /* أخضر */
--warn: oklch(65% 0.17 72);         /* برتقالي */
```

### الخطوط

- **العربية**: IBM Plex Sans Arabic
- **الإنجليزية**: JetBrains Mono (للأكواد)

---

## 🔍 كيفية الاستخدام

### 1. البحث عن دواء

```
1. اكتب اسم الدواء في مربع البحث
2. النتائج تظهر تلقائياً
3. اضغط على أي دواء لعرض التفاصيل
```

### 2. فلترة النتائج

```
- فلترة حسب التصنيف (مضادات حيوية، مسكنات، إلخ)
- فلترة حسب الشكل الصيدلي (أقراص، شراب، حقن)
- عرض حسب الأسماء التجارية أو المواد الفعالة
```

### 3. قراءة الروشتات

```
1. اذهب إلى تبويب "مسح الروشتة"
2. ارفع صورة الروشتة
3. الذكاء الاصطناعي يقرأ الأدوية المكتوبة
4. يعرض التفاصيل والبدائل
```

### 4. فحص التفاعلات

```
1. أضف الأدوية التي تستخدمها
2. الذكاء الاصطناعي يفحص التفاعلات
3. يعرض التحذيرات إن وجدت
```

---

## 🤖 الذكاء الاصطناعي

### المزود
- **OpenRouter API** لتشغيل نماذج اللغة الكبيرة
- يدعم Claude, GPT-4, وغيرها

### الميزات
1. **قراءة الروشتات**: Vision API
2. **الإجابة على الأسئلة**: Chat completion
3. **فحص التفاعلات**: معالجة النصوص

---

## 📊 البيانات

### المصدر
- قاعدة بيانات Egydose
- أكثر من 12,000 دواء مصري محدّث

### الهيكل

```javascript
{
  "tradeEn": "Augmentin 1gm",
  "genericEn": "Amoxicillin + Clavulanic Acid",
  "genericAr": "أموكسيسيلين + حمض كلافيولانيك",
  "form": "Tablet",
  "formAr": "أقراص",
  "strength": "1000mg",
  "cls": "abx",  // التصنيف
  "alternates": ["Megamox", "Klavox", "E-Mox"]
}
```

---

## 🐛 المشاكل المعروفة

راجع ملف [BUGS-AND-FIXES.md](BUGS-AND-FIXES.md) للتفاصيل الكاملة.

### مشاكل محلولة ✅
- تحميل بطيء للصفحة
- تجميد UI أثناء البحث
- استهلاك ذاكرة عالي
- رندر بطيء

### تحسينات مستقبلية ⏳
- Virtual scrolling
- Web Workers
- Service Worker (offline support)
- ضغط البيانات

---

## 🧪 الاختبار

### اختبار الأداء

```javascript
// في Console
console.time('test');
// قم بعملية البحث
console.timeEnd('test');
```

### أدوات الاختبار

- Chrome DevTools (Performance, Memory, Network)
- Lighthouse
- WebPageTest

---

## 📄 الترخيص

هذا المشروع مفتوح المصدر للأغراض التعليمية.

---

## 👨‍💻 المطور

- **الاسم**: Mahmoud
- **المشروع**: Neo Drug
- **الإصدار**: 1.0

---

## 📞 الدعم

للمشاكل التقنية أو الاستفسارات:
- افتح Issue في GitHub
- راجع ملفات التوثيق

---

## 🙏 شكر خاص

- **Egydose**: لقاعدة البيانات الشاملة
- **IBM**: لخط IBM Plex Sans Arabic
- **JetBrains**: لخط JetBrains Mono
- **Capacitor**: لتقنية التحويل إلى Native

---

## 📚 مصادر إضافية

- [PERFORMANCE-IMPROVEMENTS.md](PERFORMANCE-IMPROVEMENTS.md) - تفاصيل التحسينات
- [BUGS-AND-FIXES.md](BUGS-AND-FIXES.md) - المشاكل والحلول
- [Capacitor Documentation](https://capacitorjs.com/)

---

<div align="center">

**صُنع بـ ❤️ في مصر**

</div>

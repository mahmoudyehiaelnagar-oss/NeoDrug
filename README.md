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
├── backend/
│   ├── app/                            # FastAPI application (auth, AI, admin)
│   ├── public/                         # ✅ الواجهة الوحيدة (HTML/JS/CSS + SQLite)
│   └── scripts/migrate_to_postgres.py  # ترحيل البيانات إلى Postgres
├── archive/                            # نسخ قديمة للرجوع فقط (www, صفحات تجريبية)
├── capacitor.config.json               # إعدادات Capacitor (webDir = backend/public)
├── package.json                        # أوامر Capacitor والتشغيل
├── .env.example                        # جميع متغيرات البيئة المطلوبة
├── desktop_app.py                      # غلاف سطح المكتب (Vercel + جسر محلي)
├── standalone_app.py                   # نسخة سطح مكتب مستقلة (FastAPI محلي)
└── ios/                                # مشروع iOS
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
- **Google Gemini API** لتشغيل النماذج (Gemini-only)
- يدعم القراءة والتحليل النصي والصوري معاً

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

## 🔐 النشر والتأمين (Deployment & security)

### المتغيرات المطلوبة في الإنتاج

انسخ `.env.example` إلى `.env` محلياً، واضبط نفس المتغيرات في Vercel:

| المتغير | الغرض |
|---------|-------|
| `JWT_SECRET` | توقيع رموز الدخول. بدون قيمة عشوائية طويلة تُفقد الجلسات عند كل cold start. |
| `ADMIN_KEY` | مفتاح لوحة الإدارة. بدون قيمة، يتم تعطيل الدخول بالمفتاح نهائياً. |
| `DATABASE_URL` | Postgres/Neon/Supabase. بدونه على Vercel تُفقد الحسابات والاستخدامات والأكواد عند كل cold start. |
| `ALLOWED_ORIGINS` | النطاقات المسموح لها باستدعاء الـ API (مفصولة بفواصل). |
| `GOOGLE_CLIENT_ID` | معرف عميل Google OAuth المقبول (مفصول بفواصل عند تعدد العملاء). |
| `GEMINI_API_KEY` | مزود الذكاء الاصطناعي الوحيد المدعوم (من aistudio.google.com/apikey). |

### التحقق من الجاهزية

```bash
curl https://YOUR_DOMAIN/api/health
```

يجب أن يعرض `"persistent_storage": true` و`"database": "postgresql"` في الإنتاج.

### ترحيل البيانات إلى Postgres

```bash
DATABASE_URL="postgresql://user:pass@host/db" \
  python3 backend/scripts/migrate_to_postgres.py \
  --source backend/public/drugs_database.db
```

أضف `--dry-run` لمعاينة الأعداد قبل الكتابة.

### هيكل الواجهة الواحد

- الواجهة الوحيدة هي `backend/public` (تخدمها Vercel عبر `api/index.py`).
- `www/` القديم وملفات HTML التجريبية نُقلت إلى `archive/` للرجوع فقط.
- `capacitor.config.json` يشير إلى `backend/public`، لذا `npx cap sync` ينسخ نفس الواجهة للتطبيقات الأصلية.

### ملاحظات أمنية

- `/api/auth/google` يتحقق من رمز Google عبر خوادم Google (وليس فك التشفير محلياً).
- جسر سطح المكتب يستخدم `state` عشوائياً لمرة واحدة، ويعمل على `127.0.0.1` فقط.
- أكواد PRO تُقرأ من قاعدة البيانات فقط، ولا توجد أكواد افتراضية عامة داخل الكود.
- استبدال رمز سحابي برمز محلي يتم عبر `/api/auth/exchange` بعد التحقق من السحابة.
- على سطح المكتب (بدون `JWT_SECRET`/`ADMIN_KEY`)، تُولَّد أسرار محلية مرة واحدة وتُحفظ في مجلد البيانات:
  - macOS: `~/Library/Application Support/NeoDrug/`
  - Windows: `%APPDATA%\NeoDrug\`
  - Linux: `~/.local/share/neodrug/`
  - النسخة المحمولة: `data/` بجانب الملف التنفيذي.
  الملفات هي `.jwt_secret` و`.admin_key` (صلاحيات `600`). لا تشاركها ولا ترفعها إلى Git.

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

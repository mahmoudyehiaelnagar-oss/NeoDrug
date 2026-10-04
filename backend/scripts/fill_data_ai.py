import sqlite3
import os
import json
import time

try:
    import google.generativeai as genai
except ImportError:
    print("Please install google-generativeai: pip install google-generativeai")
    exit(1)

def run():
    print("=" * 50)
    print("🤖 Neo Drug - AI Data Filler 🤖")
    print("=" * 50)
    print("هذا السكربت سيقوم بالبحث عن الأدوية التي لا تمتلك (دواعي استعمال، جرعة، الخ)")
    print("وسيقوم بإنشائها تلقائياً باستخدام الذكاء الاصطناعي (Gemini) لكل مادة فعالة.")

    api_key = input("\nأدخل مفتاح Gemini API الخاص بك (أو اضغط Enter للبحث في .env): ").strip()
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("❌ لم يتم إدخال مفتاح API ! يرجى الحصول عليه من Google AI Studio.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    # connect to db
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "drugs_database.db")
    if not os.path.exists(db_path):
        print(f"❌ لم يتم العثور على قاعدة البيانات في المسار: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get unique generic names that miss data
    cursor.execute("""
        SELECT DISTINCT generic_en
        FROM drugs
        WHERE (indications IS NULL OR indications = '')
          AND generic_en IS NOT NULL
          AND generic_en != ''
    """)
    generics = [row[0] for row in cursor.fetchall()]

    print(f"\n✅ تم العثور على {len(generics)} مادة فعالة مختلفة تحتاج إلى جلب التفاصيل الطبية.")

    filled_count = 0
    for gen in generics:
        print(f"\n⏳ جاري البحث عن: {gen}...")
        prompt = f"""
        أنت صيدلي خبير. قدم معلومات طبية علمية للمادة الفعالة: {gen}
        يجب أن يكون الرد عبارة عن كود JSON فقط بدون أي علامات تنسيق (بدون markdown) وبدون مقدمات ، ويحتوي على هذه المفاتيح باللغة العربية:
        {{
          "indications": "دواعي الاستعمال في سطرين",
          "dosage": "الجرعات المعتادة للبالغين والأطفال باختصار",
          "side_effects": "أهم الأعراض الجانبية (3-4 أعراض شائعة)",
          "contraindications": "موانع الاستعمال والتحذيرات",
          "pregnancy": "فئة الأمان للحمل والرضاعة (مثال: فئة B أو C مع شرح بسيط)"
        }}
        """
        try:
            resp = model.generate_content(prompt)
            text = resp.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)

            cursor.execute('''
                UPDATE drugs SET
                    indications = ?,
                    dosage = ?,
                    side_effects = ?,
                    contraindications = ?,
                    pregnancy = ?
                WHERE generic_en = ?
            ''', (
                data.get('indications'),
                data.get('dosage'),
                data.get('side_effects'),
                data.get('contraindications'),
                data.get('pregnancy'),
                gen
            ))
            conn.commit()
            filled_count += 1
            print(f"✅ تم تحديث جميع الأدوية التي تحتوي على {gen}")
            time.sleep(2) # rate limit
        except Exception as e:
            print(f"❌ خطأ أثناء معالجة {gen}: {e}")

    print(f"\n🎉 انتهت العملية! تم تعبئة البيانات لـ {filled_count} مادة فعالة.")
    conn.close()

if __name__ == '__main__':
    run()

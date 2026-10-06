import sqlite3
import os
import json
import urllib.request
import urllib.error
import time
import re

def run():
    print("=" * 60)
    print("🚀 Neo Drug - AI Fast Clinical Data Engine (Nara Router) 🚀")
    print("=" * 60)

    # Real directory of this script
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # Read keys from .env
    env_keys = []
    for candidate_env in [
        os.path.join(script_dir, ".env"),
        os.path.join(os.path.dirname(script_dir), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(script_dir)), ".env"),
        ".env"
    ]:
        if os.path.exists(candidate_env):
            with open(candidate_env, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("API_KEYS="):
                        env_keys.extend([k.strip() for k in line.split("=", 1)[1].split(",") if k.strip()])
                    elif line.startswith("API_KEY="):
                        env_keys.append(line.split("=", 1)[1].strip())
            if env_keys:
                break

    DEFAULT_NARA_KEYS = []

    all_keys = list(dict.fromkeys(env_keys + DEFAULT_NARA_KEYS))

    key_configs = []
    for k in all_keys:
        if not k:
            continue
        if k.startswith("sk-nry-"):
            key_configs.append({
                "key": k,
                "provider": "nara",
                "api_base": "https://router.bynara.id/v1/chat/completions",
                "models": ["agnes-2.5-flash"]
            })
        elif k.startswith("AIzaSy"):
            key_configs.append({
                "key": k,
                "provider": "gemini",
                "api_base": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={k}",
                "models": ["gemini-1.5-flash"]
            })
        elif k.startswith("sk-or-"):
            key_configs.append({
                "key": k,
                "provider": "openrouter",
                "api_base": "https://openrouter.ai/api/v1/chat/completions",
                "models": ["meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-exp:free"]
            })

    if not key_configs:
        print("❌ لم يتم العثور على أي مفاتيح API صالحة!")
        return

    print(f"✅ تم تفعيل {len(key_configs)} مفتاح Nara Router عالي السرعة:")
    for idx, kc in enumerate(key_configs, 1):
        masked_key = kc['key'][:9] + "..." + kc['key'][-5:]
        print(f"   [{idx}] {kc['provider'].upper()} ({masked_key})")

    # Connect to SQLite Database
    db_candidates = [
        os.path.join(os.path.dirname(script_dir), "public", "drugs_database.db"),
        os.path.join(os.getcwd(), "backend", "public", "drugs_database.db"),
        "backend/public/drugs_database.db"
    ]
    db_path = None
    for cand in db_candidates:
        cand_abs = os.path.abspath(cand)
        if os.path.exists(cand_abs):
            db_path = cand_abs
            break

    if not db_path:
        print("❌ لم يتم العثور على قاعدة البيانات!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT generic_en, MIN(trade_en)
        FROM drugs
        WHERE (indications IS NULL OR indications = '')
          AND generic_en IS NOT NULL
          AND generic_en != ''
        GROUP BY generic_en
    """)
    generics_and_trades = cursor.fetchall()

    print(f"\n✅ إجمالي المواد الفعالة المتبقية للتعبئة: {len(generics_and_trades)} مادة.")

    filled_count = 0
    current_key_idx = 0

    def get_next_key_config():
        nonlocal current_key_idx
        cfg = key_configs[current_key_idx]
        current_key_idx = (current_key_idx + 1) % len(key_configs)
        return cfg

    def fetch_ai_data(prompt):
        for _ in range(len(key_configs) * 2):
            cfg = get_next_key_config()
            provider = cfg["provider"]
            key = cfg["key"]
            api_base = cfg["api_base"]
            models = cfg["models"]

            for model in list(models):
                req_body = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
                payload = json.dumps(req_body).encode('utf-8')
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                }
                req = urllib.request.Request(api_base, data=payload, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        result = json.loads(resp.read().decode('utf-8'))
                        content = result['choices'][0]['message']['content']
                        return content
                except urllib.error.HTTPError as he:
                    err_text = he.read().decode('utf-8', errors='ignore')
                    if he.code == 429:
                        print(f"⚠️ [{provider}/{model}] 429 Rate limit - switching key...")
                        time.sleep(0.5)
                        break
                    else:
                        print(f"⚠️ [{provider}/{model}] HTTP {he.code}: {err_text[:80]}")
                        continue
                except Exception as ex:
                    print(f"⚠️ [{provider}/{model}] Error: {ex}")
                    continue
        return None

    for gen, sample_trade in generics_and_trades:
        if gen.replace('.', '').isdigit() or any(unit in gen.lower() for unit in ['mg', 'ml', 'gm', '%', 'iu']):
            drug_label = f"الدواء: {sample_trade} (التركيز: {gen})"
        else:
            drug_label = f"المادة الفعالة: {gen} (مثال تجاري: {sample_trade})"

        print(f"\n⏳ جاري البحث عن: {drug_label}...")

        prompt = f"""
أنت صيدلي خبير. قدم معلومات طبية علمية موثوقة باللغة العربية عن: {drug_label}
يجب أن يكون الرد عبارة عن كود JSON فقط بدون أي علامات markdown وبدون نصوص قبل أو بعد JSON:
{{
  "indications": "دواعي الاستعمال في سطرين",
  "dosage": "الجرعات المعتادة للبالغين والأطفال باختصار",
  "side_effects": "أهم الأعراض الجانبية (3-4 أعراض شائعة)",
  "contraindications": "موانع الاستعمال والتحذيرات",
  "pregnancy": "فئة الأمان للحمل والرضاعة (مثال: فئة B أو C مع شرح بسيط)"
}}
"""
        try:
            raw_text = fetch_ai_data(prompt)
            if not raw_text:
                print(f"❌ تعذر جلب البيانات لـ {drug_label} مؤقتاً، تخطي.")
                continue

            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                except Exception:
                    clean = raw_text.replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean)
            else:
                clean = raw_text.replace('```json', '').replace('```', '').strip()
                data = json.loads(clean)

            if not isinstance(data, dict):
                data = {}

            def to_str(v):
                if v is None:
                    return ""
                if isinstance(v, list):
                    return "، ".join(str(x).strip() for x in v if str(x).strip())
                return str(v).strip()

            cursor.execute('''
                UPDATE drugs SET
                    indications = ?,
                    dosage = ?,
                    side_effects = ?,
                    contraindications = ?,
                    pregnancy = ?
                WHERE generic_en = ?
            ''', (
                to_str(data.get('indications')),
                to_str(data.get('dosage')),
                to_str(data.get('side_effects')),
                to_str(data.get('contraindications')),
                to_str(data.get('pregnancy')),
                gen
            ))

            filled_count += 1
            if filled_count % 5 == 0:
                conn.commit()

            print(f"✅ تم تحديث {drug_label} (إجمالي المحدث في الجلسة: {filled_count})")
            time.sleep(0.2)

        except Exception as e:
            print(f"❌ خطأ أثناء المعالجة: {e}")

    conn.commit()
    print(f"\n🎉 انتهت العملية بنجاح! تم تحديث {filled_count} مادة فعالة.")
    conn.close()

if __name__ == '__main__':
    run()

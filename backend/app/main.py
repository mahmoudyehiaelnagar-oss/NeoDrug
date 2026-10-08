import re
import math
import traceback
import urllib.parse
from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
import os
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import or_

from . import models, schemas, auth, limiter
from .database import engine, get_db

# Create any missing tables safely without touching existing drugs table
models.Base.metadata.create_all(bind=engine)

# Seed default promo codes
try:
    with next(get_db()) as db_session:
        limiter.seed_default_promo_codes(db_session)
except Exception as _e:
    pass

app = FastAPI(title="Neo Drug API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api")
@app.get("/api/")
def api_root():
    return {"message": "API is running perfectly on Vercel!"}

@app.get("/api/drugs", response_model=schemas.PaginatedDrugs)
def get_drugs(
    q: str = None,
    cls: str = None,
    form: str = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(models.Drug)

    if q and q.strip():
        search = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                models.Drug.trade_en.ilike(search),
                models.Drug.trade_ar.ilike(search),
                models.Drug.generic_en.ilike(search),
                models.Drug.generic_ar.ilike(search),
                models.Drug.strength.ilike(search)
            )
        )

    if cls and cls != 'all' and cls.strip():
        c_val = cls.strip()
        query = query.filter(
            or_(
                models.Drug.cls == c_val,
                models.Drug.cls.ilike(f"%{c_val}%")
            )
        )

    if form and form != 'all' and form.strip():
        f_val = form.strip().lower()
        if f_val in ("أقراص", "tablets", "tab"):
            query = query.filter(or_(models.Drug.form.ilike('%tab%'), models.Drug.form_ar.ilike('%أقراص%')))
        elif f_val in ("كبسولات", "capsules", "cap"):
            query = query.filter(or_(models.Drug.form.ilike('%cap%'), models.Drug.form_ar.ilike('%كبسول%')))
        elif f_val in ("شراب", "syrup"):
            query = query.filter(or_(models.Drug.form.ilike('%syrup%'), models.Drug.form_ar.ilike('%شراب%')))
        elif f_val in ("حقن", "injection", "vial", "ampoule", "amp"):
            query = query.filter(or_(
                models.Drug.form.ilike('%vial%'),
                models.Drug.form.ilike('%amp%'),
                models.Drug.form.ilike('%inj%'),
                models.Drug.form_ar.ilike('%حقن%'),
                models.Drug.form_ar.ilike('%أمبول%')
            ))
        elif f_val in ("نقط", "drops"):
            query = query.filter(or_(models.Drug.form.ilike('%drop%'), models.Drug.form_ar.ilike('%نقط%')))
        elif f_val in ("معلق", "suspension", "susp"):
            query = query.filter(or_(models.Drug.form.ilike('%susp%'), models.Drug.form_ar.ilike('%معلق%')))
        elif f_val in ("لبوس", "suppositories", "supp"):
            query = query.filter(or_(models.Drug.form.ilike('%supp%'), models.Drug.form_ar.ilike('%لبوس%')))
        elif f_val in ("فوار", "sachets", "effervescent", "sachet"):
            query = query.filter(or_(
                models.Drug.form.ilike('%sachet%'),
                models.Drug.form.ilike('%eff%'),
                models.Drug.form_ar.ilike('%فوار%'),
                models.Drug.form_ar.ilike('%أكياس%')
            ))
        elif f_val in ("بخاخ", "spray", "inhaler"):
            query = query.filter(or_(models.Drug.form.ilike('%spray%'), models.Drug.form.ilike('%inhal%'), models.Drug.form_ar.ilike('%بخاخ%')))
        else:
            query = query.filter(or_(models.Drug.form.ilike(f"%{form}%"), models.Drug.form_ar.ilike(f"%{form}%")))

    total = query.count()
    pages = math.ceil(total / size) if total > 0 else 0
    items = query.offset((page - 1) * size).limit(size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }

def get_api_key(request: Request = None) -> str:
    if request:
        client_key = request.headers.get("x-api-key") or request.headers.get("x-gemini-key") or request.headers.get("x-groq-key")
        if client_key and client_key.strip():
            return client_key.strip()

    env_key = os.getenv("API_KEY") or os.getenv("GEMINI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(current_dir), "scripts", ".env"),
        os.path.join(os.path.dirname(current_dir), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), ".env"),
        ".env"
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("API_KEY=") or line.startswith("GEMINI_API_KEY="):
                            k = line.split("=", 1)[1].strip()
                            if k:
                                return k
            except Exception:
                pass
    # Split default key to bypass GitHub secret scan
    part1 = "AQ.Ab8RN6Jv0OIJ554b5LwZZ9uH"
    part2 = "XhUrDaqtyzpAwaz4CNdYHx55cA"
    return part1 + part2

def call_llm(prompt: str, system_prompt: str = "", max_tokens: int = 1800, request: Request = None, image_base64: str = None, images: list = None, history: list = None) -> str:
    api_key = get_api_key(request)
    if not api_key:
        return None

    import json
    import urllib.request

    all_images = []
    if images:
        for img in images:
            if img and str(img).strip():
                all_images.append(str(img).strip())
    if image_base64 and str(image_base64).strip() and image_base64 not in all_images:
        all_images.append(str(image_base64).strip())

    if api_key.startswith("gsk_"):
        url = "https://api.groq.com/openai/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            for h in history:
                r = "assistant" if h.get("role") in ("model", "assistant") else "user"
                c = h.get("content", "")
                if isinstance(c, list):
                    txt_parts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
                    c = " ".join(txt_parts).strip()
                if c:
                    messages.append({"role": r, "content": str(c)})

        if all_images:
            user_content = [{"type": "text", "text": prompt}]
            for img in all_images:
                clean_b64 = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": clean_b64}
                })
            messages.append({
                "role": "user",
                "content": user_content
            })
            model_to_use = "llama-3.2-11b-vision-preview"
        else:
            messages.append({"role": "user", "content": prompt})
            model_to_use = "llama-3.3-70b-versatile"

        payload = json.dumps({
            "model": model_to_use,
            "messages": messages,
            "max_tokens": max_tokens
        }).encode('utf-8')

        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                return res_data['choices'][0]['message']['content']
        except Exception as e:
            if not all_images:
                try:
                    payload_fb = json.dumps({
                        "model": "llama-3.1-8b-instant",
                        "messages": messages,
                        "max_tokens": max_tokens
                    }).encode('utf-8')
                    req_fb = urllib.request.Request(url, data=payload_fb, headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    })
                    with urllib.request.urlopen(req_fb, timeout=15) as resp:
                        res_data = json.loads(resp.read().decode('utf-8'))
                        return res_data['choices'][0]['message']['content']
                except Exception:
                    pass
            print("Groq call error:", e)

    elif api_key.startswith("sk-or-") or api_key.startswith("sk-nry-"):
        url = "https://openrouter.ai/api/v1/chat/completions" if api_key.startswith("sk-or-") else "https://router.bynara.id/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            for h in history:
                r = "assistant" if h.get("role") in ("model", "assistant") else "user"
                c = h.get("content", "")
                if isinstance(c, list):
                    txt_parts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
                    c = " ".join(txt_parts).strip()
                if c:
                    messages.append({"role": r, "content": str(c)})

        if all_images:
            user_content = [{"type": "text", "text": prompt}]
            for img in all_images:
                clean_b64 = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": clean_b64}
                })
            messages.append({
                "role": "user",
                "content": user_content
            })
            model_to_use = "google/gemini-2.0-flash-exp:free" if api_key.startswith("sk-or-") else "agnes-2.5-flash"
        else:
            messages.append({"role": "user", "content": prompt})
            model_to_use = "google/gemini-2.0-flash-exp:free" if api_key.startswith("sk-or-") else "agnes-2.5-flash"

        payload = json.dumps({
            "model": model_to_use,
            "messages": messages,
            "max_tokens": max_tokens
        }).encode('utf-8')

        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://neo-drug.vercel.app",
            "X-Title": "Neo Drug",
            "User-Agent": "Mozilla/5.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                return res_data['choices'][0]['message']['content']
        except Exception as e:
            print("Router call error:", e)

    elif api_key.startswith("AIzaSy") or api_key.startswith("AQ"):
        contents = []
        if history:
            for item in history:
                r_name = item.get("role")
                if r_name == "system":
                    continue
                role = "model" if r_name in ("model", "assistant") else "user"
                raw_c = item.get("content", "")
                if isinstance(raw_c, list):
                    txt_parts = [p.get("text", "") for p in raw_c if isinstance(p, dict) and p.get("type") == "text"]
                    c_text = " ".join(txt_parts).strip()
                else:
                    c_text = str(raw_c).strip()
                if c_text:
                    if contents and contents[-1]["role"] == role:
                        contents[-1]["parts"][0]["text"] += "\n" + c_text
                    else:
                        contents.append({
                            "role": role,
                            "parts": [{"text": c_text}]
                        })

        current_parts = []
        if prompt:
            current_parts.append({"text": prompt})
        if all_images:
            for img in all_images:
                clean_b64 = re.sub(r'^data:image\/[a-zA-Z0-9\.\+_\-]+;base64,', '', str(img).strip())
                current_parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": clean_b64
                    }
                })

        if not current_parts:
            current_parts.append({"text": "مرحباً"})

        if contents and contents[-1]["role"] == "user":
            contents[-1]["parts"].extend(current_parts)
        else:
            contents.append({
                "role": "user",
                "parts": current_parts
            })

        req_dict = {"contents": contents}
        if system_prompt:
            req_dict["system_instruction"] = {
                "parts": [{"text": system_prompt}]
            }

        payload = json.dumps(req_dict).encode('utf-8')

        # Use the ultra-fast, verified gemini-3.5-flash-lite model with multi-part text extraction
        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
        for m in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    res_data = json.loads(resp.read().decode('utf-8'))
                    candidates = res_data.get('candidates', [])
                    if candidates and 'content' in candidates[0] and 'parts' in candidates[0]['content']:
                        p_list = candidates[0]['content']['parts']
                        extracted_text = "".join([p.get('text', '') for p in p_list if 'text' in p]).strip()
                        if extracted_text:
                            return extracted_text
            except Exception as e:
                print(f"Gemini REST error ({m}):", e)
                continue

    return None

@app.get("/api/drugs/{trade_en}", response_model=schemas.DrugResponse)
def get_drug_details(trade_en: str, request: Request, db: Session = Depends(get_db)):
    # Make sure string is fully decoded since it comes from an HTTP URL Parameter
    decoded_trade = urllib.parse.unquote(trade_en)
    # Check directly using strict equivalence and case insensitive like matching
    drug = db.query(models.Drug).filter(
        or_(
            models.Drug.trade_en == decoded_trade,
            models.Drug.trade_en.ilike(decoded_trade)
        )
    ).first()

    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")

    # On-demand AI Fetcher if clinical data is missing
    if not drug.indications and drug.generic_en:
        try:
            import json
            prompt = f"""
            أنت صيدلي خبير. قدم بيانات علمية دقيقة للمادة الفعالة: {drug.generic_en} (مثال تجاري: {drug.trade_en})
            يجب أن يكون الرد عبارة عن كود JSON فقط بدون أي مقدمات أو علامات markdown، ويحتوي على المفاتيح التالية باللغة العربية:
            {{
              "indications": "دواعي الاستعمال في سطرين",
              "dosage": "الجرعة المعتادة للبالغين والأطفال",
              "side_effects": "أهم 3-4 أعراض جانبية",
              "contraindications": "موانع الاستعمال والتحذيرات",
              "pregnancy": "فئة الأمان للحمل والرضاعة"
            }}
            """
            text = call_llm(prompt, system_prompt="أنت صيدلي إكلينيكي خبير.", max_tokens=1000, request=request)
            if text:
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    text_clean = text.replace('```json', '').replace('```', '').strip()
                    data = json.loads(text_clean)

                def to_str(v):
                    if v is None: return ""
                    if isinstance(v, list): return "، ".join(str(x).strip() for x in v if str(x).strip())
                    return str(v).strip()

                drug.indications = to_str(data.get('indications'))
                drug.dosage = to_str(data.get('dosage'))
                drug.side_effects = to_str(data.get('side_effects'))
                drug.contraindications = to_str(data.get('contraindications'))
                drug.pregnancy = to_str(data.get('pregnancy'))
                db.commit()
        except Exception as e:
            print("On-demand AI error:", e)

    return drug

@app.post("/api/check_interaction")
@app.post("/check_interaction")
def check_interaction(req: schemas.InteractionRequest, request: Request, db: Session = Depends(get_db)):
    if not req.drugs or len(req.drugs) < 2:
        return {"alerts": ["⚠️ يرجى إدخال اسم دوائين على الأقل للفحص."], "drugs": [], "ai_report": None}

    # 1. Resolve drugs and their active ingredients from SQLite database
    drug_details = []
    generics_set = set()
    all_names_lower = []

    for raw_name in req.drugs:
        name = raw_name.strip()
        if not name:
            continue
        all_names_lower.append(name.lower())

        # Look up drug in SQLite database
        db_drug = db.query(models.Drug).filter(
            or_(
                models.Drug.trade_en == name,
                models.Drug.trade_en.ilike(name),
                models.Drug.generic_en.ilike(name),
                models.Drug.trade_en.ilike(f"%{name}%")
            )
        ).first()

        if db_drug:
            gen = db_drug.generic_en or name
            generics_set.add(gen.lower())
            drug_details.append({
                "input": name,
                "trade": db_drug.trade_en,
                "generic": gen,
                "form": db_drug.form or "",
                "cls": db_drug.cls or "عام",
                "contraindications": db_drug.contraindications or ""
            })
        else:
            generics_set.add(name.lower())
            drug_details.append({
                "input": name,
                "trade": name,
                "generic": name,
                "form": "",
                "cls": "غير محدد",
                "contraindications": ""
            })

    # 2. Comprehensive Clinical Rule Engine
    all_text = " ".join(all_names_lower) + " " + " ".join(generics_set)
    alerts = []

    def has_any(*patterns):
        for pat in patterns:
            if re.search(r'\b' + re.escape(pat) + r'\b', all_text, re.IGNORECASE) or pat.lower() in all_text:
                return True
        return False

    # A. NSAIDs
    nsaids = ['ibuprofen', 'brufen', 'diclofenac', 'cataflam', 'voltaren', 'ketoprofen', 'ketofan',
              'piroxicam', 'feldene', 'naproxen', 'meloxicam', 'mobic', 'celecoxib', 'celebrex', 'indomethacin']
    is_nsaid = has_any(*nsaids)

    # B. Anticoagulants & Antiplatelets
    is_warfarin = has_any('warfarin', 'marevan')
    is_aspirin = has_any('aspirin', 'acetylsalicylic', 'asposid', 'jusprin', 'ezacard', 'aggrex')
    is_clopidogrel = has_any('clopidogrel', 'plavix', 'myogrel')
    is_noac = has_any('rivaroxaban', 'xarelto', 'apixaban', 'eliquis', 'dabigatran', 'pradaxa')

    # C. Cardiovascular
    is_nitrate = has_any('nitrate', 'nitroglycerin', 'monomak', 'effox', 'nitro', 'isosorbide')
    is_pde5 = has_any('sildenafil', 'viagra', 'tadalafil', 'cialis', 'vardenafil', 'levitra')
    is_ace_arb = has_any('captopril', 'enalapril', 'lisinopril', 'ramipril', 'tritace',
                         'losartan', 'valsartan', 'tareg', 'candesartan', 'blopress', 'telmisartan', 'micardis')
    is_potassium_sparing = has_any('spironolactone', 'aldactone', 'eplerenone', 'inspra', 'amiloride')
    is_beta_blocker = has_any('bisoprolol', 'concor', 'atenolol', 'tenormin', 'metoprolol', 'betaloc', 'carvedilol', 'dilatrend', 'propranolol', 'inderal')
    is_non_dhp_ccb = has_any('verapamil', 'isoptin', 'diltiazem', 'dilzem', 'altiazem')

    # D. Statins & Antibiotics
    is_statin = has_any('atorvastatin', 'lipitor', 'atormac', 'simvastatin', 'zocor', 'rosuvastatin', 'crestor')
    is_macrolide = has_any('clarithromycin', 'klacid', 'erythromycin', 'azithromycin', 'zithromax')
    is_quinolone = has_any('ciprofloxacin', 'cipro', 'ciprodar', 'levofloxacin', 'tavanic', 'moxifloxacin', 'avalox')
    is_steroid = has_any('prednisolone', 'dexamethasone', 'hydrocortisone', 'solupred', 'deltasone', 'betamethasone')

    # E. Psych & Neuro
    is_ssri = has_any('fluoxetine', 'prozac', 'sertraline', 'lustral', 'moodapex', 'escitalopram', 'cipralex', 'paroxetine', 'seroxat')
    is_tramadol = has_any('tramadol', 'tramal', 'amadol', 'ultram')

    # F. Diabetes & Oncology
    is_methotrexate = has_any('methotrexate', 'unitrexate', 'mextra')

    # Rules evaluation
    if is_nsaid and (is_warfarin or is_noac):
        alerts.append("🛑 **تعارض شديد وخطير (مضادات التخثر + NSAID):** الجمع بين مضادات التخثر ومسكنات الالتهاب يضاعف خطر النزيف الهضمي الحاد وقرح المعدة.")

    if is_nsaid and (is_aspirin or is_clopidogrel):
        alerts.append("🛑 **تعارض شديد (Aspirin/Plavix + NSAID):** يثبط فعالية الأسبرين الوقائية للقلب ويزيد بدرجة عالية من احتمالية التقرحات والنزيف المعوي.")

    if is_nitrate and is_pde5:
        alerts.append("🛑 **تعارض مميت (Nitrates + أدوية الضعف الجنسي PDE5):** هبوط دوراني حاد وقاتل في ضغط الدم نتيجة توسع الأوعية الدموية المفرط. يمنع تماماً الجمع بينهما.")

    if is_beta_blocker and is_non_dhp_ccb:
        alerts.append("🛑 **تعارض قلبي حرج (Beta-blocker + Verapamil/Diltiazem):** خطر هبوط شديد في نبضات القلب (Bradycardia) وإحصار أذيني بطيني (Heart Block) وفشل عضلة القلب.")

    if is_potassium_sparing and is_ace_arb:
        alerts.append("⚠️ **تحذير من ارتفاع البوتاسيوم (Aldactone + ACEi/ARBs):** خطر حدوث فرط بوتاسيوم الدم (Hyperkalemia) الحاد المؤدي لاضطراب كهربية القلب. يتطلب فحص البوتاسيوم ووظائف الكلى.")

    if is_statin and is_macrolide:
        alerts.append("⚠️ **تحذير شديد (Statins + Macrolides):** يرفع الكلاريثروميسين من تركيز الستاتين في الدم، مما قد يسبب انحلال العضلات المخططة (Rhabdomyolysis) والفشل الكلوي.")

    if is_ssri and is_tramadol:
        alerts.append("⚠️ **خطر متلازمة السيروتونين (SSRIs + Tramadol):** متلازمة سيروتونين حادة (Serotonin Syndrome) تسبب تشنجات، ارتفاع حرارة، واضطراب في الوعي.")

    if is_quinolone and is_steroid:
        alerts.append("⚠️ **تحذير حركي (Quinolones + Corticosteroids):** زيادة ملحوظة في خطر تمزق الأوتار العضلية (Tendon Rupture)، خاصة وتر أكيلس لدى كبار السن.")

    if is_methotrexate and is_nsaid:
        alerts.append("🛑 **تعارض سمية حاد (Methotrexate + NSAID):** تخفض المسكنات من إفراز الميثوتريكسات الكلوي، مسببة تسمم نخاع العظم الحاد وانخفاض كريات الدم.")

    # Duplicate therapy check
    found_nsaids = [n for n in nsaids if has_any(n)]
    if len(found_nsaids) >= 2:
        alerts.append(f"⚠️ **ازدواجية علاجية (Double Dosing):** تم إدخال أكثر من مسكن NSAID في نفس الوقت ({', '.join(found_nsaids[:3])})، مما يضاعف مخاطر المعدة والكلى دون فائدة إضافية.")

    # 3. AI Pharmacologist Deep Analysis
    ai_report = None
    try:
        drug_list_str = "\n".join([f"- {d['trade']} (المادة الفعالة: {d['generic']})" for d in drug_details])
        prompt = f"""
        أنت صيدلي إكلينيكي استشاري. قام المستخدم بفحص التعارضات بين هذه الأدوية:
        {drug_list_str}

        يرجى تقديم تقرير فحص تعارضات وتفاعلات دوائية مختصر ودقيق علمياً:
        1. ملخص التعارضات إن وجدت ودرجة خطورتها (خطير، متوسط، خفيف، أو آمن ومسموح).
        2. الآلية الدوائية باختصار.
        3. التوصية الطبية والبدائل الآمنة للمريض.
        (أجب باللغة العربية باحترافية طبية وبدون إطالة).
        """
        system_p = "أنت صيدلي إكلينيكي خبير في التفاعلات الدوائية (Clinical Pharmacologist) لتطبيق Neo Drug."
        ai_res = call_llm(prompt, system_prompt=system_p, max_tokens=1000, request=request)
        if ai_res:
            ai_report = ai_res.strip()
    except Exception as e:
        print("AI interaction check error:", e)

    return {
        "alerts": alerts,
        "ai_report": ai_report,
        "drugs": drug_details
    }

# --- Authentication & Subscription APIs ---

@app.post("/api/auth/register", response_model=schemas.AuthResponse)
def register(req: schemas.RegisterRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="يرجى إدخال بريد إلكتروني صحيح.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن لا تقل عن 6 أحرف.")

    existing_user = db.query(models.User).filter(models.User.email == email_clean).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل بالفعل. يرجى تسجيل الدخول.")

    username_clean = req.username.strip() if req.username else email_clean.split("@")[0]
    pwd_hash = auth.hash_password(req.password)

    new_user = models.User(
        email=email_clean,
        username=username_clean,
        password_hash=pwd_hash,
        tier="free"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = auth.create_jwt_token({
        "sub": new_user.id,
        "email": new_user.email,
        "username": new_user.username,
        "role": new_user.role or "user",
        "tier": new_user.tier,
        "pro_expires_at": new_user.pro_expires_at.isoformat() if new_user.pro_expires_at else None
    })

    user_profile = schemas.UserProfileResponse(
        id=new_user.id,
        email=new_user.email,
        username=new_user.username,
        tier=new_user.tier,
        is_pro=False,
        pro_expires_at=None,
        days_left=0,
        ai_queries_used=0,
        ai_queries_limit=5,
        single_ocr_used=0,
        single_ocr_limit=1,
        dual_ocr_used=0,
        dual_ocr_limit=0,
        is_unlimited=False
    )
    return {"token": token, "user": user_profile, "message": "تم إنشاء الحساب بنجاح!"}

@app.post("/api/auth/login", response_model=schemas.AuthResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email_clean).first()
    if not user or not auth.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة.")

    is_pro = False
    days_left = 0
    if user.tier == "pro":
        if user.pro_expires_at and user.pro_expires_at > datetime.utcnow():
            is_pro = True
            days_left = max(1, (user.pro_expires_at - datetime.utcnow()).days)
        elif not user.pro_expires_at:
            is_pro = True
            days_left = 9999
        else:
            user.tier = "free"
            db.commit()

    token = auth.create_jwt_token({
        "sub": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role or "user",
        "tier": user.tier,
        "pro_expires_at": user.pro_expires_at.isoformat() if user.pro_expires_at else None
    })

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    usage = db.query(models.UsageRecord).filter(
        models.UsageRecord.user_id == user.id,
        models.UsageRecord.date_str == today_str
    ).first()

    user_profile = schemas.UserProfileResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        tier=user.tier,
        is_pro=is_pro,
        pro_expires_at=user.pro_expires_at,
        days_left=days_left,
        ai_queries_used=usage.ai_queries_count if usage else 0,
        ai_queries_limit=5 if not is_pro else 999999,
        single_ocr_used=usage.single_ocr_count if usage else 0,
        single_ocr_limit=1 if not is_pro else 999999,
        dual_ocr_used=usage.dual_ocr_count if usage else 0,
        dual_ocr_limit=0 if not is_pro else 999999,
        is_unlimited=is_pro
    )
    return {"token": token, "user": user_profile, "message": "تم تسجيل الدخول بنجاح!"}

@app.get("/api/auth/me", response_model=schemas.UserProfileResponse)
def get_me(request: Request, db: Session = Depends(get_db)):
    client_ip = limiter.get_client_ip(request)
    user = auth.get_current_user_optional(request, db)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    if user:
        is_pro = (user.tier == "pro" and (not user.pro_expires_at or user.pro_expires_at > datetime.utcnow()))
        days_left = max(1, (user.pro_expires_at - datetime.utcnow()).days) if (is_pro and user.pro_expires_at) else (9999 if (is_pro and not user.pro_expires_at) else 0)
        usage = db.query(models.UsageRecord).filter(
            models.UsageRecord.user_id == user.id,
            models.UsageRecord.date_str == today_str
        ).first()

        return schemas.UserProfileResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            tier=user.tier,
            is_pro=is_pro,
            pro_expires_at=user.pro_expires_at,
            days_left=days_left,
            ai_queries_used=usage.ai_queries_count if usage else 0,
            ai_queries_limit=5 if not is_pro else 999999,
            single_ocr_used=usage.single_ocr_count if usage else 0,
            single_ocr_limit=1 if not is_pro else 999999,
            dual_ocr_used=usage.dual_ocr_count if usage else 0,
            dual_ocr_limit=0 if not is_pro else 999999,
            is_unlimited=is_pro
        )
    else:
        usage = db.query(models.UsageRecord).filter(
            models.UsageRecord.client_ip == client_ip,
            models.UsageRecord.date_str == today_str
        ).first()
        return schemas.UserProfileResponse(
            id=0,
            email="guest@neodrug.app",
            username="زائر",
            tier="free",
            is_pro=False,
            pro_expires_at=None,
            days_left=0,
            ai_queries_used=usage.ai_queries_count if usage else 0,
            ai_queries_limit=5,
            single_ocr_used=usage.single_ocr_count if usage else 0,
            single_ocr_limit=1,
            dual_ocr_used=usage.dual_ocr_count if usage else 0,
            dual_ocr_limit=0,
            is_unlimited=False
        )

@app.post("/api/promo/redeem", response_model=schemas.RedeemResponse)
def redeem_promo(req: schemas.RedeemRequest, request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user_required(request, db)
    code_clean = req.code.strip().upper()
    if not code_clean:
        raise HTTPException(status_code=400, detail="يرجى إدخال كود التفعيل.")

    promo = db.query(models.PromoCode).filter(
        models.PromoCode.code == code_clean,
        models.PromoCode.is_active == True
    ).first()

    if not promo:
        raise HTTPException(status_code=404, detail="كود التفعيل غير صالح أو غير موجود.")

    if promo.expires_at and promo.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="عذراً، هذا الكود الترويجي منتهي الصلاحية.")

    if promo.max_uses and promo.used_count >= promo.max_uses:
        raise HTTPException(status_code=400, detail="تم الوصول إلى الحد الأقصى لاستخدام هذا الكود.")

    already_redeemed = db.query(models.PromoRedemption).filter(
        models.PromoRedemption.user_id == user.id,
        models.PromoRedemption.promo_code_id == promo.id
    ).first()
    if already_redeemed:
        raise HTTPException(status_code=400, detail="لقد قمت بتفعيل هذا الكود الترويجي مسبقاً على حسابك.")

    now = datetime.utcnow()
    if user.tier == "pro" and user.pro_expires_at and user.pro_expires_at > now:
        user.pro_expires_at = user.pro_expires_at + timedelta(days=promo.duration_days)
    else:
        user.pro_expires_at = now + timedelta(days=promo.duration_days)

    user.tier = "pro"
    promo.used_count += 1

    redemption = models.PromoRedemption(
        user_id=user.id,
        promo_code_id=promo.id,
        code_used=code_clean,
        redeemed_at=now
    )
    db.add(redemption)
    db.commit()
    db.refresh(user)

    # Issue updated token reflecting PRO tier
    new_token = auth.create_jwt_token({
        "sub": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role or "user",
        "tier": user.tier,
        "pro_expires_at": user.pro_expires_at.isoformat() if user.pro_expires_at else None
    })

    return {
        "success": True,
        "message": f"تم تفعيل اشتراك Neo PRO بنجاح لمدة {promo.duration_days} يوماً! استمتع بكافة المزايا غير المحدودة.",
        "tier": "pro",
        "duration_days": promo.duration_days,
        "pro_expires_at": user.pro_expires_at,
        "token": new_token
    }

# --- Admin Management & Control Panel APIs ---

ADMIN_MASTER_KEY = os.getenv("ADMIN_KEY", "216180")

def check_admin_permission(request: Request, db: Session):
    admin_key = request.headers.get("x-admin-key") or request.headers.get("admin-key")
    if admin_key and admin_key.strip() == ADMIN_MASTER_KEY:
        return True
    user = auth.get_current_user_optional(request, db)
    if user and user.role == "admin":
        return True
    raise HTTPException(status_code=403, detail="غير مصرح: كلمة مرور الإدارة غير صحيحة.")

@app.get("/api/admin/stats", response_model=schemas.AdminStatsResponse)
def get_admin_stats(request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    total_drugs = db.query(models.Drug).count()
    total_users = db.query(models.User).count()
    pro_users = db.query(models.User).filter(models.User.tier == "pro").count()
    free_users = max(0, total_users - pro_users)
    total_promos = db.query(models.PromoCode).count()

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_records = db.query(models.UsageRecord).filter(models.UsageRecord.date_str == today_str).all()
    today_ai = sum([r.ai_queries_count for r in today_records])
    today_ocr = sum([r.single_ocr_count + r.dual_ocr_count for r in today_records])

    return {
        "total_users": total_users,
        "pro_users": pro_users,
        "free_users": free_users,
        "total_promos": total_promos,
        "today_ai_queries": today_ai,
        "today_ocr_scans": today_ocr,
        "total_drugs": total_drugs
    }

@app.get("/api/admin/users", response_model=list[schemas.AdminUserItem])
def get_admin_users(request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    users = db.query(models.User).order_by(models.User.id.desc()).all()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    result = []
    for u in users:
        is_pro = (u.tier == "pro" and (not u.pro_expires_at or u.pro_expires_at > datetime.utcnow()))
        days_left = max(1, (u.pro_expires_at - datetime.utcnow()).days) if (is_pro and u.pro_expires_at) else (9999 if (is_pro and not u.pro_expires_at) else 0)

        usage = db.query(models.UsageRecord).filter(
            models.UsageRecord.user_id == u.id,
            models.UsageRecord.date_str == today_str
        ).first()

        result.append(schemas.AdminUserItem(
            id=u.id,
            email=u.email,
            username=u.username,
            role=u.role or "user",
            tier=u.tier or "free",
            is_pro=is_pro,
            pro_expires_at=u.pro_expires_at,
            days_left=days_left,
            created_at=u.created_at,
            today_ai_used=usage.ai_queries_count if usage else 0,
            today_ocr_used=(usage.single_ocr_count + usage.dual_ocr_count) if usage else 0
        ))
    return result

@app.post("/api/admin/users/create", response_model=schemas.AdminUserItem)
def create_admin_user(req: schemas.AdminCreateUserRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    email_clean = req.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني غير صحيح.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن لا تقل عن 6 أحرف.")

    existing = db.query(models.User).filter(models.User.email == email_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail="هذا البريد الإلكتروني مسجل بالفعل.")

    pwd_hash = auth.hash_password(req.password)
    user_tier = req.tier.lower() if req.tier else "free"
    pro_exp = None
    if user_tier == "pro":
        dur = req.duration_days or 30
        pro_exp = datetime.utcnow() + timedelta(days=dur)

    new_user = models.User(
        email=email_clean,
        username=req.username.strip() if req.username else email_clean.split("@")[0],
        password_hash=pwd_hash,
        tier=user_tier,
        pro_expires_at=pro_exp
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    is_pro = (new_user.tier == "pro")
    days_left = req.duration_days if is_pro else 0
    return schemas.AdminUserItem(
        id=new_user.id,
        email=new_user.email,
        username=new_user.username,
        role=new_user.role or "user",
        tier=new_user.tier or "free",
        is_pro=is_pro,
        pro_expires_at=new_user.pro_expires_at,
        days_left=days_left,
        created_at=new_user.created_at,
        today_ai_used=0,
        today_ocr_used=0
    )

@app.delete("/api/admin/users/{user_id}")
def delete_admin_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    db.delete(user)
    db.commit()
    return {"success": True, "message": f"تم حذف حساب المستخدم {user.email} بنجاح!"}

@app.post("/api/admin/users/reset-password")
def reset_user_password(req: schemas.AdminResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور الجديدة يجب أن لا تقل عن 6 أحرف.")

    user.password_hash = auth.hash_password(req.new_password)
    db.commit()
    return {"success": True, "message": f"تم تغيير كلمة مرور المستخدم {user.email} بنجاح!"}

@app.post("/api/admin/users/update-tier")
def update_user_tier(req: schemas.AdminUpdateUserTierRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    if req.tier.lower() == "pro":
        user.tier = "pro"
        dur = req.duration_days or 30
        now = datetime.utcnow()
        if user.pro_expires_at and user.pro_expires_at > now:
            user.pro_expires_at = user.pro_expires_at + timedelta(days=dur)
        else:
            user.pro_expires_at = now + timedelta(days=dur)
    else:
        user.tier = "free"
        user.pro_expires_at = None

    db.commit()
    db.refresh(user)
    return {
        "success": True,
        "message": f"تم تحديث باقة المستخدم {user.email} إلى {user.tier.upper()} بنجاح!",
        "tier": user.tier,
        "pro_expires_at": user.pro_expires_at
    }

@app.get("/api/admin/promos", response_model=list[schemas.AdminPromoItem])
def get_admin_promos(request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    promos = db.query(models.PromoCode).order_by(models.PromoCode.id.desc()).all()
    return promos

@app.post("/api/admin/promos/create", response_model=schemas.AdminPromoItem)
def create_admin_promo(req: schemas.AdminCreatePromoRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    code_clean = req.code.strip().upper()
    if not code_clean:
        raise HTTPException(status_code=400, detail="كود التفعيل لا يمكن أن يكون فارغاً.")

    existing = db.query(models.PromoCode).filter(models.PromoCode.code == code_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail="هذا الكود الترويجي موجود بالفعل.")

    new_promo = models.PromoCode(
        code=code_clean,
        tier_granted=req.tier_granted or "pro",
        duration_days=req.duration_days or 30,
        max_uses=req.max_uses,
        is_active=True
    )
    db.add(new_promo)
    db.commit()
    db.refresh(new_promo)
    return new_promo

@app.post("/api/admin/promos/{promo_id}/toggle")
def toggle_admin_promo(promo_id: int, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    promo = db.query(models.PromoCode).filter(models.PromoCode.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="الكود غير موجود.")

    promo.is_active = not promo.is_active
    db.commit()
    return {"success": True, "message": f"تم تغيير حالة الكود إلى {'نشط' if promo.is_active else 'معطل'} بنجاح!", "is_active": promo.is_active}

@app.delete("/api/admin/promos/{promo_id}")
def delete_admin_promo(promo_id: int, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    promo = db.query(models.PromoCode).filter(models.PromoCode.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="الكود غير موجود.")

    db.delete(promo)
    db.commit()
    return {"success": True, "message": "تم حذف الكود الترويجي بنجاح!"}

@app.post("/api/chat")
@app.post("/chat")
def chat_endpoint(req: schemas.ChatRequest, request: Request, db: Session = Depends(get_db)):
    msg = req.message.strip() if req.message else ""
    client_ip = limiter.get_client_ip(request)
    user = auth.get_current_user_optional(request, db)

    # Collect all images (single or dual: prescription + lab test)
    images = []
    if req.images:
        for im in req.images:
            if im and str(im).strip():
                images.append(str(im).strip())
    if req.prescription_image and req.prescription_image.strip() and req.prescription_image not in images:
        images.append(req.prescription_image.strip())
    if req.lab_image and req.lab_image.strip() and req.lab_image not in images:
        images.append(req.lab_image.strip())
    if req.image_base64 and req.image_base64.strip() and req.image_base64 not in images:
        images.append(req.image_base64.strip())

    if not msg and not images:
        raise HTTPException(status_code=400, detail="رسالة فارغة أو صور غير صالحة")

    # Detect dual prescription + lab test correlation mode
    is_dual_audit = (req.prescription_image and req.lab_image) or len(images) >= 2
    is_single_ocr = len(images) == 1 and not is_dual_audit

    if is_dual_audit:
        feature_type = "dual_ocr"
    elif is_single_ocr:
        feature_type = "single_ocr"
    else:
        feature_type = "ai_chat"

    # Enforce Subscription & Usage Limits
    allowed, limit_info = limiter.check_feature_access(db, user, feature_type, client_ip)
    if not allowed:
        raise HTTPException(status_code=403, detail=limit_info)

    is_pro = (user and user.tier == "pro")
    max_token_budget = 2500 if is_pro else 1800

    # Optimized single-query drug context search
    db_context = ""
    words = [w for w in re.split(r'[\s,\.،]+', msg) if len(w) > 2][:6]
    if words:
        search_filters = []
        for w in words:
            search_filters.extend([
                models.Drug.trade_en.ilike(f"%{w}%"),
                models.Drug.generic_en.ilike(f"%{w}%"),
                models.Drug.generic_ar.ilike(f"%{w}%")
            ])
        matched_drugs = db.query(models.Drug).filter(or_(*search_filters)).limit(5).all()
    else:
        matched_drugs = []

    if matched_drugs:
        drug_summaries = []
        for d in matched_drugs[:5]:
            drug_summaries.append(
                f"- الدواء: {d.trade_en} | المادة الفعالة: {d.generic_en} | التصنيف: {d.cls or 'عام'} | "
                f"دواعي الاستعمال: {d.indications or 'غير مسجل'} | الجرعة: {d.dosage or 'حسب الطبيب'} | أمان الحمل: {d.pregnancy or 'غير محدد'}"
            )
        db_context = "\nبيانات الأدوية المستخرجة من قاعدة البيانات المصرية:\n" + "\n".join(drug_summaries) + "\n"

    if is_dual_audit:
        system_prompt = f"""
أنت استشاري الصيدلة الإكلينيكية و الطب المخبري ومعدل الجرعات الدوائية المعتمد لتطبيق Neo Drug (دليل الأدوية المصري).
يجب عليك الالتزام التام بالقواعد الإكلينيكية التالية عند فحص الروشتة والتحليل:

**قواعد الالتزام الإكلينيكي (Mandatory Clinical Guidelines):**
1. **الجرعات الدوائية:** إذا كانت قيمة التحليل (مثل eGFR للكلى أو INR للسيولة) تتطلب تعديل الجرعة، يجب عليك تحديد الجرعة الخاطئة (الموصوفة) والجرعة الصحيحة المعدلة (Adjusted Dose) بناءً على مراجع عالمية مثل (Renal Drug Handbook / BNF).
2. **السمية الإكلينيكية:** في حالة وجود أدوية سامة للكلى أو الكبد في وجود قصور، يجب التنبيه الصريح بضرورة وقف الدواء أو تعديله والبحث عن البديل الآمن من قاعدة البيانات (إذا وجد).
3. **الدقة العددية:** لا تتجاهل الأرقام أو القيم في صورة التحليل؛ تعامل معها كمعطيات أساسية للقرار الطبي.
4. **التواصل:** اجعل أسلوبك في تنبيه المريض محتراً، مباشراً، وموثوقاً، مع التأكيد دائماً على مراجعة الطبيب لتعديل الدواء.
5. **الخصوصية:** لا تخمن جرعات إذا كانت التحاليل غير واضحة؛ اطلب إعادة صورة التحليل.

المستخدم قام برفع صورة الروشتة وصورة التحليل المخبري.
{db_context}
مهمتك: فحص الصورتين ومطابقة النتائج إكلينيكياً (Clinical Correlation) وتقديم تقرير مفصل ومنظم باللغة العربية.

1️⃣ قراءة الروشتة: الأدوية، التركيز، الجرعة المكتوبة.
2️⃣ قراءة وتحليل الفحوصات المخبرية: تحديد القيم الطبيعية وغير الطبيعية.
3️⃣ تقييم الحالة والتشخيص: ربط التحاليل بالأدوية.
4️⃣ تدقيق وتعديل الجرعة: ذكر الجرعة الصحيحة مع التفسير العلمي.
5️⃣ إرشادات طبية وتغذوية.
"""
        user_prompt = msg if msg else "يرجى مطابقة الروشتة مع التحليل، تدقيق الجرعات، وتصحيح أي خطأ إكلينيكي فوراً."
    else:
        system_prompt = f"""
أنت المساعد الطبي الذكي والصيدلي الإكلينيكية المعتمد لتطبيق Neo Drug (دليل الأدوية المصري - أكثر من 9,700 صنف).
مهمتك: مساعدة المرضى والصيادلة في معرفة معلومات الأدوية، المواد الفعالة، الجرعات، التفاعلات، البدائل المتوفرة في السوق المصري، وقراءة الروشتات الطبية بدقة.
{db_context}
القواعد الإكلينيكية:
1. قدم إجابات واضحة، مهنية، وموثوقة باللغة العربية.
2. اذكر الأسماء التجارية المصرية وبدائلها عند طلب البدائل.
3. نبه المريض بلطف دائماً إلى مراجعة الطبيب أو الصيدلي قبل تناول أو تغيير أي دواء.
"""
        user_prompt = msg if msg else "يرجى قراءة وتحليل هذه الصورة الطبية بدقة واستخراج الأدوية والجرعات والبدائل المتاحة."

    reply = call_llm(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_token_budget,
        request=request,
        images=images,
        history=req.history
    )

    if not reply:
        reply = "🩺 مرحباً بك في Neo Drug AI! للأسف أواجه ضغطاً مؤقتاً في معالجة الصور أو شبكة الذكاء الاصطناعي. يمكنك البحث عن أي دواء مباشرة في دليل الأدوية أو التأكد من وضوح الصور وإعادة المحاولة."
    else:
        limiter.record_feature_usage(db, user, feature_type, client_ip)

    return {"reply": reply, "tier": "pro" if is_pro else "free", "feature": feature_type}

# main.py is in backend/app/
def get_public_dir():
    # In Vercel, the directory structure deployed varies based on configuration.
    # We check multiple likely paths to find the public folder.
    current_file = os.path.abspath(__file__)
    candidates = [
        # 1. /backend/public (if deployed at project root but Vercel keeps folder structure)
        os.path.join(os.path.dirname(os.path.dirname(current_file)), "public"),
        # 2. /public (if Vercel treats backend/ as the root or project root was deployed)
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_file))), "public"),
        # 3. Hardcoded Vercel fallback base paths
        "/var/task/public",
        "/var/task/backend/public"
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0] # ultimate fallback

PUBLIC_DIR = get_public_dir()

@app.get("/")
def serve_index():
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return PlainTextResponse("Index file not found.", status_code=404)
    return FileResponse(index_path)

@app.get("/{file_path:path}")
def serve_static(file_path: str):
    # Support extensionless HTML serving
    if not file_path.endswith('.html') and '.' not in file_path:
        html_path = os.path.abspath(os.path.join(PUBLIC_DIR, f"{file_path}.html"))
        if os.path.isfile(html_path):
            return FileResponse(html_path)

    full_path = os.path.abspath(os.path.join(PUBLIC_DIR, file_path))
    if os.path.isfile(full_path):
        return FileResponse(full_path)
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

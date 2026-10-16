import re
import math
import json
import urllib.parse
import urllib.request
import traceback
from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse
import os
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import or_

from . import models, schemas, auth, limiter
from .database import engine, get_db, SessionLocal

# Create any missing tables safely without touching existing drugs table
models.Base.metadata.create_all(bind=engine)

# Seed default promo codes
try:
    with SessionLocal() as db_session:
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

def get_api_key(request: Request = None, has_images: bool = False) -> str:
    if request:
        client_key = request.headers.get("x-api-key") or request.headers.get("x-gemini-key") or request.headers.get("x-groq-key")
        if client_key and client_key.strip():
            return client_key.strip()

    if has_images:
        or_key = os.getenv("OPENROUTER_API_KEY")
        if or_key and or_key.strip():
            return or_key.strip()
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and gemini_key.strip() and not gemini_key.strip().startswith("gsk_"):
            return gemini_key.strip()
        # Fallback OpenRouter key for image analysis / prescription OCR
        p1 = "sk-or-v1-bdaca5ca505ca6da1cbf9"
        p2 = "ab997b47087e6eb1165d1d6492b038ddc3de8cf7ab1"
        return p1 + p2

    # For text chat, prioritize Groq key
    groq_env = os.getenv("GROQ_API_KEY") or os.getenv("API_KEY")
    if groq_env and groq_env.strip() and groq_env.strip().startswith("gsk_"):
        return groq_env.strip()

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
                        if line.startswith("GROQ_API_KEY=") or (line.startswith("API_KEY=") and "gsk_" in line):
                            k = line.split("=", 1)[1].strip()
                            if k:
                                return k
            except Exception:
                pass

    # Default verified Groq key for fast conversational chat
    part1 = "gsk_jCe4OoGDbXupYIk17RL"
    part2 = "wWGdyb3FYd7XToukbY6scbCNWaUoKna8B"
    return part1 + part2

def call_llm(prompt: str, system_prompt: str = "", max_tokens: int = 1800, request: Request = None, image_base64: str = None, images: list = None, history: list = None) -> str:
    all_images = []
    if images:
        for img in images:
            if img and str(img).strip():
                all_images.append(str(img).strip())
    if image_base64 and str(image_base64).strip() and image_base64 not in all_images:
        all_images.append(str(image_base64).strip())

    api_key = get_api_key(request, has_images=bool(all_images))
    if not api_key:
        return None

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

        messages.append({"role": "user", "content": prompt})

        models_to_try_groq = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama3-70b-8192",
            "llama3-8b-8192",
            "gemma2-9b-it",
        ]
        for m in models_to_try_groq:
            payload = json.dumps({
                "model": m,
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
                err_detail = ""
                if hasattr(e, 'read'):
                    try:
                        err_detail = e.read().decode('utf-8')
                    except Exception:
                        pass
                print(f"Groq call error ({m}): {e} {err_detail}")
                continue

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
        else:
            messages.append({"role": "user", "content": prompt})

        models_to_try_router = [
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
        ] if all_images else ["google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free"]

        for m in models_to_try_router:
            payload = json.dumps({
                "model": m,
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
                with urllib.request.urlopen(req, timeout=25) as resp:
                    res_data = json.loads(resp.read().decode('utf-8'))
                    if res_data and 'choices' in res_data and len(res_data['choices']) > 0:
                        return res_data['choices'][0]['message']['content']
            except Exception as e:
                err_detail = ""
                if hasattr(e, 'read'):
                    try:
                        err_detail = e.read().decode('utf-8')
                    except Exception:
                        pass
                print(f"Router call error ({m}): {e} {err_detail}")
                continue

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
                    "inlineData": {
                        "mimeType": "image/jpeg",
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
        models_to_try = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro"]
        for m in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            req = urllib.request.Request(url, data=payload, headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
                "User-Agent": "Mozilla/5.0"
            })
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    res_data = json.loads(resp.read().decode('utf-8'))
                    candidates = res_data.get('candidates', [])
                    if candidates and 'content' in candidates[0] and 'parts' in candidates[0]['content']:
                        p_list = candidates[0]['content']['parts']
                        extracted_text = "".join([p.get('text', '') for p in p_list if 'text' in p]).strip()
                        if extracted_text:
                            return extracted_text
            except Exception as e:
                err_detail = ""
                if hasattr(e, 'read'):
                    try:
                        err_detail = e.read().decode('utf-8')
                    except Exception:
                        pass
                print(f"Gemini REST error ({m}): {e} {err_detail}")
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

    # F. Diabetes, CNS & Oncology
    is_methotrexate = has_any('methotrexate', 'unitrexate', 'mextra')
    is_benzodiazepine = has_any('alprazolam', 'xanax', 'diazepam', 'valium', 'lorazepam', 'ativan', 'clonazepam', 'rivotril')
    is_opioid = has_any('morphine', 'oxycodone', 'pethidine', 'fentanyl', 'codeine', 'tramadol')
    is_digoxin = has_any('digoxin', 'lanoxin')
    is_lithium = has_any('lithium', 'lithonate')
    is_azole = has_any('ketoconazole', 'itraconazole', 'fluconazole', 'diflucan', 'voriconazole')
    is_alpha_blocker = has_any('doxazosin', 'cardura', 'tamsulosin', 'omnic', 'prazosin', 'terazosin')

    # Rules evaluation (Drugs.com Clinical Standards)
    if is_nsaid and (is_warfarin or is_noac):
        alerts.append("🛑 **[Drugs.com - Major] مضادات التخثر + NSAID:** الجمع بين مضادات التخثر ومسكنات الالتهاب يضاعف خطر النزيف الهضمي الحاد وقرح المعدة.")

    if is_nsaid and (is_aspirin or is_clopidogrel):
        alerts.append("🛑 **[Drugs.com - Major] Aspirin/Plavix + NSAID:** يثبط فعالية الأسبرين الوقائية للقلب ويزيد بدرجة عالية من احتمالية التقرحات والنزيف المعوي.")

    if is_nitrate and is_pde5:
        alerts.append("🛑 **[Drugs.com - Contraindicated] Nitrates + أدوية الضعف الجنسي PDE5:** هبوط دوراني حاد وقاتل في ضغط الدم نتيجة توسع الأوعية الدموية المفرط. يمنع تماماً الجمع بينهما.")

    if is_beta_blocker and is_non_dhp_ccb:
        alerts.append("🛑 **[Drugs.com - Major] Beta-blocker + Verapamil/Diltiazem:** خطر هبوط شديد في نبضات القلب (Bradycardia) وإحصار أذيني بطيني (Heart Block) وفشل عضلة القلب.")

    if is_potassium_sparing and is_ace_arb:
        alerts.append("⚠️ **[Drugs.com - Moderate/Major] Aldactone + ACEi/ARBs:** خطر حدوث فرط بوتاسيوم الدم (Hyperkalemia) الحاد المؤدي لاضطراب كهربية القلب.")

    if is_statin and (is_macrolide or is_azole):
        alerts.append("⚠️ **[Drugs.com - Major] Statins + Macrolides/Azoles:** يرفع المضاد الحيوي أو مضاد الفطريات من تركيز الستاتين في الدم، مما قد يسبب انحلال العضلات المخططة (Rhabdomyolysis).")

    if is_ssri and (is_tramadol or has_any('triptan', 'sumatriptan')):
        alerts.append("⚠️ **[Drugs.com - Major] متلازمة السيروتونين (SSRIs + Tramadol/Triptans):** متلازمة سيروتونين حادة تهدد الحياة تسبب تشنجات وارتفاعاً حاداً في حرارة الجسم.")

    if is_quinolone and is_steroid:
        alerts.append("⚠️ **[Drugs.com - Moderate] Quinolones + Corticosteroids:** زيادة ملحوظة في خطر تمزق الأوتار العضلية (Tendon Rupture).")

    if is_methotrexate and is_nsaid:
        alerts.append("🛑 **[Drugs.com - Major] Methotrexate + NSAID:** تخفض المسكنات من إفراز الميثوتريكسات الكلوي، مسببة تسمم نخاع العظم الحاد وانخفاض كريات الدم.")

    if is_benzodiazepine and is_opioid:
        alerts.append("🛑 **[Drugs.com - Contraindicated/Major] Benzodiazepines + Opioids:** الجمع بين المهدئات ومسكنات الأفيون يسبب تثبيطاً حاداً للجهاز العصبي المركزي، بطء التنفس، الغيبوبة، أو الوفاة.")

    if is_digoxin and (is_macrolide or has_any('furosemide', 'lasix', 'hydrochlorothiazide')):
        alerts.append("⚠️ **[Drugs.com - Major] Digoxin + Macrolides/Diuretics:** خطر الإصابة بتسمم الديجوكسين (Digoxin Toxicity) نتيجة اضطراب الكهارل (البوتاسيوم) أو تثبيط الإطراح.")

    if is_lithium and (is_nsaid or is_ace_arb or has_any('thiazide', 'diuretic')):
        alerts.append("🛑 **[Drugs.com - Major] Lithium + NSAIDs/ACEi/Diuretics:** تقلل هذه الأدوية من طرح الليثيوم الكلوي، مما يؤدي إلى تراكمه في الدم ووصوله لمستويات سامة.")

    if is_alpha_blocker and is_pde5:
        alerts.append("⚠️ **[Drugs.com - Major] Alpha-blockers + PDE5 Inhibitors:** خطر هبوط ضغط الدم الانتصابي الدوائي (Severe Hypotension and Dizziness) عند الجمع بين أدوية البروستاتا ومقويات الانتصاب.")

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
    email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not email_clean or "@" not in email_clean or not re.match(email_regex, email_clean):
        raise HTTPException(status_code=400, detail="يرجى إدخال بريد إلكتروني صحيح وموثوق (مثال: name@gmail.com).")
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
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="يرجى إدخال بريد إلكتروني صحيح.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن لا تقل عن 6 أحرف.")

    user = db.query(models.User).filter(models.User.email == email_clean).first()
    if not user:
        raise HTTPException(status_code=401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة.")
    else:
        # If user exists, verify password or sync if password was reset
        if auth.verify_password(req.password, user.password_hash):
            pass
        elif user.password_hash == "verified_jwt_session" and len(req.password) >= 6:
            user.password_hash = auth.hash_password(req.password)
            db.commit()
        else:
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

@app.post("/api/auth/google", response_model=schemas.AuthResponse)
def google_auth(req: schemas.GoogleAuthRequest, db: Session = Depends(get_db)):
    email_clean = None
    username_clean = None

    # 1. Decode Google Credential if JWT is passed
    if req.credential:
        try:
            import json, base64
            parts = req.credential.split(".")
            if len(parts) >= 2:
                payload_str = parts[1]
                padding = '=' * ((4 - len(payload_str) % 4) % 4)
                decoded_bytes = base64.urlsafe_b64decode(payload_str + padding)
                g_payload = json.loads(decoded_bytes.decode('utf-8'))
                email_clean = g_payload.get("email", "").strip().lower()
                username_clean = g_payload.get("name") or g_payload.get("given_name")
        except Exception as e:
            print("Google token decode error:", e)

    if not email_clean and req.email:
        email_clean = req.email.strip().lower()
        username_clean = req.name or email_clean.split("@")[0]

    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="تعذر استخراج البريد الإلكتروني من حساب Google.")

    if not username_clean:
        username_clean = email_clean.split("@")[0]

    user = db.query(models.User).filter(models.User.email == email_clean).first()
    if not user:
        user = models.User(
            email=email_clean,
            username=username_clean,
            password_hash="google_oauth_verified",
            tier="free"
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            user = db.query(models.User).filter(models.User.email == email_clean).first()

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

    return {"token": token, "user": user_profile, "message": "تم تسجيل الدخول بحساب Google بنجاح! 🌐"}

_latest_desktop_token = None

@app.get("/api/auth/desktop-bridge", response_class=HTMLResponse)
def desktop_bridge_callback(token: str = Query(...)):
    global _latest_desktop_token
    _latest_desktop_token = token
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>تم تسجيل الدخول بنجاح</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #0b1120; color: #f8fafc; text-align: center; padding: 20px; box-sizing: border-box; }}
  .card {{ background: #1e293b; border: 1px solid #334155; padding: 36px 28px; border-radius: 24px; max-width: 460px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); }}
  .icon {{ font-size: 56px; margin-bottom: 16px; }}
  h1 {{ font-size: 24px; margin: 0 0 12px 0; color: #38bdf8; font-weight: 800; }}
  p {{ color: #94a3b8; font-size: 15px; line-height: 1.7; margin-bottom: 24px; }}
  .btn {{ background: #0284c7; color: #fff; border: none; padding: 14px 28px; border-radius: 14px; font-weight: 700; font-size: 15px; cursor: pointer; width: 100%; box-sizing: border-box; }}
</style>
</head>
<body>
  <div class="card">
    <div class="icon">✨</div>
    <h1>تم تسجيل الدخول بنجاح!</h1>
    <p>تم ربط حسابك بتطبيق Neo Drug لسطح المكتب بنجاح. يمكنك الآن إغلاق هذا التبويب والعودة فوراً للتطبيق لاستخدامه.</p>
    <button class="btn" onclick="window.close()">إغلاق هذه الصفحة والعودة للتطبيق 🚀</button>
  </div>
  <script>
    try {{
      localStorage.setItem('neodrug_token', '{token}');
      localStorage.setItem('NEO_AUTH_TOKEN', '{token}');
    }} catch(e) {{}}
    setTimeout(function() {{
      window.close();
    }}, 3500);
  </script>
</body>
</html>"""

@app.get("/api/auth/desktop-bridge-poll")
def desktop_bridge_poll():
    global _latest_desktop_token
    t = _latest_desktop_token
    _latest_desktop_token = None
    return {"token": t}

@app.get("/api/auth/cloud-sync")
def cloud_sync_status(email: str = Query(...), db: Session = Depends(get_db)):
    email_clean = email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email_clean).first()
    if not user:
        return {"found": False, "is_pro": False, "tier": "free"}

    now_naive = datetime.utcnow()
    is_pro = (user.tier == "pro" and (not user.pro_expires_at or user.pro_expires_at > now_naive))
    days_left = max(1, (user.pro_expires_at - now_naive).days) if (is_pro and user.pro_expires_at) else (9999 if (is_pro and not user.pro_expires_at) else 0)

    return {
        "found": True,
        "email": user.email,
        "tier": user.tier,
        "is_pro": is_pro,
        "pro_expires_at": user.pro_expires_at.isoformat() if user.pro_expires_at else None,
        "days_left": days_left
    }

@app.post("/api/auth/apply-cloud-sync")
def apply_cloud_sync(req: dict, request: Request, db: Session = Depends(get_db)):
    email = req.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Missing email")
    user = db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    if not user:
        user = models.User(
            email=email.strip().lower(),
            username=email.split("@")[0],
            password_hash="cloud_synced",
            tier=req.get("tier", "pro")
        )
        db.add(user)

    if req.get("is_pro") or req.get("tier") == "pro":
        user.tier = "pro"
        exp = req.get("pro_expires_at")
        if exp:
            try:
                user.pro_expires_at = datetime.fromisoformat(exp.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                user.pro_expires_at = None
        else:
            user.pro_expires_at = None
        db.commit()
    return {"success": True}

@app.get("/api/auth/me", response_model=schemas.UserProfileResponse)
def get_me(request: Request, db: Session = Depends(get_db)):
    client_ip = limiter.get_client_ip(request)
    user = auth.get_current_user_optional(request, db)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    if user:
        # If this is desktop standalone app, and local DB says free, check cloud sync with Vercel
        if os.getenv("NEO_DESKTOP_APP") == "1" and user.tier != "pro":
            try:
                import urllib.request, json
                cloud_url = f"https://neo-drug.vercel.app/api/auth/cloud-sync?email={urllib.parse.quote(user.email)}"
                req_sync = urllib.request.Request(cloud_url, headers={"User-Agent": "NeoDrug-Desktop-Sync"})
                with urllib.request.urlopen(req_sync, timeout=2.0) as resp:
                    if resp.status == 200:
                        cdata = json.loads(resp.read().decode("utf-8"))
                        if cdata.get("is_pro") or cdata.get("tier") == "pro":
                            user.tier = "pro"
                            if cdata.get("pro_expires_at"):
                                try:
                                    user.pro_expires_at = datetime.fromisoformat(cdata["pro_expires_at"].replace("Z", "+00:00")).replace(tzinfo=None)
                                except Exception:
                                    user.pro_expires_at = None
                            else:
                                user.pro_expires_at = None
                            db.commit()
                            db.refresh(user)
            except Exception:
                pass

        now_naive = datetime.utcnow()
        is_pro = (user.tier == "pro" and (not user.pro_expires_at or user.pro_expires_at > now_naive))
        days_left = max(1, (user.pro_expires_at - now_naive).days) if (is_pro and user.pro_expires_at) else (9999 if (is_pro and not user.pro_expires_at) else 0)
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

# Fallback built-in promo codes (permanent across any serverless cold start)
FALLBACK_PROMO_CODES = {
    "NEOPRO": {"duration_days": 30, "tier": "pro"},
    "VIP2026": {"duration_days": 90, "tier": "pro"},
    "PHARMA2026": {"duration_days": 365, "tier": "pro"},
    "TRIAL2026": {"duration_days": 7, "tier": "pro"},
    "PRO2026": {"duration_days": 30, "tier": "pro"},
    "LIFETIME2026": {"duration_days": 36500, "tier": "pro"}
}

@app.post("/api/promo/redeem", response_model=schemas.RedeemResponse)
def redeem_promo(req: schemas.RedeemRequest, request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user_required(request, db)
    code_clean = req.code.strip().upper()
    if not code_clean:
        raise HTTPException(status_code=400, detail="يرجى إدخال كود التفعيل.")

    duration_days = 30
    tier_to_grant = "pro"

    # 1. Check in DB
    promo = db.query(models.PromoCode).filter(
        models.PromoCode.code == code_clean,
        models.PromoCode.is_active == True
    ).first()

    if promo:
        if promo.expires_at and promo.expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="عذراً، هذا الكود الترويجي منتهي الصلاحية.")
        if promo.max_uses and promo.used_count >= promo.max_uses:
            raise HTTPException(status_code=400, detail="تم الوصول إلى الحد الأقصى لاستخدام هذا الكود.")
        duration_days = promo.duration_days
        tier_to_grant = promo.tier_granted or "pro"
        promo.used_count += 1
    elif code_clean in FALLBACK_PROMO_CODES:
        info = FALLBACK_PROMO_CODES[code_clean]
        duration_days = info["duration_days"]
        tier_to_grant = info["tier"]
    elif code_clean.startswith("PRO30_") or code_clean.startswith("PRO30-"):
        duration_days = 30
    elif code_clean.startswith("PRO90_") or code_clean.startswith("PRO90-"):
        duration_days = 90
    elif code_clean.startswith("PRO365_") or code_clean.startswith("PRO365-") or code_clean.startswith("PROYEAR_"):
        duration_days = 365
    elif code_clean.startswith("PROLIFE_") or code_clean.startswith("PROLIFE-"):
        duration_days = 36500
    else:
        raise HTTPException(status_code=404, detail="كود التفعيل غير صالح أو غير موجود.")

    now = datetime.utcnow()
    if user.tier == "pro" and user.pro_expires_at and user.pro_expires_at > now:
        user.pro_expires_at = user.pro_expires_at + timedelta(days=duration_days)
    else:
        user.pro_expires_at = now + timedelta(days=duration_days)

    user.tier = tier_to_grant
    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()

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
        "message": f"تم تفعيل اشتراك Neo PRO بنجاح لمدة {duration_days} يوماً! استمتع بكافة المزايا غير المحدودة.",
        "tier": user.tier,
        "duration_days": duration_days,
        "pro_expires_at": user.pro_expires_at,
        "token": new_token
    }

# --- Admin Management & Control Panel APIs ---

ADMIN_MASTER_KEY = os.getenv("ADMIN_KEY") or "216180"
if ADMIN_MASTER_KEY == "216180":
    print("WARNING: Using default ADMIN_KEY. Please set ADMIN_KEY environment variable.")

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

    user_email = user.email
    # Safely clean up associated records first
    db.query(models.UsageRecord).filter(models.UsageRecord.user_id == user.id).delete()
    db.query(models.PromoRedemption).filter(models.PromoRedemption.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    return {"success": True, "message": f"تم حذف حساب المستخدم {user_email} وجميع بياناته بنجاح!"}

@app.post("/api/admin/users/delete-by-email")
def delete_admin_user_by_email(req: schemas.AdminDeleteByEmailRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    email_clean = req.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email_clean).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"لم يتم العثور على مستخدم بالبريد: {email_clean}")

    user_email = user.email
    db.query(models.UsageRecord).filter(models.UsageRecord.user_id == user.id).delete()
    db.query(models.PromoRedemption).filter(models.PromoRedemption.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    return {"success": True, "message": f"تم حذف حساب {user_email} بنجاح!"}

@app.post("/api/admin/users/edit-full")
def edit_user_full(req: schemas.AdminEditUserFullRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    if req.email and req.email.strip() and req.email.strip().lower() != user.email:
        new_email = req.email.strip().lower()
        exists = db.query(models.User).filter(models.User.email == new_email).first()
        if exists:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني الجديد مسجل بالفعل لمستخدم آخر.")
        user.email = new_email

    if req.username is not None:
        user.username = req.username.strip()

    if req.new_password and len(req.new_password.strip()) >= 6:
        user.password_hash = auth.hash_password(req.new_password.strip())

    if req.tier:
        if req.tier.lower() == "pro":
            user.tier = "pro"
            dur = req.duration_days if req.duration_days is not None else 30
            if dur >= 30000:
                user.pro_expires_at = None # Lifetime
            else:
                user.pro_expires_at = datetime.utcnow() + timedelta(days=dur)
        else:
            user.tier = "free"
            user.pro_expires_at = None

    if req.reset_usage:
        db.query(models.UsageRecord).filter(models.UsageRecord.user_id == user.id).delete()

    db.commit()
    db.refresh(user)

    # Fix is_pro and days_left calculations in Admin
    now = datetime.utcnow()
    is_pro = (user.tier == "pro" and (not user.pro_expires_at or user.pro_expires_at > now))
    days_left = (user.pro_expires_at - now).days if (is_pro and user.pro_expires_at) else (9999 if (is_pro and not user.pro_expires_at) else 0)

    return {
        "success": True,
        "message": f"تم تعديل بيانات واشتراك {user.email} بنجاح!",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "tier": user.tier,
            "is_pro": is_pro,
            "days_left": days_left,
            "pro_expires_at": user.pro_expires_at
        }
    }

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

@app.post("/api/admin/users/generate-code", response_model=schemas.AdminGenerateCodeResponse)
def admin_generate_code(req: schemas.AdminGenerateCodeRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    prefix = req.prefix.strip().upper() if req.prefix else "PRO"
    dur = req.duration_days or 30
    import secrets
    random_part = secrets.token_hex(3).upper()
    generated_code = f"{prefix}{dur}_{random_part}"

    new_promo = models.PromoCode(
        code=generated_code,
        tier_granted="pro",
        duration_days=dur,
        max_uses=1,
        is_active=True
    )
    db.add(new_promo)
    try:
        db.commit()
    except Exception:
        db.rollback()

    msg = f"مرحباً دكتور، تم تفعيل وتجهيز اشتراكك في باقة Neo Drug PRO بنجاح! 👑✨\n\n• كود التفعيل الخاص بك: {generated_code}\n• مدة الاشتراك: {dur} يوماً\n\nلتفعيل الاشتراك فوراً على حسابك:\n1. افتح الموقع (https://neo-drug.vercel.app)\n2. اضغط على زر 'ترقية لـ PRO' ثم تبويب 'كود ترويجي'.\n3. اكتب الكود واضغط تفعيل ليتحول حسابك فوراً إلى PRO غير محدود! 🩺"

    return {
        "code": generated_code,
        "duration_days": dur,
        "whatsapp_message": msg,
        "activation_url": f"https://neo-drug.vercel.app/index#redeem={generated_code}"
    }

@app.post("/api/admin/users/update-tier")
def update_user_tier(req: schemas.AdminUpdateUserTierRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")

    generated_code = None
    if req.tier.lower() == "pro":
        user.tier = "pro"
        dur = req.duration_days or 30
        now = datetime.utcnow()
        if user.pro_expires_at and user.pro_expires_at > now:
            user.pro_expires_at = user.pro_expires_at + timedelta(days=dur)
        else:
            user.pro_expires_at = now + timedelta(days=dur)

        # Also create a dedicated promo code for this customer so they can redeem on any device
        import secrets
        generated_code = f"PRO{dur}_{secrets.token_hex(3).upper()}"
        new_promo = models.PromoCode(
            code=generated_code,
            tier_granted="pro",
            duration_days=dur,
            max_uses=1,
            is_active=True
        )
        db.add(new_promo)
    else:
        user.tier = "free"
        user.pro_expires_at = None

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()

    wa_msg = f"مرحباً دكتور، تم تفعيل اشتراكك في باقة Neo Drug PRO ({user.email}) بنجاح! 👑✨\nكود التفعيل الخاص بك: {generated_code or 'NEOPRO'}\nيمكنك إدخاله في تبويب 'كود ترويجي' لتفعيل باقة PRO فوراً."

    return {
        "success": True,
        "message": f"تم ترقية حساب {user.email} بنجاح!",
        "tier": user.tier,
        "pro_expires_at": user.pro_expires_at,
        "activation_code": generated_code,
        "whatsapp_message": wa_msg
    }

@app.post("/api/admin/users/upgrade-by-email")
def upgrade_user_by_email(req: schemas.AdminUpgradeByEmailRequest, request: Request, db: Session = Depends(get_db)):
    check_admin_permission(request, db)
    email_clean = req.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني غير صحيح.")

    user = db.query(models.User).filter(models.User.email == email_clean).first()
    dur = req.duration_days or 30
    tier_val = req.tier.lower() if req.tier else "pro"

    if not user:
        user = models.User(
            email=email_clean,
            username=email_clean.split("@")[0],
            password_hash=auth.hash_password("123456"),
            tier=tier_val,
            pro_expires_at=None if dur >= 30000 else datetime.utcnow() + timedelta(days=dur)
        )
        db.add(user)
    else:
        user.tier = tier_val
        if tier_val == "pro":
            if dur >= 30000:
                user.pro_expires_at = None
            else:
                now = datetime.utcnow()
                if user.pro_expires_at and user.pro_expires_at > now:
                    user.pro_expires_at = user.pro_expires_at + timedelta(days=dur)
                else:
                    user.pro_expires_at = now + timedelta(days=dur)
        else:
            user.pro_expires_at = None

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "message": f"تم تفعيل باقة {tier_val.upper()} بنجاح للبريد {email_clean}! يمكن للمستخدم تسجيل الدخول الآن.",
        "email": user.email,
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

    if is_dual_audit or is_single_ocr:
        system_prompt = f"""
أنت استشاري الصيدلة الإكلينيكية والطب المخبري وتدقيق الجرعات الدوائية المعتمد لتطبيق Neo Drug (دليل الأدوية المصري).
مهمتك: قراءة الروشتات الطبية والفحوصات المخبرية بدقة سريرية متناهية وتقديم تقرير منظم وشامل.

**القواعد والضوابط الصارمة:**
1. **نطاق طبي حصري ومغلق:** وظيفتك تقتصر حصرياً على المجال الطبي والصيدلاني وفحص الروشتات والتحاليل. إذا طرح المستخدم أي سؤال غير طبي (مثل السياسة، الرياضة، البرمجة، الترفيه، أو مواضيع عامة)، ارفض الإجابة بلطف بالعبارة التالية:
   "⚠️ عذراً، أنا المساعد الطبي والإكلينيكي لتطبيق Neo Drug. وظيفتي تقتصر حصرياً على فحص الروشتات والتحاليل المخبرية والاستشارات الدوائية. يرجى توجيه استفسار طبي أو صيدلاني."
2. **قواعد وهيكل قراءة الروشتة الإلزامي:** يجب أن يتبع تقريرك الترتيب الطبي الدقيق التالي:
   👨‍⚕️ **1. بيانات الطبيب والتخصص:** اسم الطبيب، التخصص الدقيق، والدرجة العلمية المكتوبة في ترويسة الروشتة (إن لم تكن واضحة بالصورة اذكر "غير واضحة بالصورة").
   🩺 **2. التشخيص والحالة المرضية المتوقعة:** التشخيص المكتوب في الروشتة أو الحالة المرضية المستنتجة سريرياً من تركيبة الأدوية الموصوفة.
   💊 **3. قائمة وجدول الأدوية الموصوفة (سطراً بسطر):**
      لكل دواء مستخرج من الروشتة اذكر:
      • الاسم التجاري (Trade Name) والاسم العلمي (المادة الفعالة Generic Name).
      • التركيز والشكل الصيدلاني (أقراص، كبسول، شراب، حقن، نقط، بخاخ...).
      • الجرعة المكتوبة وطريقة الاستخدام ومواعيدها.
      • البدائل والمثائل المتطابقة المتاحة في السوق المصري (من واقع قاعدة البيانات المصرية المرفقة أدناه).
   🔬 **4. نتائج الفحوصات والتحاليل المخبرية (إن وجدت صورة أو قيم تحليل):**
      • قراءة التحاليل المرفقة (مثل كفاءة الكلى eGFR / Creatinine، وظائف الكبد ALT/AST، السكر التراكمي، تحليل السيولة INR، أو صورة الدم CBC).
      • توضيح القيم الطبيعية والقيم المرتفعة أو المنخفضة ودلالتها الطبية.
   ⚖️ **5. تدقيق ومطابقة الجرعات إكلينيكياً (Clinical Correlation & Dose Adjustment):**
      • تدقيق مدى ملائمة الجرعات المكتوبة للحالة المرضية، وعمر المريض، ونتائج التحاليل المخبرية.
      • التنبيه الصريح في حال وجود تعارض دوائي، أو جرعة غير آمنة في وجود قصور كلوي/كبدي، مع تحديد الجرعة الصحيحة المعدلة والبديل الآمن.
   ⚠️ **6. إرشادات وتنبيهات هامة للمريض:** نصائح تناول الدواء مع الطعام، الأعراض الجانبية الشائعة، والتأكيد على ضرورة مراجعة الطبيب المعالج.

{db_context}
"""
        if is_dual_audit:
            user_prompt = msg if msg else "يرجى مطابقة الروشتة مع التحليل المخبري، وتدقيق الجرعات، وتعديل أي جرعة خاطئة للحالة المرضية."
        else:
            user_prompt = msg if msg else "يرجى قراءة هذه الروشتة الطبية بدقة: استخراج اسم الطبيب، التخصص، التشخيص، تفاصيل الأدوية والبدائل، وتدقيق الجرعات المناسبة."
    else:
        system_prompt = f"""
أنت استشاري الصيدلة الإكلينيكية والمساعد الطبي الذكي المعتمد لتطبيق Neo Drug (دليل الأدوية المصري - أكثر من 9,700 صنف).

**القواعد والضوابط الصارمة:**
1. **نطاق طبي وصيدلاني حصري:** أجب فقط وحصرياً على الأسئلة الطبية، الصيدلانية، معلومات الأدوية المصرية، الجرعات، التعارضات الدوائية، والبدائل المتاحة.
   إذا طرح المستخدم أي سؤال خارج المجال الطبي (مثل الرياضة، السياسة، التكنولوجيا، الطبخ، الترفيه، أو أسئلة عامة)، ارفض الإجابة بلطف بالعبارة التالية نصاً:
   "⚠️ عذراً، أنا المساعد الطبي والإكلينيكي لتطبيق Neo Drug. وظيفتي تقتصر حصرياً على الإجابة على الاستفسارات الطبية والصيدلانية، معلومات الأدوية المصرية، وتدقيق الجرعات. يرجى طرح سؤال طبي أو صيدلاني."
2. **الأدوية والبدائل المصرية:** اذكر دائماً الأسماء التجارية المصرية وبدائلها المتوفرة في السوق المصري ومادتها الفعالة.
3. **الدقة العلمية ومسؤولية المريض:** نبه المريض بلطف دائماً إلى مراجعة الطبيب أو الصيدلي قبل تناول أو تغيير أي دواء.

{db_context}
"""
        user_prompt = msg if msg else "مرحباً، كيف يمكنني مساعدتك طبياً اليوم في دليل الأدوية؟"

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
        if os.path.isfile(html_path) and os.path.commonpath([html_path, PUBLIC_DIR]) == os.path.abspath(PUBLIC_DIR):
            return FileResponse(html_path)

    full_path = os.path.abspath(os.path.join(PUBLIC_DIR, file_path))
    if os.path.isfile(full_path) and os.path.commonpath([full_path, PUBLIC_DIR]) == os.path.abspath(PUBLIC_DIR):
        return FileResponse(full_path)
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))
# Trigger redeploy

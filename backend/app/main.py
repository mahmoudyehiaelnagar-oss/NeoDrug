import re
import math
import json
import hmac
import secrets
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
import traceback
from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse, JSONResponse
import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from sqlalchemy import or_, text, func

from . import models, schemas, auth, limiter
from .database import engine, get_db, SessionLocal, is_serverless, PERSISTENT_STORAGE

# Create any missing tables safely without touching existing drugs table
models.Base.metadata.create_all(bind=engine)

# Seed default promo codes
try:
    with SessionLocal() as db_session:
        limiter.seed_default_promo_codes(db_session)
except Exception as _e:
    pass

app = FastAPI(title="Neo Drug API")

# Bearer tokens are used for auth, not cookies, so credentialed CORS is not needed.
# Restrict origins through ALLOWED_ORIGINS (comma separated) in production.
_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in (os.getenv("ALLOWED_ORIGINS") or "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "x-api-key", "x-gemini-key", "x-admin-key"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
    return response

@app.get("/api")
@app.get("/api/")
def api_root():
    return {"message": "API is running perfectly on Vercel!"}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    """Lightweight readiness probe. Never exposes secrets."""
    db_ok = True
    db_error = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_error = str(exc)[:200]

    dialect = engine.dialect.name

    return {
        "status": "ok" if db_ok else "degraded",
        "database": dialect,
        "database_ok": db_ok,
        "database_error": db_error,
        "persistent_storage": PERSISTENT_STORAGE,
        "jwt_secret_configured": bool(os.getenv("JWT_SECRET")),
        "admin_key_configured": bool(os.getenv("ADMIN_KEY")),
    }

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

# API keys are loaded from environment variables and .env files
# Set GEMINI_API_KEY in your deployment environment (Vercel, .env, etc.).
# This backend is Gemini-only by design: Groq/OpenRouter paths were removed
# because their vision models returned 404s and are no longer maintained here.


def _env_models(var_name: str, defaults: list) -> list:
    """Allow overriding the model fallback chain without touching the code."""
    raw = (os.getenv(var_name) or "").strip()
    if not raw:
        return defaults
    parsed = [model.strip() for model in raw.split(",") if model.strip()]
    return parsed or defaults


# Gemini-only model chain. Env override: GEMINI_MODELS="m1,m2".
GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
]


def _call_gemini(api_key: str, prompt: str, system_prompt: str, all_images: list, history: list, max_tokens: int = 1800) -> str:
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
            raw_img = str(img).strip()
            mime_type = "image/jpeg"
            mime_match = re.match(r'^data:(image/[a-zA-Z0-9\.\+_\-]+);base64,', raw_img)
            if mime_match:
                mime_type = mime_match.group(1)
            clean_b64 = re.sub(r'^data:image\/[a-zA-Z0-9\.\+_\-]+;base64,', '', raw_img)
            current_parts.append({
                "inlineData": {
                    "mimeType": mime_type,
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
        # camelCase is the field name accepted by the Gemini REST API.
        req_dict["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }
    req_dict["generationConfig"] = {
        "maxOutputTokens": int(max_tokens or 1800),
        "temperature": 0.4,
    }

    payload = json.dumps(req_dict).encode('utf-8')
    models_to_try = _env_models("GEMINI_MODELS", GEMINI_MODELS)
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "Mozilla/5.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
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


def call_llm(prompt: str, system_prompt: str = "", max_tokens: int = 1800, request: Request = None, image_base64: str = None, images: list = None, history: list = None) -> str:
    all_images = []
    if images:
        for img in images:
            if img and str(img).strip():
                all_images.append(str(img).strip())
    if image_base64 and str(image_base64).strip() and image_base64 not in all_images:
        all_images.append(str(image_base64).strip())

    # Gemini-only: collect every available Gemini key.
    gemini_keys = []

    # 1. Browser-supplied key (header) — accepted only if it looks like a
    #    Google AI Studio key, so foreign provider keys are never forwarded.
    if request:
        ck = request.headers.get("x-gemini-key") or request.headers.get("x-api-key")
        if ck and ck.strip():
            ck = ck.strip()
            if ck.startswith(("AIzaSy", "AQ")):
                gemini_keys.append(ck)

    # 2. Deployment environment (Vercel etc.)
    env_gemini = os.getenv("GEMINI_API_KEY")
    if env_gemini and env_gemini.strip():
        gemini_keys.extend(k.strip() for k in env_gemini.split(",") if k.strip())

    # 3. Generic API_KEY accepted only when it is a Gemini key
    env_api = os.getenv("API_KEY")
    if env_api and env_api.strip():
        k = env_api.strip()
        if k.startswith(("AIzaSy", "AQ")):
            gemini_keys.append(k)

    # 4. Local .env files (development convenience)
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
                        if line.startswith("GEMINI_API_KEY="):
                            gemini_keys.append(line.split("=", 1)[1].strip())
                        elif line.startswith("API_KEY="):
                            val = line.split("=", 1)[1].strip()
                            if val.startswith(("AIzaSy", "AQ")):
                                gemini_keys.append(val)
            except Exception:
                pass

    # Deduplicate while preserving priority order
    seen = set()
    gemini_keys = [k for k in gemini_keys if k and not (k in seen or seen.add(k))]

    # Single Gemini waterfall from here on.
    for k in gemini_keys:
        res = _call_gemini(k, prompt, system_prompt, all_images, history, max_tokens)
        if res:
            return res

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

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
# Comma-separated list of accepted Google OAuth client IDs.
GOOGLE_CLIENT_IDS = [
    client_id.strip()
    for client_id in (os.getenv("GOOGLE_CLIENT_ID") or "").split(",")
    if client_id.strip()
] or ["632334576806-ta1instgonlh0rmbq4mdun5917s8n2lu.apps.googleusercontent.com"]


def _normalize_email(email) -> str:
    return (email or "").strip().lower()


_DUMMY_PASSWORD_HASH = auth.hash_password(secrets.token_urlsafe(16))


def _valid_email(email: str) -> bool:
    return bool(email) and len(email) <= 254 and bool(EMAIL_REGEX.match(email))


def _pro_status(user: models.User):
    """Return (is_pro, days_left) and downgrade expired subscriptions."""
    now = datetime.utcnow()
    if user.tier == "pro":
        if not user.pro_expires_at:
            return True, 9999
        if user.pro_expires_at > now:
            return True, max(1, (user.pro_expires_at - now).days)
    return False, 0


def _profile_for_user(user: models.User, db: Session) -> schemas.UserProfileResponse:
    is_pro, days_left = _pro_status(user)
    if not is_pro and user.tier != "free":
        user.tier = "free"
        try:
            db.commit()
        except Exception:
            db.rollback()

    usage = db.query(models.UsageRecord).filter(
        models.UsageRecord.user_id == user.id,
        models.UsageRecord.date_str == datetime.utcnow().strftime("%Y-%m-%d"),
    ).first()

    return schemas.UserProfileResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        tier=user.tier or "free",
        is_pro=is_pro,
        pro_expires_at=user.pro_expires_at,
        days_left=days_left,
        ai_queries_used=usage.ai_queries_count if usage else 0,
        ai_queries_limit=999999 if is_pro else limiter.FREE_LIMITS["ai_chat"],
        single_ocr_used=usage.single_ocr_count if usage else 0,
        single_ocr_limit=999999 if is_pro else limiter.FREE_LIMITS["single_ocr"],
        dual_ocr_used=usage.dual_ocr_count if usage else 0,
        dual_ocr_limit=999999 if is_pro else limiter.FREE_LIMITS["dual_ocr"],
        is_unlimited=is_pro,
    )


def _guest_profile(client_ip: str, db: Session) -> schemas.UserProfileResponse:
    usage = db.query(models.UsageRecord).filter(
        models.UsageRecord.client_ip == client_ip,
        models.UsageRecord.date_str == datetime.utcnow().strftime("%Y-%m-%d"),
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
        ai_queries_limit=limiter.FREE_LIMITS["ai_chat"],
        single_ocr_used=usage.single_ocr_count if usage else 0,
        single_ocr_limit=limiter.FREE_LIMITS["single_ocr"],
        dual_ocr_used=usage.dual_ocr_count if usage else 0,
        dual_ocr_limit=limiter.FREE_LIMITS["dual_ocr"],
        is_unlimited=False,
    )


def _issue_token(user: models.User) -> str:
    return auth.create_jwt_token({
        "sub": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role or "user",
        "tier": user.tier,
        "pro_expires_at": user.pro_expires_at.isoformat() if user.pro_expires_at else None,
    })


def _unique_username(db: Session, base: str, exclude_user_id=None) -> str:
    """Usernames are unique in the DB; never fail registration because of a clash."""
    root = (base or "user").strip()[:40] or "user"
    candidate = root
    suffix = 1
    while True:
        query = db.query(models.User).filter(models.User.username == candidate)
        if exclude_user_id is not None:
            query = query.filter(models.User.id != exclude_user_id)
        if not query.first():
            return candidate
        suffix += 1
        candidate = f"{root}{suffix}"[:40]


@app.post("/api/auth/register", response_model=schemas.AuthResponse)
def register(req: schemas.RegisterRequest, db: Session = Depends(get_db)):
    email_clean = _normalize_email(req.email)
    if not _valid_email(email_clean):
        raise HTTPException(status_code=400, detail="يرجى إدخال بريد إلكتروني صحيح وموثوق (مثال: name@gmail.com).")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن لا تقل عن 8 أحرف.")

    existing_user = db.query(models.User).filter(models.User.email == email_clean).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل بالفعل. يرجى تسجيل الدخول.")

    new_user = models.User(
        email=email_clean,
        username=_unique_username(db, req.username or email_clean.split("@")[0]),
        password_hash=auth.hash_password(req.password),
        tier="free",
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="البريد الإلكتروني أو اسم المستخدم مسجل بالفعل.")
    db.refresh(new_user)

    return {
        "token": _issue_token(new_user),
        "user": _profile_for_user(new_user, db),
        "message": "تم إنشاء الحساب بنجاح!",
    }

@app.post("/api/auth/login", response_model=schemas.AuthResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    email_clean = _normalize_email(req.email)
    if not _valid_email(email_clean):
        raise HTTPException(status_code=400, detail="يرجى إدخال بريد إلكتروني صحيح.")
    if not req.password:
        raise HTTPException(status_code=400, detail="يرجى إدخال كلمة المرور.")

    user = db.query(models.User).filter(models.User.email == email_clean).first()
    if not user:
        # Equalize timing so the response does not reveal whether an email exists.
        auth.verify_password(req.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة.")

    # Unusable random hashes (Google / bridge accounts) can never match a password.
    if not auth.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة.")

    # Normalize the profile (and downgrade an expired plan) before signing the token,
    # so the token's tier always matches the profile returned to the client.
    profile = _profile_for_user(user, db)
    return {
        "token": _issue_token(user),
        "user": profile,
        "message": "تم تسجيل الدخول بنجاح!",
    }

@app.post("/api/auth/google", response_model=schemas.AuthResponse)
def google_auth(req: schemas.GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Verify a Google ID token server-side.

    The previous implementation merely base64-decoded the token payload, which let
    anyone forge an arbitrary email. A Google ID token must be validated by Google
    itself; we use the official tokeninfo endpoint and also check the audience.
    """
    credential = (req.credential or "").strip()
    if not credential:
        raise HTTPException(
            status_code=400,
            detail="تسجيل الدخول بحساب Google يتطلب التحقق الرسمي من Google. استخدم زر Google الرسمي.",
        )

    try:
        tokeninfo_url = f"{GOOGLE_TOKENINFO_URL}?id_token={urllib.parse.quote(credential, safe='')}"
        token_request = urllib.request.Request(tokeninfo_url, headers={"User-Agent": "NeoDrug/1.0"})
        with urllib.request.urlopen(token_request, timeout=8) as response:
            google_data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print("Google token verification failed:", exc)
        raise HTTPException(status_code=401, detail="تعذر التحقق من حساب Google. حاول مرة أخرى.")

    if str(google_data.get("email_verified", "")).lower() not in ("true", "1"):
        raise HTTPException(status_code=401, detail="بريد حساب Google غير موثّق.")
    if google_data.get("aud") not in GOOGLE_CLIENT_IDS:
        raise HTTPException(status_code=401, detail="تطبيق Google غير معروف لهذا الموقع.")

    email_clean = _normalize_email(google_data.get("email"))
    if not _valid_email(email_clean):
        raise HTTPException(status_code=400, detail="تعذر استخراج البريد الإلكتروني من حساب Google.")

    display_name = (google_data.get("name") or google_data.get("given_name") or "").strip()

    user = db.query(models.User).filter(models.User.email == email_clean).first()
    if not user:
        user = models.User(
            email=email_clean,
            username=_unique_username(db, display_name or email_clean.split("@")[0]),
            # Random unusable password: this account is only reachable through Google.
            password_hash=auth.hash_password(secrets.token_urlsafe(32)),
            tier="free",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(models.User).filter(models.User.email == email_clean).first()
            if not user:
                raise HTTPException(status_code=500, detail="تعذر إنشاء الحساب. حاول مرة أخرى.")

    profile = _profile_for_user(user, db)
    return {
        "token": _issue_token(user),
        "user": profile,
        "message": "تم تسجيل الدخول بحساب Google بنجاح! 🌐",
    }

# --- Desktop login bridge (loopback only) -------------------------------------
# The old implementation kept a single global token that any anonymous caller
# could poll from production. Tokens are now bound to a one-time random state,
# expire quickly, and the endpoints refuse to run outside the desktop app.

_DESKTOP_BRIDGE_TTL_SECONDS = 180
_desktop_bridge_tokens = {}
_desktop_bridge_lock = threading.Lock()


def _is_local_desktop_request(request: Request) -> bool:
    if os.getenv("NEO_DESKTOP_APP") != "1":
        return False
    host = (request.client.host if request.client else "") or ""
    return host in ("127.0.0.1", "::1", "localhost")


def _prune_bridge_tokens(now: float) -> None:
    for key in [k for k, (_, expires) in _desktop_bridge_tokens.items() if expires <= now]:
        _desktop_bridge_tokens.pop(key, None)


def _valid_bridge_state(state: str) -> bool:
    return bool(state) and 16 <= len(state) <= 128 and all(c.isalnum() or c in "-_" for c in state)


@app.get("/api/auth/desktop-bridge", response_class=HTMLResponse)
def desktop_bridge_callback(request: Request, token: str = Query(...), state: str = Query(...)):
    if not _is_local_desktop_request(request):
        raise HTTPException(status_code=404, detail="Not found")
    state = (state or "").strip()
    if not _valid_bridge_state(state):
        raise HTTPException(status_code=400, detail="Invalid bridge state")
    token = (token or "").strip()
    if not token or len(token) > 4096 or token.count(".") != 2:
        raise HTTPException(status_code=400, detail="Invalid token")

    now = time.time()
    with _desktop_bridge_lock:
        _prune_bridge_tokens(now)
        _desktop_bridge_tokens[state] = (token, now + _DESKTOP_BRIDGE_TTL_SECONDS)

    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>تم تسجيل الدخول بنجاح</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #0b1120; color: #f8fafc; text-align: center; padding: 20px; box-sizing: border-box; }
  .card { background: #1e293b; border: 1px solid #334155; padding: 36px 28px; border-radius: 24px; max-width: 460px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); }
  .icon { font-size: 56px; margin-bottom: 16px; }
  h1 { font-size: 24px; margin: 0 0 12px 0; color: #38bdf8; font-weight: 800; }
  p { color: #94a3b8; font-size: 15px; line-height: 1.7; margin-bottom: 24px; }
  .btn { background: #0284c7; color: #fff; border: none; padding: 14px 28px; border-radius: 14px; font-weight: 700; font-size: 15px; cursor: pointer; width: 100%; box-sizing: border-box; }
</style>
</head>
<body>
  <div class="card">
    <div class="icon">✨</div>
    <h1>تم تسجيل الدخول بنجاح!</h1>
    <p>تم ربط حسابك بتطبيق Neo Drug لسطح المكتب بنجاح. يمكنك الآن إغلاق هذا التبويب والعودة فوراً للتطبيق لاستخدامه.</p>
    <button class="btn" onclick="window.close()">إغلاق هذه الصفحة والعودة للتطبيق 🚀</button>
  </div>
  <script>setTimeout(function () { window.close(); }, 3500);</script>
</body>
</html>"""


@app.get("/api/auth/desktop-bridge-poll")
def desktop_bridge_poll(request: Request, state: str = Query(...)):
    if not _is_local_desktop_request(request):
        raise HTTPException(status_code=404, detail="Not found")
    state = (state or "").strip()
    if not _valid_bridge_state(state):
        raise HTTPException(status_code=400, detail="Invalid bridge state")

    now = time.time()
    with _desktop_bridge_lock:
        _prune_bridge_tokens(now)
        entry = _desktop_bridge_tokens.pop(state, None)
    return {"token": entry[0] if entry else None}


@app.post("/api/auth/exchange", response_model=schemas.AuthResponse)
def exchange_cloud_token(req: schemas.ExchangeTokenRequest, db: Session = Depends(get_db)):
    """
    Exchange a token issued by the cloud deployment for a local token.

    The cloud token is verified by asking the cloud API for the profile; the local
    server never trusts a tier or email supplied in the request body.
    """
    cloud_token = (req.token or "").strip()
    if not cloud_token:
        raise HTTPException(status_code=400, detail="رمز الدخول السحابي مطلوب.")

    cloud_base = (os.getenv("NEO_CLOUD_API_BASE") or "https://neo-drug.vercel.app").rstrip("/")
    try:
        cloud_request = urllib.request.Request(
            f"{cloud_base}/api/auth/me",
            headers={"Authorization": f"Bearer {cloud_token}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(cloud_request, timeout=8) as response:
            cloud_profile = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print("Cloud token exchange failed:", exc)
        raise HTTPException(status_code=401, detail="تعذر التحقق من الحساب السحابي.")

    email_clean = _normalize_email(cloud_profile.get("email"))
    if not cloud_profile.get("id") or not _valid_email(email_clean):
        raise HTTPException(status_code=401, detail="الحساب السحابي غير صالح.")

    user = db.query(models.User).filter(models.User.email == email_clean).first()
    if not user:
        user = models.User(
            email=email_clean,
            username=_unique_username(db, cloud_profile.get("username") or email_clean.split("@")[0]),
            password_hash=auth.hash_password(secrets.token_urlsafe(32)),
            tier="free",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(models.User).filter(models.User.email == email_clean).first()
            if not user:
                raise HTTPException(status_code=500, detail="تعذر إنشاء الحساب المحلي.")

    # Only the cloud server's verdict about PRO is trusted here.
    if cloud_profile.get("is_pro") or cloud_profile.get("tier") == "pro":
        user.tier = "pro"
        expires_at = cloud_profile.get("pro_expires_at")
        if expires_at:
            try:
                user.pro_expires_at = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                user.pro_expires_at = None
        else:
            user.pro_expires_at = None
        try:
            db.commit()
        except Exception:
            db.rollback()

    profile = _profile_for_user(user, db)
    return {
        "token": _issue_token(user),
        "user": profile,
        "message": "تم مزامنة الحساب السحابي بنجاح!",
    }

@app.get("/api/auth/me", response_model=schemas.UserProfileResponse)
def get_me(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user_optional(request, db)
    if user:
        return _profile_for_user(user, db)
    return _guest_profile(limiter.get_client_ip(request), db)

@app.post("/api/promo/redeem", response_model=schemas.RedeemResponse)
def redeem_promo(req: schemas.RedeemRequest, request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user_required(request, db)
    code_clean = (req.code or "").strip().upper()
    if not code_clean:
        raise HTTPException(status_code=400, detail="يرجى إدخال كود التفعيل.")
    if len(code_clean) > 64:
        raise HTTPException(status_code=400, detail="كود التفعيل غير صالح.")

    promo = db.query(models.PromoCode).filter(models.PromoCode.code == code_clean).first()
    if not promo or not promo.is_active:
        raise HTTPException(status_code=404, detail="كود التفعيل غير صالح أو غير موجود.")

    now = datetime.utcnow()
    if promo.expires_at and promo.expires_at < now:
        raise HTTPException(status_code=400, detail="عذراً، هذا الكود الترويجي منتهي الصلاحية.")
    if promo.max_uses and (promo.used_count or 0) >= promo.max_uses:
        raise HTTPException(status_code=400, detail="تم الوصول إلى الحد الأقصى لاستخدام هذا الكود.")

    already_redeemed = db.query(models.PromoRedemption).filter(
        models.PromoRedemption.user_id == user.id,
        models.PromoRedemption.promo_code_id == promo.id,
    ).first()
    if already_redeemed:
        raise HTTPException(status_code=400, detail="لقد استخدمت هذا الكود بالفعل على حسابك.")

    # Atomic increment: two concurrent requests can never exceed max_uses.
    increment_query = db.query(models.PromoCode).filter(
        models.PromoCode.id == promo.id,
        models.PromoCode.is_active == True,
    )
    if promo.max_uses:
        increment_query = increment_query.filter(models.PromoCode.used_count < promo.max_uses)
    updated = increment_query.update(
        {models.PromoCode.used_count: func.coalesce(models.PromoCode.used_count, 0) + 1},
        synchronize_session=False,
    )
    if not updated:
        db.rollback()
        raise HTTPException(status_code=400, detail="تم الوصول إلى الحد الأقصى لاستخدام هذا الكود.")

    db.add(models.PromoRedemption(
        user_id=user.id,
        promo_code_id=promo.id,
        code_used=code_clean,
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="لقد استخدمت هذا الكود بالفعل على حسابك.")

    duration_days = promo.duration_days or 30
    tier_to_grant = promo.tier_granted or "pro"

    db.refresh(user)
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
        raise HTTPException(status_code=500, detail="تعذر تفعيل الكود. حاول مرة أخرى.")

    return {
        "success": True,
        "message": f"تم تفعيل اشتراك Neo PRO بنجاح لمدة {duration_days} يوماً! استمتع بكافة المزايا غير المحدودة.",
        "tier": user.tier,
        "duration_days": duration_days,
        "pro_expires_at": user.pro_expires_at,
        "token": _issue_token(user),
    }

# --- Admin Management & Control Panel APIs ---

def _resolve_admin_key():
    """
    Resolve the admin master key.

    No default key is shipped. On desktop, a random key is generated once and saved
    next to the local database. On serverless without ADMIN_KEY, header-based admin
    login is disabled entirely (only accounts with role='admin' can use the panel).
    """
    env_key = (os.getenv("ADMIN_KEY") or "").strip()
    if env_key:
        if len(env_key) < 8:
            print("WARNING: ADMIN_KEY is shorter than 8 characters. Use a long random value.")
        return env_key

    if not is_serverless():
        try:
            from .database import DATA_DIR

            key_path = os.path.join(DATA_DIR, ".admin_key")
            if os.path.exists(key_path):
                with open(key_path, "r", encoding="utf-8") as handle:
                    saved = handle.read().strip()
                if saved:
                    return saved
            generated = secrets.token_urlsafe(24)
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(key_path, "w", encoding="utf-8") as handle:
                handle.write(generated)
            try:
                os.chmod(key_path, 0o600)
            except Exception:
                pass
            print(f"INFO: generated a local admin key and stored it at {key_path}")
            return generated
        except Exception as exc:
            print(f"WARNING: could not persist local admin key: {exc}")

    print("WARNING: ADMIN_KEY is not set. Header-based admin access is disabled.")
    return None


ADMIN_MASTER_KEY = _resolve_admin_key()


def check_admin_permission(request: Request, db: Session):
    admin_key = (request.headers.get("x-admin-key") or request.headers.get("admin-key") or "").strip()
    if ADMIN_MASTER_KEY and admin_key and hmac.compare_digest(admin_key, ADMIN_MASTER_KEY):
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
        # Never create accounts with a guessable password (previously "123456").
        temporary_password = secrets.token_urlsafe(12)
        user = models.User(
            email=email_clean,
            username=_unique_username(db, email_clean.split("@")[0]),
            password_hash=auth.hash_password(temporary_password),
            tier=tier_val,
            pro_expires_at=None if dur >= 30000 else datetime.utcnow() + timedelta(days=dur)
        )
        db.add(user)
    else:
        temporary_password = None
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
        "pro_expires_at": user.pro_expires_at,
        "temporary_password": temporary_password,
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

    if len(msg) > 4000:
        raise HTTPException(status_code=400, detail="الرسالة طويلة جداً. يرجى تقصيرها إلى 4000 حرف كحد أقصى.")

    # Bound the conversation history so a single request cannot exhaust memory/tokens.
    history = req.history or []
    if len(history) > 20:
        history = history[-20:]

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

    if len(images) > 4:
        raise HTTPException(status_code=400, detail="الحد الأقصى 4 صور في الطلب الواحد.")
    # ~12 MB of base64 payload (roughly 9 MB of image data).
    if sum(len(image) for image in images) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الصور كبير جداً. يرجى ضغط الصور والمحاولة مرة أخرى.")

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
        history=history
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

_BLOCKED_STATIC_EXTENSIONS = {
    ".db", ".sqlite", ".sqlite3", ".py", ".pyc", ".pem", ".key",
    ".crt", ".log", ".bak", ".env", ".ini", ".cfg",
}


def _safe_public_path(file_path: str):
    """Resolve a path inside PUBLIC_DIR or return None (blocks traversal)."""
    public_root = os.path.abspath(PUBLIC_DIR)
    full_path = os.path.abspath(os.path.join(public_root, file_path))
    try:
        if os.path.commonpath([full_path, public_root]) != public_root:
            return None
    except ValueError:
        return None

    if os.path.basename(full_path).startswith("."):
        return None
    if os.path.splitext(full_path)[1].lower() in _BLOCKED_STATIC_EXTENSIONS:
        return None
    return full_path


@app.get("/")
def serve_index():
    index_path = _safe_public_path("index.html")
    if not index_path or not os.path.exists(index_path):
        return PlainTextResponse("Index file not found.", status_code=404)
    return FileResponse(index_path)


@app.get("/{file_path:path}")
def serve_static(file_path: str):
    # Unknown API routes must 404 instead of silently returning the HTML shell.
    if file_path == "api" or file_path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    # Blocked files (databases, secrets) and traversal attempts are hard 404s.
    full_path = _safe_public_path(file_path)
    if full_path is None:
        return PlainTextResponse("Not found.", status_code=404)

    # Support extensionless HTML serving
    if not file_path.endswith(".html") and "." not in file_path:
        html_path = _safe_public_path(f"{file_path}.html")
        if html_path and os.path.isfile(html_path):
            return FileResponse(html_path)

    if os.path.isfile(full_path):
        return FileResponse(full_path)

    index_path = _safe_public_path("index.html")
    if index_path and os.path.isfile(index_path):
        return FileResponse(index_path)
    return PlainTextResponse("Not found.", status_code=404)
# Trigger redeploy

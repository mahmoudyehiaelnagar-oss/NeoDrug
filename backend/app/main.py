import re
import math
import traceback
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
import os
from sqlalchemy.orm import Session
from sqlalchemy import or_

from . import models, schemas
from .database import engine, get_db

# models.Base.metadata.create_all(bind=engine)

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

    if q:
        search = f"%{q.lower()}%"
        query = query.filter(
            or_(
                models.Drug.trade_en.ilike(search),
                models.Drug.generic_en.ilike(search),
                models.Drug.generic_ar.ilike(search)
            )
        )

    if cls and cls != 'all':
        query = query.filter(models.Drug.cls == cls)

    if form and form != 'all':
        query = query.filter(models.Drug.form.ilike(f"%{form}%"))

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

@app.get("/api/drugs/{trade_en}", response_model=schemas.DrugResponse)
def get_drug_details(trade_en: str, db: Session = Depends(get_db)):
    drug = db.query(models.Drug).filter(models.Drug.trade_en.ilike(trade_en)).first()
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    return drug

@app.post("/api/check_interaction")
@app.post("/check_interaction")
def check_interaction(req: schemas.InteractionRequest):
    search_string = " ".join(req.drugs).lower()

    has_nsaid = bool(re.search(r'ibuprofen|diclofenac|ketoprofen|piroxicam|naproxen|brufen|cataflam|voltaren', search_string))
    has_aspirin = bool(re.search(r'aspirin|acetylsalicylic|asposid|jusprin', search_string))
    has_warfarin = bool(re.search(r'warfarin|marevan', search_string))
    has_nitrates = bool(re.search(r'nitrate|nitroglycerin|monomak|nitro', search_string))
    has_sildenafil = bool(re.search(r'sildenafil|viagra|tadalafil|cialis', search_string))

    alerts = []
    if has_nsaid and has_aspirin:
        alerts.append("⚠️ **تعارض شديد (NSAID + Aspirin):** زيادة خطر النزيف المعدي المعوي وتقرحات المعدة.")
    if (has_nsaid or has_aspirin) and has_warfarin:
        alerts.append("⚠️ **تعارض خطير (مضادات التخثر + مسكنات):** خطورة عالية لحدوث نزيف. يجب تجنب الاستخدام المشترك.")
    if has_nitrates and has_sildenafil:
        alerts.append("⚠️ **تعارض مميت (Nitrates + PDE5 inhibitors):** هبوط حاد وشديد في ضغط الدم قد يهدد الحياة.")

    return {"alerts": alerts}

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

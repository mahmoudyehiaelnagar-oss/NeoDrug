import re
import math
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from sqlalchemy.orm import Session
from sqlalchemy import or_

from . import models, schemas
from .database import engine, get_db

# Commented out create_all to prevent Read-Only filesystem crashes on Vercel
# models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Neo Drug API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
@app.get("/api")
@app.get("/api/")
def api_root():
    return {"message": "API is running perfectly on Vercel!"}

@app.get("/api/drugs", response_model=schemas.PaginatedDrugs)
@app.get("/drugs", response_model=schemas.PaginatedDrugs)
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
@app.get("/drugs/{trade_en}", response_model=schemas.DrugResponse)
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

# Serve Static files as a fallback
# We get the absolute path for Vercel deployment where the working directory is /var/task
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

@app.get("/{file_path:path}")
def serve_static(file_path: str):
    # Security check to prevent directory traversal
    full_path = os.path.abspath(os.path.join(PUBLIC_DIR, file_path))
    if not full_path.startswith(os.path.abspath(PUBLIC_DIR)):
        return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

    if os.path.isfile(full_path):
        return FileResponse(full_path)
    # Return index.html for unknown routes to support SPA/navigation
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

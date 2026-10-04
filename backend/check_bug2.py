from app.database import SessionLocal
from app import models, schemas
import time

db = SessionLocal()
drug = db.query(models.Drug).filter(models.Drug.trade_en.ilike("Abevemy")).first()
print("Found:", drug.trade_en)
print("Alternates object type:", type(drug.alternates))

try:
    response = schemas.DrugResponse.model_validate(drug)
    print("Validate success:", response.trade_en)
except Exception as e:
    print("Validate failed:", e)


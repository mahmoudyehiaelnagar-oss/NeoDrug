from app.database import SessionLocal
from app import models, schemas
import time
from fastapi.encoders import jsonable_encoder

db = SessionLocal()
drug = db.query(models.Drug).filter(models.Drug.trade_en.ilike("Abilaxine")).first()
response = schemas.DrugResponse.model_validate(drug)
encoded = jsonable_encoder(response)
print("Encoded:", encoded)

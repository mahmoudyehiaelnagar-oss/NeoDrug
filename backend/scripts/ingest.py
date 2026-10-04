import json
import os
import sys

# Add parent dir to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app import models

def run():
    print("Creating tables...")
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # Check if we already ingested
    if db.query(models.Drug).count() > 0:
        print("Data already exists in database. Aborting ingestion.")
        return

    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "drugs_db.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    print("Loading drugs_db.json...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Found {len(data)} items to ingest.")

    objects = []
    for item in data:
        # Some fields might not exist in every JSON object
        drug = models.Drug(
            trade_en=item.get('tradeEn'),
            trade_ar=item.get('tradeAr'),
            generic_en=item.get('genericEn'),
            generic_ar=item.get('genericAr'),
            form=item.get('form'),
            form_ar=item.get('formAr'),
            strength=item.get('strength'),
            cls=item.get('cls'),
            indications=item.get('indications'),
            dosage=item.get('dosage'),
            side_effects=item.get('sideEffects'),
            contraindications=item.get('contraindications'),
            pregnancy=item.get('pregnancy'),
            alternates=item.get('alternates', [])
        )
        objects.append(drug)

    print("Inserting into database...")
    # Bulk insert for speed
    db.bulk_save_objects(objects)
    db.commit()
    db.close()

    print("Ingestion complete.")

if __name__ == "__main__":
    run()

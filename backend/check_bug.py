from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    res = conn.execute(text("SELECT trade_en FROM drugs WHERE trade_en LIKE 'A-Viton'")).fetchall()
    print(res)

import os
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ORIGINAL_DB_PATH = os.path.join(BASE_DIR, "public", "drugs_database.db")

# If running on Vercel (Read-Only filesystem), copy the DB to /tmp which is writable
if os.getenv("VERCEL"):
    TMP_DB_PATH = "/tmp/drugs_database.db"
    # Copy only if it doesn't exist to speed up warm starts
    if not os.path.exists(TMP_DB_PATH):
        try:
            shutil.copy2(ORIGINAL_DB_PATH, TMP_DB_PATH)
        except Exception as e:
            print(f"Error copying DB to /tmp: {e}")
    DB_PATH = TMP_DB_PATH
else:
    DB_PATH = ORIGINAL_DB_PATH

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

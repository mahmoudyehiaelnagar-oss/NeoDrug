import os
import shutil
import fcntl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL_DB_PATH = os.path.join(BASE_DIR, "public", "drugs_database.db")

# If running on Vercel (Read-Only filesystem), copy the DB to /tmp which is writable
if os.getenv("VERCEL"):
    TMP_DB_PATH = "/tmp/drugs_database.db"
    LOCK_PATH = "/tmp/drugs_database.lock"
    # Use file locking to prevent concurrent copy attempts
    if not os.path.exists(TMP_DB_PATH):
        try:
            with open(LOCK_PATH, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                if not os.path.exists(TMP_DB_PATH):
                    shutil.copy2(ORIGINAL_DB_PATH, TMP_DB_PATH)
                    os.chmod(TMP_DB_PATH, 0o666)
                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            print(f"Error copying DB to /tmp: {e}")
    try:
        os.chmod(TMP_DB_PATH, 0o666)
    except Exception:
        pass
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

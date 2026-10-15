import os
import sys
import shutil
import fcntl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL_DB_PATH = os.path.join(BASE_DIR, "public", "drugs_database.db")
if not os.path.exists(ORIGINAL_DB_PATH) and getattr(sys, 'frozen', False):
    # PyInstaller bundle fallback
    BUNDLE_ROOT = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    ORIGINAL_DB_PATH = os.path.join(BUNDLE_ROOT, "backend", "public", "drugs_database.db")

# If running on Vercel / Lambda (Read-Only filesystem), copy the DB to /tmp which is writable
is_read_only_env = bool(
    os.getenv("VERCEL")
    or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
    or os.path.exists("/var/task")
)

if is_read_only_env:
    TMP_DB_PATH = "/tmp/drugs_database.db"
    LOCK_PATH = "/tmp/drugs_database.lock"

    candidate_sources = [
        ORIGINAL_DB_PATH,
        "/var/task/public/drugs_database.db",
        "/var/task/backend/public/drugs_database.db",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "drugs_database.db")
    ]
    actual_source = next((c for c in candidate_sources if os.path.exists(c)), ORIGINAL_DB_PATH)

    if not os.path.exists(TMP_DB_PATH) or os.path.getsize(TMP_DB_PATH) == 0:
        try:
            with open(LOCK_PATH, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                if not os.path.exists(TMP_DB_PATH) or os.path.getsize(TMP_DB_PATH) == 0:
                    shutil.copyfile(actual_source, TMP_DB_PATH)
                fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            print(f"Error copying DB to /tmp: {e}")
            try:
                shutil.copyfile(actual_source, TMP_DB_PATH)
            except Exception:
                pass
    try:
        os.chmod(TMP_DB_PATH, 0o777)
    except Exception:
        pass
    DB_PATH = TMP_DB_PATH
else:
    # Desktop Standalone Mode (macOS / Windows / Linux):
    # Store database in portable USB folder or user's permanent application data folder
    portable_dir = os.getenv("NEO_PORTABLE_DATA_DIR")
    if portable_dir and os.path.exists(portable_dir):
        data_dir = portable_dir
    elif sys.platform == "darwin":
        data_dir = os.path.expanduser("~/Library/Application Support/NeoDrug")
    elif sys.platform == "win32":
        data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "NeoDrug")
    else:
        data_dir = os.path.expanduser("~/.local/share/neodrug")

    os.makedirs(data_dir, exist_ok=True)
    USER_DB_PATH = os.path.join(data_dir, "drugs_database.db")
    if not os.path.exists(USER_DB_PATH) or os.path.getsize(USER_DB_PATH) == 0:
        if os.path.exists(ORIGINAL_DB_PATH):
            try:
                shutil.copyfile(ORIGINAL_DB_PATH, USER_DB_PATH)
            except Exception as e:
                print(f"Error copying initial DB to user data dir: {e}")
    try:
        os.chmod(USER_DB_PATH, 0o666)
    except Exception:
        pass
    DB_PATH = USER_DB_PATH

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

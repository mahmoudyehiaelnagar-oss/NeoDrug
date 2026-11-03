import os
import sys
import shutil
import urllib.parse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL_DB_PATH = os.path.join(BASE_DIR, "public", "drugs_database.db")

if not os.path.exists(ORIGINAL_DB_PATH) and getattr(sys, "frozen", False):
    # PyInstaller bundle fallback
    BUNDLE_ROOT = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    ORIGINAL_DB_PATH = os.path.join(BUNDLE_ROOT, "backend", "public", "drugs_database.db")


def is_serverless() -> bool:
    """True when running on a read-only / ephemeral filesystem (Vercel, Lambda)."""
    return bool(
        os.getenv("VERCEL")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.path.exists("/var/task")
    )


def _local_data_dir() -> str:
    """Writable, permanent directory for the desktop/portable builds."""
    portable_dir = os.getenv("NEO_PORTABLE_DATA_DIR")
    if portable_dir:
        try:
            os.makedirs(portable_dir, exist_ok=True)
            return portable_dir
        except Exception:
            pass

    if sys.platform == "darwin":
        data_dir = os.path.expanduser("~/Library/Application Support/NeoDrug")
    elif sys.platform == "win32":
        data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "NeoDrug")
    else:
        data_dir = os.path.expanduser("~/.local/share/neodrug")

    try:
        os.makedirs(data_dir, exist_ok=True)
    except Exception:
        # Read-only filesystem (serverless): secrets are ephemeral anyway.
        data_dir = "/tmp"
    return data_dir


# ---------------------------------------------------------------------------
# Database selection
#  1. DATABASE_URL (Postgres/Neon/Supabase) -> persistent, serverless-safe
#  2. Vercel/Lambda without DATABASE_URL -> SQLite copy in /tmp (NOT persistent)
#  3. Desktop / portable -> SQLite in a permanent user folder
# ---------------------------------------------------------------------------
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()


def _normalize_database_url(url: str) -> str:
    """Make sure Postgres URLs use the pg8000 driver (already a dependency)."""
    for prefix in (
        "postgres://",
        "postgresql://",
        "postgresql+psycopg2://",
        "postgresql+psycopg://",
    ):
        if url.startswith(prefix):
            return "postgresql+pg8000://" + url[len(prefix):]
    return url


def _prepare_postgres_url(url: str):
    """
    Translate libpq-style query parameters into pg8000 connect arguments.

    pg8000 does not understand ``sslmode``/``channel_binding``; passing them through
    would raise a TypeError on connect. SSL is configured explicitly instead.
    """
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    sslmode = (query.pop("sslmode", None) or "").lower()
    query.pop("channel_binding", None)

    connect_args = {}
    if sslmode:
        import ssl

        context = ssl.create_default_context()
        if sslmode in ("require", "prefer", "allow"):
            # Encrypted transport without CA verification (common for managed DBs).
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        connect_args["ssl_context"] = context

    clean_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
    return clean_url, connect_args


if DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = _normalize_database_url(DATABASE_URL)
    DATA_DIR = _local_data_dir()  # still used to persist the local JWT/admin secrets
    DB_PATH = ""
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            connect_args={"check_same_thread": False, "timeout": 30},
            future=True,
        )
    else:
        SQLALCHEMY_DATABASE_URL, _pg_connect_args = _prepare_postgres_url(SQLALCHEMY_DATABASE_URL)
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=280,
            pool_size=5,
            max_overflow=5,
            connect_args=_pg_connect_args,
            future=True,
        )
    PERSISTENT_STORAGE = True
else:
    PERSISTENT_STORAGE = not is_serverless()

    if is_serverless():
        # Ephemeral fallback: writable but wiped on every cold start.
        DATA_DIR = "/tmp"
        DB_PATH = "/tmp/drugs_database.db"
        print(
            "WARNING: DATABASE_URL is not set. Falling back to SQLite in /tmp on a "
            "serverless platform: users, usage counters and promo codes will NOT persist. "
            "Set DATABASE_URL (Postgres) for production."
        )
    else:
        DATA_DIR = _local_data_dir()
        DB_PATH = os.path.join(DATA_DIR, "drugs_database.db")

    # Import fcntl lazily: it does not exist on Windows.
    def _copy_sqlite_db(source: str, target: str) -> None:
        if not os.path.exists(source):
            print(f"WARNING: source database not found at {source}")
            return
        try:
            import fcntl  # POSIX only

            lock_path = target + ".lock"
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                try:
                    if not os.path.exists(target) or os.path.getsize(target) == 0:
                        shutil.copyfile(source, target)
                finally:
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
        except ImportError:
            # Windows: no flock, plain copy
            if not os.path.exists(target) or os.path.getsize(target) == 0:
                shutil.copyfile(source, target)
        except Exception as exc:
            print(f"Error copying DB: {exc}")
            try:
                if not os.path.exists(target) or os.path.getsize(target) == 0:
                    shutil.copyfile(source, target)
            except Exception:
                pass

    if is_serverless():
        candidate_sources = [
            ORIGINAL_DB_PATH,
            "/var/task/public/drugs_database.db",
            "/var/task/backend/public/drugs_database.db",
            os.path.join(BASE_DIR, "public", "drugs_database.db"),
        ]
        actual_source = next((c for c in candidate_sources if os.path.exists(c)), ORIGINAL_DB_PATH)
        _copy_sqlite_db(actual_source, DB_PATH)
    else:
        if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
            _copy_sqlite_db(ORIGINAL_DB_PATH, DB_PATH)

    try:
        os.chmod(DB_PATH, 0o666)
    except Exception:
        pass

    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

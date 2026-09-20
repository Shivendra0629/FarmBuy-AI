import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1. Check for external DATABASE_URL (e.g. Render PostgreSQL, Supabase, Neon, or cloud DB)
ENV_DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Check for persistent storage directory (e.g. Render Persistent Disk mounted at /data or /var/data)
DATA_DIR = os.getenv("DATA_DIR") or os.getenv("PERSISTENT_DATA_DIR")

IS_RENDER = bool(os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"))

if ENV_DATABASE_URL and ENV_DATABASE_URL.strip():
    # Render provides postgres:// urls, but SQLAlchemy 2.0+ requires postgresql://
    clean_url = ENV_DATABASE_URL.strip()
    if clean_url.startswith("postgres://"):
        DATABASE_URL = clean_url.replace("postgres://", "postgresql://", 1)
    else:
        DATABASE_URL = clean_url

    IS_SQLITE = False
    DATABASE_ENGINE = "postgresql"
    IS_PERSISTENT = True
    STORAGE_TYPE = "Render PostgreSQL (Persistent Cloud Database)"

    pg_connect_args = {}
    if "sslmode" not in DATABASE_URL:
        # 'prefer' enables SSL if supported by server (external host), or falls back to plain (internal)
        pg_connect_args["sslmode"] = "prefer"

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=pg_connect_args
    )
else:
    IS_SQLITE = True
    DATABASE_ENGINE = "sqlite"

    if DATA_DIR and os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        DB_PATH = os.path.join(DATA_DIR, "agriconnect.db")
        IS_PERSISTENT = True
        STORAGE_TYPE = f"SQLite on Persistent Disk ({DATA_DIR})"
    else:
        DB_PATH = os.path.join(BASE_DIR, "agriconnect.db")
        if IS_RENDER:
            IS_PERSISTENT = False
            STORAGE_TYPE = "Render Ephemeral Disk (Non-Persistent: data will reset on sleep/restart. Set DATABASE_URL in Render Dashboard!)"
        else:
            IS_PERSISTENT = True
            STORAGE_TYPE = "Local SQLite (Persistent on Local Hard Drive)"

    DATABASE_URL = f"sqlite:///{DB_PATH.replace(os.sep, '/')}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

    # Enable SQLite WAL (Write-Ahead Logging) and Normal synchronous mode
    # WAL prevents concurrency locks and guarantees atomic persistence to disk
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception:
            pass

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
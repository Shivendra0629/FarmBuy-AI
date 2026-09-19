import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1. Check for external DATABASE_URL (e.g. Render PostgreSQL or hosted DB)
ENV_DATABASE_URL = os.getenv("DATABASE_URL")

# 2. Check for persistent storage directory (e.g. Render Persistent Disk mounted at /data or /var/data)
DATA_DIR = os.getenv("DATA_DIR") or os.getenv("PERSISTENT_DATA_DIR")

if ENV_DATABASE_URL:
    # Render provides postgres:// urls, but SQLAlchemy 2.0 requires postgresql://
    if ENV_DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = ENV_DATABASE_URL.replace("postgres://", "postgresql://", 1)
    else:
        DATABASE_URL = ENV_DATABASE_URL

    IS_SQLITE = False
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300
    )
else:
    IS_SQLITE = True
    if DATA_DIR:
        os.makedirs(DATA_DIR, exist_ok=True)
        DB_PATH = os.path.join(DATA_DIR, "agriconnect.db")
    else:
        DB_PATH = os.path.join(BASE_DIR, "agriconnect.db")

    DATABASE_URL = f"sqlite:///{DB_PATH.replace(os.sep, '/')}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

    # Enable SQLite WAL (Write-Ahead Logging) and Normal synchronous mode
    # WAL prevents concurrency locks and guarantees instant persistence to disk
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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from datetime import datetime
from sqlalchemy import text

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .database import Base, engine, SessionLocal, IS_SQLITE, DATABASE_ENGINE, IS_PERSISTENT, STORAGE_TYPE
from . import models
from .models import Product, Admin, Farmer, Buyer, Supply, Order
from .security import hash_password
from .routers import matching, supply_intelligence, auth, admin


def init_db_defaults():
    """
    Idempotently initialize database tables, baseline commodities, and Super Admin.
    GUARANTEE: NEVER deletes, resets, or overwrites any existing farmer, buyer,
    supply, order, or admin data.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Baseline agricultural commodities (seeded ONLY if products table is empty)
        if db.query(Product).count() == 0:
            products_data = [
                {"name": "Tomato", "category": "Vegetable", "unit": "kg", "mandi_benchmark_price": 22.0, "perishability_days": 7},
                {"name": "Potato (Jyoti)", "category": "Tuber", "unit": "kg", "mandi_benchmark_price": 16.5, "perishability_days": 45},
                {"name": "Red Onion", "category": "Allium", "unit": "kg", "mandi_benchmark_price": 28.0, "perishability_days": 25},
                {"name": "Green Chilli", "category": "Spice", "unit": "kg", "mandi_benchmark_price": 54.0, "perishability_days": 10},
                {"name": "Cauliflower", "category": "Vegetable", "unit": "kg", "mandi_benchmark_price": 18.0, "perishability_days": 8},
            ]
            for pdata in products_data:
                db.add(Product(**pdata))
            db.commit()

        # 2. Super Admin (Owner) Account:
        # Persisted directly in the database. Seeded ONLY if no OWNER account exists.
        owner_in_db = db.query(Admin).filter(Admin.role == "OWNER").first()
        if not owner_in_db:
            owner_id = os.getenv("OWNER_ADMIN_ID", "Sm_0629")
            owner_pwd = os.getenv("OWNER_ADMIN_PASSWORD", "9973868328")
            owner_admin = Admin(
                id=999,
                name="Super Admin",
                admin_user_id=owner_id,
                password_hash=hash_password(owner_pwd),
                role="OWNER",
                is_active=1
            )
            db.add(owner_admin)
            db.commit()
            print(f"[FarmBuy AI] Root Super Admin '{owner_id}' initialized in database.")
        else:
            # Preserve existing owner credentials untouched
            pass

    except Exception as e:
        print(f"[FarmBuy AI] DB initialization warning: {e}")
        db.rollback()
    finally:
        db.close()


# Run initialization on module load
init_db_defaults()

app = FastAPI(
    title="FarmBuy AI",
    description="AI-Powered Farm-to-Buyer Supply Intelligence Platform",
    version="2.0.0"
)


# Prevent browser & proxy HTTP GET caching of dynamic API data
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheMiddleware)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event hook for cloud deployments (e.g. Render)
@app.on_event("startup")
def on_startup():
    init_db_defaults()


# Include REST Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(supply_intelligence.router)
app.include_router(matching.router)


@app.get("/health")
def health_check():
    """
    Comprehensive health and database persistence diagnostics.
    Tests live database connection and reports exact storage type and live counts.
    """
    db = SessionLocal()
    db_status = "connected"
    counts = {}
    try:
        db.execute(text("SELECT 1"))
        counts = {
            "farmers": db.query(Farmer).count(),
            "buyers": db.query(Buyer).count(),
            "supplies": db.query(Supply).count(),
            "orders": db.query(Order).count(),
            "team_admins": db.query(Admin).filter(Admin.role == "ADMIN").count(),
            "super_admins": db.query(Admin).filter(Admin.role == "OWNER").count(),
            "commodities": db.query(Product).count()
        }
    except Exception as err:
        db_status = f"error: {str(err)}"
    finally:
        db.close()

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "platform": "FarmBuy AI",
        "version": "2.0.0",
        "database": db_status,
        "database_engine": DATABASE_ENGINE,
        "is_persistent": IS_PERSISTENT,
        "storage_type": STORAGE_TYPE,
        "records": counts,
        "server_time": datetime.utcnow().isoformat() + "Z"
    }


# Frontend static files path
frontend_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "1_Frontend")
)

if os.path.exists(frontend_dir):
    # Mount frontend static directory with html=True so / serves index.html
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {
            "message": "FarmBuy AI Backend running. Frontend directory not found.",
            "docs": "/docs"
        }
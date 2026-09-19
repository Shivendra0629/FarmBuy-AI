from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .database import Base, engine, SessionLocal, IS_SQLITE
from . import models
from .models import Product, Admin
from .security import hash_password, get_owner_credentials
from .routers import matching, supply_intelligence, auth, admin


def init_db_defaults():
    """Idempotently initialize database tables, baseline commodities, and Super Admin account."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Baseline agricultural commodities (if empty)
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

        # 2. Fix admin IDs: Ensure Super Admin does not occupy id=1 in admins table,
        # and re-index regular team admins so they start strictly from id=1.
        # Super Admin is the platform root owner managed via owner_config.json / env vars.
        owner_in_db = db.query(Admin).filter(Admin.role == "OWNER").first()
        if owner_in_db:
            db.delete(owner_in_db)
            db.commit()

        # Re-index existing regular admins starting from id=1
        regular_admins = db.query(Admin).filter(Admin.role == "ADMIN").order_by(Admin.created_at.asc(), Admin.id.asc()).all()
        reindexed = False
        for target_id, adm in enumerate(regular_admins, start=1):
            if adm.id != target_id:
                adm.id = target_id
                reindexed = True
        if reindexed:
            db.commit()
    except Exception as e:
        print(f"[AgriConnect AI] DB initialization warning: {e}")
        db.rollback()
    finally:
        db.close()


# Run initialization
init_db_defaults()

app = FastAPI(
    title="FarmBuy AI ",
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
    return {
        "status": "healthy",
        "platform": "AgriConnect AI",
        "version": "2.0.0",
        "database": "connected"
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
            "message": "AgriConnect AI Backend running. Frontend directory not found.",
            "docs": "/docs"
        }
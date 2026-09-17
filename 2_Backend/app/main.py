from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .database import Base, engine
from . import models
from .routers import matching, supply_intelligence, auth

# Ensure tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FarmBuy AI ",
    description="AI-Powered Farm-to-Buyer Supply Intelligence Platform",
    version="2.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST Routers
app.include_router(auth.router)
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
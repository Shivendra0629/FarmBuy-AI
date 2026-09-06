from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import Product
from ..services.matching_service import match_supply
from ..services.price_service import get_price_insight
from ..services.route_service import optimize_route

router = APIRouter(
    prefix="/matching",
    tags=["Legacy Matching"]
)


@router.get("/")
def find_supply(
    product_id: int = Query(..., gt=0, description="Product ID (must exist)"),
    required_quantity: float = Query(..., gt=0, description="Required quantity in kg (must be > 0)"),
    strategy: str = Query("balanced", description="Matching strategy ('balanced', 'cost', 'distance')"),
    buyer_lat: float = Query(22.5726, ge=-90.0, le=90.0),
    buyer_lon: float = Query(88.3639, ge=-180.0, le=180.0),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return match_supply(
        db=db,
        product_id=product_id,
        required_quantity=required_quantity,
        buyer_lat=buyer_lat,
        buyer_lon=buyer_lon,
        strategy=strategy
    )


@router.get("/price-insight")
def price_insight(
    product_id: int = Query(..., gt=0, description="Product ID (must exist)"),
    required_quantity: float = Query(1000.0, gt=0, description="Required quantity in kg (must be > 0)"),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return get_price_insight(
        db=db,
        product_id=product_id,
        required_quantity=required_quantity
    )


@router.get("/route")
def collection_route(
    farmer_ids: str = Query(..., description="Comma-separated farmer IDs"),
    buyer_lat: float = Query(22.5726, ge=-90.0, le=90.0),
    buyer_lon: float = Query(88.3639, ge=-180.0, le=180.0),
    buyer_name: str = Query("Kolkata Wholesale Depot"),
    product_id: Optional[int] = Query(None, gt=0, description="Optional product ID to populate collection quantities"),
    db: Session = Depends(get_db)
):
    ids = [
        int(farmer_id.strip())
        for farmer_id in farmer_ids.split(",")
        if farmer_id.strip().isdigit()
    ]

    if not ids:
        raise HTTPException(status_code=400, detail="farmer_ids list cannot be empty")

    return optimize_route(
        db=db,
        farmer_ids=ids,
        buyer_name=buyer_name,
        buyer_lat=buyer_lat,
        buyer_lon=buyer_lon,
        product_id=product_id
    )
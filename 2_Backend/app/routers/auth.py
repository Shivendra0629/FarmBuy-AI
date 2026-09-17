from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Optional
import random

from ..database import get_db
from ..models import Farmer, Buyer, Product, Supply
from ..schemas import (
    FarmerLoginRegisterRequest,
    BuyerLoginRegisterRequest,
    FarmerAddSupplyRequest,
    AuthResponse,
    BuyerOut,
    FarmerOut
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Farmer & Buyer Authentication"]
)

# Approximate central coordinates for Indian states / West Bengal hubs
STATE_COORDINATES = {
    "west bengal": (22.8124, 88.2312),
    "uttar pradesh": (26.8467, 80.9462),
    "punjab": (30.9010, 75.8573),
    "maharashtra": (19.7515, 75.7139),
    "bihar": (25.0961, 85.3131),
    "haryana": (29.0588, 76.0856),
    "madhya pradesh": (22.9734, 78.6569),
    "rajasthan": (27.0238, 74.2179),
    "gujarat": (22.2587, 71.1924),
    "andhra pradesh": (15.9129, 79.7400),
    "tamil nadu": (11.1271, 78.6569),
    "karnataka": (15.3173, 75.7139),
    "delhi": (28.6139, 77.2090),
}


def estimate_coordinates(state: str, pincode: str):
    """Estimate realistic GPS coordinates based on state with local jitter for map display."""
    st_key = (state or "").strip().lower()
    base_lat, base_lon = STATE_COORDINATES.get(st_key, (22.8124, 88.2312))
    
    # Hash pincode to give reproducible unique coordinates for each farmer in the district
    try:
        p_num = int(pincode.strip()[-4:])
        lat_offset = ((p_num % 100) - 50) * 0.008
        lon_offset = (((p_num // 10) % 100) - 50) * 0.008
    except Exception:
        lat_offset = (random.random() - 0.5) * 0.2
        lon_offset = (random.random() - 0.5) * 0.2
        
    return round(base_lat + lat_offset, 4), round(base_lon + lon_offset, 4)


@router.post("/farmer", response_model=AuthResponse)
def register_or_login_farmer(payload: FarmerLoginRegisterRequest, db: Session = Depends(get_db)):
    """
    Farmer registration and login:
    Stores/updates farmer details (Name, Address, Phone Number, Pincode, State)
    and registers their commodities with Quantity (kg) and Price per kg in the database.
    """
    clean_phone = payload.phone_number.strip()
    clean_name = payload.name.strip()
    clean_commodity = payload.commodity.strip()
    clean_address = payload.address.strip()
    clean_state = payload.state.strip()
    clean_pincode = payload.pincode.strip()

    if not clean_phone or not clean_name:
        raise HTTPException(status_code=400, detail="Name and Phone Number are required.")

    # 1. Check if farmer already exists by phone number or name
    farmer = db.query(Farmer).filter(
        (Farmer.contact == clean_phone) | (Farmer.name == clean_name)
    ).first()

    lat, lon = estimate_coordinates(clean_state, clean_pincode)

    if not farmer:
        # Create new Farmer
        farmer = Farmer(
            name=clean_name,
            address=clean_address,
            location=f"{clean_address}, {clean_state} ({clean_pincode})",
            contact=clean_phone,
            pincode=clean_pincode,
            state=clean_state,
            latitude=lat,
            longitude=lon,
            rating=round(random.uniform(4.7, 5.0), 1),
            farm_size_acres=round(random.uniform(3.0, 10.0), 1)
        )
        db.add(farmer)
        db.commit()
        db.refresh(farmer)
    else:
        # Update existing farmer info
        farmer.address = clean_address
        farmer.pincode = clean_pincode
        farmer.state = clean_state
        farmer.location = f"{clean_address}, {clean_state} ({clean_pincode})"
        farmer.latitude = lat
        farmer.longitude = lon
        db.commit()
        db.refresh(farmer)

    # 2. Check or Create Product / Commodity
    product = db.query(Product).filter(Product.name.ilike(clean_commodity)).first()
    if not product:
        # Create new product record for this commodity
        product = Product(
            name=clean_commodity.capitalize(),
            category="Agricultural Produce",
            unit="kg",
            mandi_benchmark_price=round(payload.price_per_kg * 1.05, 1),
            perishability_days=14
        )
        db.add(product)
        db.commit()
        db.refresh(product)

    # 3. Add or Update Farmer's Supply for this Commodity
    existing_supply = db.query(Supply).filter(
        Supply.farmer_id == farmer.id,
        Supply.product_id == product.id
    ).first()

    today = date.today()
    if existing_supply:
        existing_supply.quantity += payload.quantity_kg
        existing_supply.expected_price = payload.price_per_kg
        existing_supply.available_date = today
    else:
        new_supply = Supply(
            farmer_id=farmer.id,
            product_id=product.id,
            quantity=payload.quantity_kg,
            expected_price=payload.price_per_kg,
            quality_grade="Grade A",
            available_date=today,
            harvest_date=today
        )
        db.add(new_supply)

    db.commit()

    return {
        "status": "success",
        "user_type": "farmer",
        "user_id": farmer.id,
        "name": farmer.name,
        "phone_number": farmer.contact,
        "address": clean_address,
        "pincode": clean_pincode,
        "state": clean_state,
        "message": f"Welcome, Farmer {farmer.name}! Your produce ({product.name}: {payload.quantity_kg:,.0f} kg @ ₹{payload.price_per_kg}/kg) is successfully registered in the platform database.",
        "details": {
            "farmer_id": farmer.id,
            "product_id": product.id,
            "product_name": product.name,
            "quantity_kg": payload.quantity_kg,
            "price_per_kg": payload.price_per_kg,
            "mandi_benchmark": product.mandi_benchmark_price,
            "location": farmer.location
        }
    }


@router.post("/buyer", response_model=AuthResponse)
def register_or_login_buyer(payload: BuyerLoginRegisterRequest, db: Session = Depends(get_db)):
    """
    Buyer registration and login:
    Stores buyer details (Name, Address, Phone Number, Pincode, State) in the database
    and authorizes access to the full crop intelligence, demand forecasts, and farm matching.
    """
    clean_phone = payload.phone_number.strip()
    clean_name = payload.name.strip()
    clean_address = payload.address.strip()
    clean_city = (payload.city or "").strip()
    clean_pincode = payload.pincode.strip()
    clean_state = payload.state.strip()

    if not clean_phone or not clean_name:
        raise HTTPException(status_code=400, detail="Name and Phone Number are required.")

    # Find or create Buyer
    buyer = db.query(Buyer).filter(
        (Buyer.phone_number == clean_phone) | (Buyer.name == clean_name)
    ).first()

    if not buyer:
        buyer = Buyer(
            name=clean_name,
            address=clean_address,
            city=clean_city,
            phone_number=clean_phone,
            pincode=clean_pincode,
            state=clean_state
        )
        db.add(buyer)
        db.commit()
        db.refresh(buyer)
    else:
        # Update buyer info
        buyer.address = clean_address
        buyer.city = clean_city
        buyer.pincode = clean_pincode
        buyer.state = clean_state
        db.commit()
        db.refresh(buyer)

    full_loc = f"{buyer.address}"
    if buyer.city:
        full_loc += f", {buyer.city}"
    full_loc += f", {buyer.state} ({buyer.pincode})"

    return {
        "status": "success",
        "user_type": "buyer",
        "user_id": buyer.id,
        "name": buyer.name,
        "phone_number": buyer.phone_number,
        "address": buyer.address,
        "pincode": buyer.pincode,
        "state": buyer.state,
        "message": f"Welcome, {buyer.name}! Access granted to live agricultural crop supplies, predictive demand intelligence, and optimized farm collection routes.",
        "details": {
            "buyer_id": buyer.id,
            "city": buyer.city,
            "hub_location": full_loc
        }
    }


@router.get("/farmer/{farmer_id}/supplies")
def get_farmer_supplies(farmer_id: int, db: Session = Depends(get_db)):
    """Get all produce commodities listed by a specific farmer."""
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    supplies = (
        db.query(Supply, Product)
        .join(Product, Supply.product_id == Product.id)
        .filter(Supply.farmer_id == farmer_id)
        .all()
    )

    result = []
    total_val = 0.0
    for s, p in supplies:
        subtotal = round(s.quantity * s.expected_price, 2)
        total_val += subtotal
        result.append({
            "supply_id": s.id,
            "product_id": p.id,
            "product_name": p.name,
            "category": p.category,
            "quantity_kg": s.quantity,
            "expected_price": s.expected_price,
            "mandi_benchmark": p.mandi_benchmark_price,
            "quality_grade": s.quality_grade,
            "subtotal_value": subtotal
        })

    return {
        "farmer_id": farmer.id,
        "name": farmer.name,
        "location": farmer.location,
        "contact": farmer.contact,
        "rating": farmer.rating,
        "total_inventory_value": round(total_val, 2),
        "supplies": result
    }


@router.post("/farmer/add-supply")
def add_farmer_supply(payload: FarmerAddSupplyRequest, db: Session = Depends(get_db)):
    """Allows an active farmer to add an additional commodity to their catalog."""
    farmer = db.query(Farmer).filter(Farmer.id == payload.farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    clean_comm = payload.commodity.strip()
    product = db.query(Product).filter(Product.name.ilike(clean_comm)).first()
    if not product:
        product = Product(
            name=clean_comm.capitalize(),
            category="Agricultural Produce",
            unit="kg",
            mandi_benchmark_price=round(payload.price_per_kg * 1.05, 1),
            perishability_days=14
        )
        db.add(product)
        db.commit()
        db.refresh(product)

    today = date.today()
    supply = db.query(Supply).filter(
        Supply.farmer_id == farmer.id,
        Supply.product_id == product.id
    ).first()

    if supply:
        supply.quantity += payload.quantity_kg
        supply.expected_price = payload.price_per_kg
    else:
        supply = Supply(
            farmer_id=farmer.id,
            product_id=product.id,
            quantity=payload.quantity_kg,
            expected_price=payload.price_per_kg,
            quality_grade=payload.quality_grade,
            available_date=today,
            harvest_date=today
        )
        db.add(supply)

    db.commit()

    return {
        "status": "success",
        "message": f"Added {payload.quantity_kg:,.0f} kg of {product.name} to {farmer.name}'s active catalog."
    }


@router.get("/buyers", response_model=List[BuyerOut])
def get_all_buyers(db: Session = Depends(get_db)):
    """List all registered buyers in the system."""
    return db.query(Buyer).order_by(Buyer.created_at.desc()).all()

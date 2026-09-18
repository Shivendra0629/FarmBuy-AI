from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Optional
import random

from ..database import get_db
from ..models import Farmer, Buyer, Product, Supply, Order, OrderItem, Demand, Admin
from ..schemas import (
    FarmerLoginRegisterRequest,
    FarmerLoginRequest,
    BuyerLoginRegisterRequest,
    BuyerLoginRequest,
    AdminLoginRequest,
    FarmerAddSupplyRequest,
    FarmerUpdateSupplyRequest,
    FarmerClearStockRequest,
    AuthResponse,
    BuyerOut,
    FarmerOut
)
from ..security import (
    verify_password,
    create_access_token,
    OWNER_ADMIN_ID,
    OWNER_ADMIN_PASSWORD
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Farmer, Buyer & Admin Authentication"]
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


def _register_farmer_record(payload: FarmerLoginRegisterRequest, db: Session):
    clean_phone = payload.phone_number.strip()
    clean_name = payload.name.strip()
    clean_commodity = (payload.commodity or "").strip()
    clean_address = (payload.address or "").strip()
    clean_state = (payload.state or "West Bengal").strip()
    clean_pincode = (payload.pincode or "").strip()

    if not clean_phone or not clean_name:
        raise HTTPException(status_code=400, detail="Name and Phone Number are required.")

    farmer = db.query(Farmer).filter(
        (Farmer.contact == clean_phone) | (Farmer.name == clean_name)
    ).first()

    lat, lon = estimate_coordinates(clean_state, clean_pincode)

    if not farmer:
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
        farmer.address = clean_address
        farmer.pincode = clean_pincode
        farmer.state = clean_state
        farmer.location = f"{clean_address}, {clean_state} ({clean_pincode})"
        farmer.latitude = lat
        farmer.longitude = lon
        farmer.contact = clean_phone
        db.commit()
        db.refresh(farmer)

    product = None
    if clean_commodity:
        product = db.query(Product).filter(Product.name.ilike(clean_commodity)).first()
        if not product:
            product = Product(
                name=clean_commodity.capitalize(),
                category="Agricultural Produce",
                unit="kg",
                mandi_benchmark_price=round(float(payload.price_per_kg or 20.0) * 1.05, 1),
                perishability_days=14
            )
            db.add(product)
            db.commit()
            db.refresh(product)

        existing_supply = db.query(Supply).filter(
            Supply.farmer_id == farmer.id,
            Supply.product_id == product.id
        ).first()

        today = date.today()
        qty = float(payload.quantity_kg or 1000)
        price = float(payload.price_per_kg or 20)
        if existing_supply:
            existing_supply.quantity += qty
            if existing_supply.initial_quantity is None:
                existing_supply.initial_quantity = existing_supply.quantity
            else:
                existing_supply.initial_quantity += qty
            existing_supply.expected_price = price
            existing_supply.available_date = today
        else:
            new_supply = Supply(
                farmer_id=farmer.id,
                product_id=product.id,
                quantity=qty,
                cleared_quantity=0.0,
                initial_quantity=qty,
                expected_price=price,
                quality_grade="Grade A",
                available_date=today,
                harvest_date=today
            )
            db.add(new_supply)

        db.commit()

    token = create_access_token({
        "sub": str(farmer.id),
        "user_id": farmer.id,
        "role": "FARMER",
        "name": farmer.name,
        "phone": farmer.contact
    })

    return farmer, product, token


@router.post("/farmer/register", response_model=AuthResponse)
def register_farmer(payload: FarmerLoginRegisterRequest, db: Session = Depends(get_db)):
    """
    Farmer registration:
    Saves the farmer's complete registration details in the database and generates a unique farmer ID.
    Shows confirmation: 'Registration successful. You can now login.'
    """
    farmer, product, token = _register_farmer_record(payload, db)
    return {
        "status": "success",
        "user_type": "farmer",
        "role": "FARMER",
        "user_id": farmer.id,
        "name": farmer.name,
        "phone_number": farmer.contact,
        "address": farmer.address or "",
        "pincode": farmer.pincode or "",
        "state": farmer.state or "",
        "access_token": token,
        "message": "Registration successful. You can now login.",
        "details": {
            "farmer_id": farmer.id,
            "product_id": product.id if product else None,
            "product_name": product.name if product else None,
            "location": farmer.location
        }
    }


@router.post("/farmer/login", response_model=AuthResponse)
def login_farmer(payload: FarmerLoginRequest, db: Session = Depends(get_db)):
    """
    Farmer login:
    Verifies name and phone number against the database.
    Loads that specific farmer's session, profile, and data.
    """
    clean_name = payload.name.strip()
    clean_phone = payload.phone_number.strip()

    farmer = db.query(Farmer).filter(
        Farmer.name.ilike(clean_name),
        Farmer.contact == clean_phone
    ).first()

    if not farmer:
        raise HTTPException(
            status_code=401,
            detail="Farmer not found. Please check your name and phone number or register first."
        )

    token = create_access_token({
        "sub": str(farmer.id),
        "user_id": farmer.id,
        "role": "FARMER",
        "name": farmer.name,
        "phone": farmer.contact
    })

    return {
        "status": "success",
        "user_type": "farmer",
        "role": "FARMER",
        "user_id": farmer.id,
        "name": farmer.name,
        "phone_number": farmer.contact,
        "address": farmer.address or "",
        "pincode": farmer.pincode or "",
        "state": farmer.state or "",
        "access_token": token,
        "message": f"Welcome back, Farmer {farmer.name}! Login successful.",
        "details": {
            "farmer_id": farmer.id,
            "location": farmer.location
        }
    }


@router.post("/farmer", response_model=AuthResponse)
def register_or_login_farmer(payload: FarmerLoginRegisterRequest, db: Session = Depends(get_db)):
    """Legacy unified farmer registration/login route maintained for compatibility."""
    farmer, product, token = _register_farmer_record(payload, db)
    return {
        "status": "success",
        "user_type": "farmer",
        "role": "FARMER",
        "user_id": farmer.id,
        "name": farmer.name,
        "phone_number": farmer.contact,
        "address": farmer.address or "",
        "pincode": farmer.pincode or "",
        "state": farmer.state or "",
        "access_token": token,
        "message": f"Welcome, Farmer {farmer.name}! Produce registered successfully.",
        "details": {
            "farmer_id": farmer.id,
            "product_id": product.id if product else None,
            "product_name": product.name if product else None,
            "location": farmer.location
        }
    }


def _register_buyer_record(payload: BuyerLoginRegisterRequest, db: Session):
    clean_phone = payload.phone_number.strip()
    clean_name = payload.name.strip()
    clean_address = payload.address.strip()
    clean_city = (payload.city or "").strip()
    clean_pincode = payload.pincode.strip()
    clean_state = payload.state.strip()

    if not clean_phone or not clean_name:
        raise HTTPException(status_code=400, detail="Name and Phone Number are required.")

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
        buyer.address = clean_address
        buyer.city = clean_city
        buyer.pincode = clean_pincode
        buyer.state = clean_state
        buyer.phone_number = clean_phone
        db.commit()
        db.refresh(buyer)

    token = create_access_token({
        "sub": str(buyer.id),
        "user_id": buyer.id,
        "role": "BUYER",
        "name": buyer.name,
        "phone": buyer.phone_number
    })

    return buyer, token


@router.post("/buyer/register", response_model=AuthResponse)
def register_buyer(payload: BuyerLoginRegisterRequest, db: Session = Depends(get_db)):
    """
    Buyer registration:
    Saves buyer details permanently in the database and generates a unique buyer ID.
    Shows confirmation: 'Registration successful. You can now login.'
    """
    buyer, token = _register_buyer_record(payload, db)
    return {
        "status": "success",
        "user_type": "buyer",
        "role": "BUYER",
        "user_id": buyer.id,
        "name": buyer.name,
        "phone_number": buyer.phone_number,
        "address": buyer.address,
        "pincode": buyer.pincode,
        "state": buyer.state,
        "access_token": token,
        "message": "Registration successful. You can now login.",
        "details": {
            "buyer_id": buyer.id,
            "city": buyer.city
        }
    }


@router.post("/buyer/login", response_model=AuthResponse)
def login_buyer(payload: BuyerLoginRequest, db: Session = Depends(get_db)):
    """
    Buyer login:
    Verifies name and phone number against the database.
    Loads buyer-specific information and orders.
    """
    clean_name = payload.name.strip()
    clean_phone = payload.phone_number.strip()

    buyer = db.query(Buyer).filter(
        Buyer.name.ilike(clean_name),
        Buyer.phone_number == clean_phone
    ).first()

    if not buyer:
        raise HTTPException(
            status_code=401,
            detail="Buyer not found. Please check your name and phone number or register first."
        )

    token = create_access_token({
        "sub": str(buyer.id),
        "user_id": buyer.id,
        "role": "BUYER",
        "name": buyer.name,
        "phone": buyer.phone_number
    })

    return {
        "status": "success",
        "user_type": "buyer",
        "role": "BUYER",
        "user_id": buyer.id,
        "name": buyer.name,
        "phone_number": buyer.phone_number,
        "address": buyer.address,
        "pincode": buyer.pincode,
        "state": buyer.state,
        "access_token": token,
        "message": f"Welcome back, {buyer.name}! Login successful.",
        "details": {
            "buyer_id": buyer.id,
            "city": buyer.city
        }
    }


@router.post("/buyer", response_model=AuthResponse)
def register_or_login_buyer(payload: BuyerLoginRegisterRequest, db: Session = Depends(get_db)):
    """Legacy buyer registration/login endpoint maintained for backward compatibility."""
    buyer, token = _register_buyer_record(payload, db)
    return {
        "status": "success",
        "user_type": "buyer",
        "role": "BUYER",
        "user_id": buyer.id,
        "name": buyer.name,
        "phone_number": buyer.phone_number,
        "address": buyer.address,
        "pincode": buyer.pincode,
        "state": buyer.state,
        "access_token": token,
        "message": f"Welcome, {buyer.name}! Access granted.",
        "details": {
            "buyer_id": buyer.id,
            "city": buyer.city
        }
    }


@router.post("/admin/login", response_model=AuthResponse)
def login_admin(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Admin & Owner login:
    Verifies Admin User ID and Password.
    If credentials match server OWNER configuration -> Authenticated as OWNER.
    Else checks regular Admin accounts in the database -> Authenticated as ADMIN.
    """
    user_id_input = payload.admin_user_id.strip()
    password_input = payload.password.strip()

    if not user_id_input or not password_input:
        raise HTTPException(status_code=400, detail="Admin User ID and Password are required.")

    # 1. Check Owner / Super Admin Credentials (Configured via Server Environment Variables)
    if user_id_input == OWNER_ADMIN_ID and password_input == OWNER_ADMIN_PASSWORD:
        token = create_access_token({
            "sub": "owner",
            "user_id": OWNER_ADMIN_ID,
            "role": "OWNER",
            "name": "Owner / Super Admin"
        })
        return {
            "status": "success",
            "user_type": "owner",
            "role": "OWNER",
            "user_id": OWNER_ADMIN_ID,
            "name": "Owner / Super Admin",
            "access_token": token,
            "message": "Super Admin authenticated successfully. Welcome to the Owner Dashboard."
        }

    # 2. Check Regular Team Admin Accounts in the Database
    admin = db.query(Admin).filter(Admin.admin_user_id == user_id_input).first()
    if not admin or not verify_password(password_input, admin.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid Admin ID or password."
        )

    if admin.is_active != 1:
        raise HTTPException(
            status_code=403,
            detail="This Admin account has been disabled. Please contact the Owner."
        )

    token = create_access_token({
        "sub": str(admin.id),
        "user_id": admin.admin_user_id,
        "role": "ADMIN",
        "name": admin.name
    })

    return {
        "status": "success",
        "user_type": "admin",
        "role": "ADMIN",
        "user_id": admin.admin_user_id,
        "name": admin.name,
        "access_token": token,
        "message": f"Welcome back, Admin {admin.name}! Login successful."
    }


@router.get("/farmer/{farmer_id}/supplies")
def get_farmer_supplies(farmer_id: int, db: Session = Depends(get_db)):
    """Get all produce commodities and stock clearance status for a specific farmer."""
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
    total_remaining_val = 0.0
    total_cleared_revenue = 0.0
    total_harvest_kg = 0.0
    total_cleared_kg = 0.0
    total_left_kg = 0.0

    for s, p in supplies:
        stock_left = max(0.0, float(s.quantity or 0.0))
        stock_cleared = max(0.0, float(s.cleared_quantity or 0.0))
        initial_tot = float(s.initial_quantity or (stock_left + stock_cleared))
        if initial_tot <= 0:
            initial_tot = stock_left + stock_cleared
        if initial_tot < (stock_left + stock_cleared):
            initial_tot = stock_left + stock_cleared

        clearance_pct = round((stock_cleared / initial_tot * 100.0), 1) if initial_tot > 0 else 0.0
        remaining_val = round(stock_left * s.expected_price, 2)
        cleared_rev = round(stock_cleared * s.expected_price, 2)
        price_diff = round(s.expected_price - p.mandi_benchmark_price, 2)

        total_remaining_val += remaining_val
        total_cleared_revenue += cleared_rev
        total_harvest_kg += initial_tot
        total_cleared_kg += stock_cleared
        total_left_kg += stock_left

        if stock_left == 0 and stock_cleared > 0:
            status_text = "ALL_ORDERED"
        elif stock_cleared > 0:
            status_text = "PARTIALLY_ORDERED"
        else:
            status_text = "IN_STOCK"

        result.append({
            "supply_id": s.id,
            "product_id": p.id,
            "product_name": p.name,
            "category": p.category,
            "expected_price": round(s.expected_price, 2),
            "mandi_benchmark": round(p.mandi_benchmark_price, 2),
            "price_diff": price_diff,
            "quality_grade": s.quality_grade or "Grade A",
            "quantity_left_kg": stock_left,
            "quantity_ordered_kg": stock_cleared,
            "stock_left_kg": stock_left,
            "stock_cleared_kg": stock_cleared,
            "total_harvest_kg": initial_tot,
            "ordered_pct": clearance_pct,
            "clearance_pct": clearance_pct,
            "remaining_value": remaining_val,
            "ordered_revenue": cleared_rev,
            "cleared_revenue": cleared_rev,
            "status": status_text
        })

    overall_clearance_pct = round((total_cleared_kg / total_harvest_kg * 100.0), 1) if total_harvest_kg > 0 else 0.0

    return {
        "farmer_id": farmer.id,
        "name": farmer.name,
        "location": farmer.location,
        "contact": farmer.contact,
        "address": farmer.address,
        "pincode": farmer.pincode,
        "state": farmer.state,
        "kpis": {
            "total_harvest_kg": round(total_harvest_kg, 1),
            "total_ordered_kg": round(total_cleared_kg, 1),
            "total_cleared_kg": round(total_cleared_kg, 1),
            "total_left_kg": round(total_left_kg, 1),
            "order_fulfillment_pct": overall_clearance_pct,
            "overall_clearance_pct": overall_clearance_pct,
            "total_ordered_revenue": round(total_cleared_revenue, 2),
            "total_cleared_revenue": round(total_cleared_revenue, 2),
            "total_remaining_value": round(total_remaining_val, 2),
            "total_inventory_value": round(total_remaining_val, 2)
        },
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
        if supply.initial_quantity is None:
            supply.initial_quantity = supply.quantity
        else:
            supply.initial_quantity += payload.quantity_kg
        supply.expected_price = payload.price_per_kg
    else:
        supply = Supply(
            farmer_id=farmer.id,
            product_id=product.id,
            quantity=payload.quantity_kg,
            cleared_quantity=0.0,
            initial_quantity=payload.quantity_kg,
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


@router.put("/farmer/supply/{supply_id}")
@router.post("/farmer/supply/{supply_id}/update")
def update_farmer_supply(
    supply_id: int,
    payload: FarmerUpdateSupplyRequest,
    db: Session = Depends(get_db)
):
    """Allows a farmer to update their crop name, available quantity, and asking price."""
    farmer = db.query(Farmer).filter(Farmer.id == payload.farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    supply = db.query(Supply).filter(
        Supply.id == supply_id,
        Supply.farmer_id == payload.farmer_id
    ).first()
    if not supply:
        raise HTTPException(status_code=404, detail="Commodity supply record not found")

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

    supply.product_id = product.id
    supply.quantity = payload.quantity_kg
    supply.expected_price = payload.price_per_kg
    if payload.quality_grade:
        supply.quality_grade = payload.quality_grade

    cleared = float(supply.cleared_quantity or 0.0)
    supply.initial_quantity = max(float(supply.initial_quantity or 0.0), payload.quantity_kg + cleared)

    db.commit()
    return {
        "status": "success",
        "message": f"Successfully updated {product.name}: {payload.quantity_kg:,.0f} kg @ ₹{payload.price_per_kg:.2f}/kg."
    }


@router.post("/farmer/clear-stock")
def clear_farmer_stock(payload: FarmerClearStockRequest, db: Session = Depends(get_db)):
    """
    Records an order / fulfilled stock for a farmer's commodity batch.
    Deducts ordered quantity from available stock (quantity left) and adds to quantity ordered.
    """
    supply = db.query(Supply).filter(
        Supply.id == payload.supply_id,
        Supply.farmer_id == payload.farmer_id
    ).first()
    if not supply:
        raise HTTPException(status_code=404, detail="Produce supply batch not found.")

    order_qty = payload.ordered_quantity_kg or payload.cleared_quantity_kg
    if not order_qty or order_qty <= 0:
        raise HTTPException(status_code=400, detail="Ordered quantity must be greater than 0.")

    if order_qty > supply.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot record order of {order_qty:,.0f} kg. Only {supply.quantity:,.0f} kg remaining in stock."
        )

    supply.quantity = max(0.0, supply.quantity - order_qty)
    supply.cleared_quantity = (supply.cleared_quantity or 0.0) + order_qty

    product = db.query(Product).filter(Product.id == supply.product_id).first()
    prod_name = product.name if product else "Commodity"

    realized_rate = payload.selling_price_per_kg or supply.expected_price
    cleared_val = round(order_qty * realized_rate, 2)

    db.commit()
    db.refresh(supply)

    return {
        "status": "success",
        "message": f"Successfully recorded order of {order_qty:,.0f} kg of {prod_name}. Remaining quantity left: {supply.quantity:,.0f} kg. Total order value: ₹{cleared_val:,.2f}.",
        "supply_id": supply.id,
        "quantity_ordered_kg": supply.cleared_quantity,
        "quantity_left_kg": supply.quantity,
        "stock_left_kg": supply.quantity,
        "stock_cleared_kg": supply.cleared_quantity,
        "cleared_revenue": cleared_val,
        "ordered_revenue": cleared_val
    }


@router.get("/buyers", response_model=List[BuyerOut])
def get_all_buyers(db: Session = Depends(get_db)):
    """List all registered buyers in the system."""
    return db.query(Buyer).order_by(Buyer.created_at.desc()).all()


@router.get("/farmer/{farmer_id}/orders")
def get_farmer_orders(
    farmer_id: int,
    product_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Fetch all buyer orders involving this farmer's commodities.
    Shows who ordered (buyer name, contact, location), what was ordered (crop, grade),
    and quantity taking (kg, total payout, order status).
    """
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    query = (
        db.query(OrderItem, Order, Product)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, Order.product_id == Product.id)
        .filter(OrderItem.farmer_id == farmer_id)
    )

    if product_id:
        query = query.filter(Order.product_id == product_id)

    records = query.order_by(Order.created_at.desc()).all()

    orders_list = []
    for item, ord_rec, prod in records:
        buyer = db.query(Buyer).filter(Buyer.name.ilike(ord_rec.buyer_name)).first()
        buyer_phone = buyer.phone_number if buyer else "Contact via Platform"
        buyer_address = buyer.address if buyer else "Central Wholesale Depot"
        buyer_city = buyer.city if buyer and buyer.city else (buyer.state if buyer else "West Bengal")

        orders_list.append({
            "order_item_id": item.id,
            "order_id": ord_rec.id,
            "order_number": ord_rec.order_number,
            "buyer_name": ord_rec.buyer_name,
            "buyer_phone": buyer_phone,
            "buyer_address": buyer_address,
            "buyer_city": buyer_city,
            "product_id": prod.id,
            "product_name": prod.name,
            "quality_grade": "Grade A",
            "allocated_quantity_kg": item.allocated_quantity,
            "price_per_kg": item.price_per_kg,
            "subtotal": item.subtotal,
            "status": ord_rec.status,
            "created_at": ord_rec.created_at.strftime("%Y-%m-%d %I:%M %p") if ord_rec.created_at else "",
            "estimated_distance_km": ord_rec.estimated_distance_km
        })

    return {
        "farmer_id": farmer.id,
        "farmer_name": farmer.name,
        "total_orders_count": len(orders_list),
        "total_ordered_quantity_kg": sum(o["allocated_quantity_kg"] for o in orders_list),
        "total_order_revenue": sum(o["subtotal"] for o in orders_list),
        "orders": orders_list
    }


@router.delete("/farmer/{farmer_id}/orders/{order_item_id}")
def delete_farmer_order_item(
    farmer_id: int,
    order_item_id: int,
    db: Session = Depends(get_db)
):
    """
    Removes an order item from the farmer's history.
    Also restores the allocated quantity back to the farmer's available stock left.
    """
    item = db.query(OrderItem).filter(
        OrderItem.id == order_item_id,
        OrderItem.farmer_id == farmer_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found in farmer history")

    ord_rec = db.query(Order).filter(Order.id == item.order_id).first()
    prod_name = "Crop"
    if ord_rec:
        product = db.query(Product).filter(Product.id == ord_rec.product_id).first()
        if product:
            prod_name = product.name

        supply = db.query(Supply).filter(
            Supply.farmer_id == farmer_id,
            Supply.product_id == ord_rec.product_id
        ).first()
        if supply:
            supply.quantity += item.allocated_quantity
            supply.cleared_quantity = max(0.0, (supply.cleared_quantity or 0.0) - item.allocated_quantity)

    qty = item.allocated_quantity
    parent_order_id = item.order_id
    db.delete(item)
    db.commit()

    # If parent order has no other items, clean it up
    remaining = db.query(OrderItem).filter(OrderItem.order_id == parent_order_id).count()
    if remaining == 0:
        db.query(Order).filter(Order.id == parent_order_id).delete()
        db.commit()

    return {
        "status": "success",
        "message": f"Successfully removed order for {qty:,.0f} kg of {prod_name} from history. Quantity restored to your available stock."
    }


@router.delete("/farmer/{farmer_id}/orders")
def clear_all_farmer_orders(
    farmer_id: int,
    product_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Clears all order history for this farmer (optionally for a specific crop).
    Restores inventory and removes order items.
    """
    query = (
        db.query(OrderItem, Order)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(OrderItem.farmer_id == farmer_id)
    )
    if product_id:
        query = query.filter(Order.product_id == product_id)

    records = query.all()
    if not records:
        return {"status": "success", "message": "No order history found to clear.", "deleted_count": 0}

    deleted_count = 0
    restored_kg = 0.0
    affected_order_ids = set()
    for item, ord_rec in records:
        affected_order_ids.add(ord_rec.id)
        supply = db.query(Supply).filter(
            Supply.farmer_id == farmer_id,
            Supply.product_id == ord_rec.product_id
        ).first()
        if supply:
            supply.quantity += item.allocated_quantity
            supply.cleared_quantity = max(0.0, (supply.cleared_quantity or 0.0) - item.allocated_quantity)
            restored_kg += item.allocated_quantity
        db.delete(item)
        deleted_count += 1

    db.commit()

    # Clean up parent orders if empty
    for o_id in affected_order_ids:
        if db.query(OrderItem).filter(OrderItem.order_id == o_id).count() == 0:
            db.query(Order).filter(Order.id == o_id).delete()
    db.commit()

    return {
        "status": "success",
        "message": f"Cleared {deleted_count} order(s) from history. {restored_kg:,.0f} kg restored to available stock.",
        "deleted_count": deleted_count,
        "restored_quantity_kg": restored_kg
    }


@router.post("/reset-database")
def reset_database(db: Session = Depends(get_db)):
    """
    Clears all user data (farmers, buyers, supplies, orders, order items, demands)
    so the platform starts 100% fresh for new logins.
    """
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(Supply).delete()
    db.query(Demand).delete()
    db.query(Farmer).delete()
    db.query(Buyer).delete()
    db.commit()
    return {
        "status": "success",
        "message": "Complete database user records cleared! Ready for new farmer and buyer logins."
    }

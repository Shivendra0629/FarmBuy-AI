from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
import random

from ..database import get_db
from ..models import Admin, Farmer, Buyer, Product, Supply, Order, OrderItem, Demand, DemandHistory
from ..schemas import (
    AdminOut,
    AdminCreateRequest,
    AdminUpdateIdRequest,
    AdminUpdatePasswordRequest,
    AdminStatusRequest,
    DemoResetRequest,
    FarmerOut,
    BuyerOut,
    SupplyOut
)
from ..security import (
    hash_password,
    verify_password,
    require_admin,
    require_owner,
    OWNER_ADMIN_ID
)

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin & Owner Management"]
)


# ============================================================================
# 1. OWNER-ONLY ADMIN MANAGEMENT (Strictly requires role == 'OWNER')
# ============================================================================

@router.get("/manage/admins", response_model=List[AdminOut])
def list_admins(
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Lists all regular team Admin accounts along with the root Owner.
    Never returns passwords or password hashes.
    """
    owner_entry = AdminOut(
        id=0,
        name="Platform Owner",
        admin_user_id=OWNER_ADMIN_ID,
        role="OWNER",
        is_active=1,
        created_at=None
    )
    db_admins = db.query(Admin).order_by(Admin.created_at.asc()).all()
    results = [owner_entry]
    for a in db_admins:
        results.append(AdminOut.model_validate(a))
    return results


@router.post("/manage/create", response_model=Dict[str, Any])
def create_admin(
    payload: AdminCreateRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Creates a new regular Admin account for the team.
    Enforces a strict ceiling of at most 6 regular Admin accounts.
    """
    clean_id = payload.admin_user_id.strip()
    clean_name = payload.name.strip()
    clean_password = payload.password.strip()

    if not clean_id or not clean_name or not clean_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin Name, User ID, and Password are all required."
        )

    # 1. Enforce max 6 regular team admins
    current_count = db.query(Admin).count()
    if current_count >= 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum limit of 6 regular Admin accounts reached. To add another, please remove an existing admin."
        )

    # 2. Prevent collision with Owner ID
    if clean_id.lower() == OWNER_ADMIN_ID.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use the Owner / Super Admin identifier for a regular admin account."
        )

    # 3. Check uniqueness among existing admins
    existing = db.query(Admin).filter(Admin.admin_user_id.ilike(clean_id)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Admin User ID '{clean_id}' already exists. Please choose a unique ID."
        )

    # 4. Hash password securely using PBKDF2-HMAC-SHA256
    pwd_hash = hash_password(clean_password)

    new_admin = Admin(
        name=clean_name,
        admin_user_id=clean_id,
        password_hash=pwd_hash,
        role="ADMIN",
        is_active=1
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {
        "status": "success",
        "message": f"Admin account '{new_admin.name}' (ID: {new_admin.admin_user_id}) created successfully.",
        "admin": {
            "id": new_admin.id,
            "name": new_admin.name,
            "admin_user_id": new_admin.admin_user_id,
            "role": new_admin.role,
            "is_active": new_admin.is_active,
            "created_at": new_admin.created_at.isoformat() if new_admin.created_at else None
        }
    }


@router.patch("/manage/{admin_id}/user-id", response_model=Dict[str, Any])
@router.put("/manage/{admin_id}/user-id", response_model=Dict[str, Any])
def update_admin_user_id(
    admin_id: int,
    payload: AdminUpdateIdRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Changes an Admin's User ID after verifying uniqueness.
    """
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    new_id = (payload.new_admin_user_id or payload.admin_user_id or "").strip()
    if not new_id:
        raise HTTPException(status_code=400, detail="New Admin User ID cannot be empty.")

    if new_id.lower() == OWNER_ADMIN_ID.lower():
        raise HTTPException(status_code=400, detail="Cannot assign the Owner / Super Admin identifier.")

    # Verify uniqueness
    duplicate = db.query(Admin).filter(
        Admin.admin_user_id.ilike(new_id),
        Admin.id != admin_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"Admin User ID '{new_id}' is already in use.")

    old_id = admin.admin_user_id
    admin.admin_user_id = new_id
    db.commit()
    db.refresh(admin)

    return {
        "status": "success",
        "message": f"Admin User ID updated from '{old_id}' to '{admin.admin_user_id}'."
    }


@router.patch("/manage/{admin_id}/password", response_model=Dict[str, Any])
@router.put("/manage/{admin_id}/password", response_model=Dict[str, Any])
def update_admin_password(
    admin_id: int,
    payload: AdminUpdatePasswordRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Changes an Admin's password.
    Hashes the new password securely and stores it. Never returns password in response.
    """
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    new_pwd = (payload.new_password or payload.password or "").strip()
    if len(new_pwd) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long.")

    admin.password_hash = hash_password(new_pwd)
    db.commit()

    return {
        "status": "success",
        "message": f"Password for Admin '{admin.name}' ({admin.admin_user_id}) updated successfully."
    }


@router.patch("/manage/{admin_id}/status", response_model=Dict[str, Any])
@router.put("/manage/{admin_id}/status", response_model=Dict[str, Any])
def update_admin_status(
    admin_id: int,
    payload: AdminStatusRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Enables or disables an Admin account.
    Disabled accounts are immediately prevented from logging in.
    """
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    admin.is_active = 1 if payload.is_active in [1, True, "1", "true", "True"] else 0
    db.commit()
    db.refresh(admin)

    status_str = "Enabled" if admin.is_active == 1 else "Disabled"
    return {
        "status": "success",
        "message": f"Admin account '{admin.name}' ({admin.admin_user_id}) is now {status_str}.",
        "is_active": admin.is_active
    }


@router.delete("/manage/{admin_id}/delete", response_model=Dict[str, Any])
@router.delete("/manage/{admin_id}", response_model=Dict[str, Any])
def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Deletes/revokes an Admin account.
    Does NOT affect any farmer, buyer, supply, or order data.
    """
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    admin_name = admin.name
    admin_uid = admin.admin_user_id
    db.delete(admin)
    db.commit()

    return {
        "status": "success",
        "message": f"Admin account '{admin_name}' (ID: {admin_uid}) has been revoked and removed."
    }


# ============================================================================
# 2. OWNER-ONLY DEMO DATABASE RESET (Preserves schema & Admin accounts)
# ============================================================================

def _seed_demo_operational_data(db: Session):
    """Restores the standard FarmBuy AI demo dataset without dropping tables or touching admins."""
    # 1. Clear operational tables
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(Demand).delete()
    db.query(DemandHistory).delete()
    db.query(Supply).delete()
    db.query(Farmer).delete()
    db.query(Buyer).delete()
    db.query(Product).delete()
    db.commit()

    today = date.today()

    # 2. Seed commodities
    products_data = [
        {"name": "Tomato", "category": "Vegetable", "unit": "kg", "mandi_benchmark_price": 22.0, "perishability_days": 7},
        {"name": "Potato (Jyoti)", "category": "Tuber", "unit": "kg", "mandi_benchmark_price": 16.5, "perishability_days": 45},
        {"name": "Red Onion", "category": "Allium", "unit": "kg", "mandi_benchmark_price": 28.0, "perishability_days": 25},
        {"name": "Green Chilli", "category": "Spice", "unit": "kg", "mandi_benchmark_price": 54.0, "perishability_days": 10},
        {"name": "Cauliflower", "category": "Vegetable", "unit": "kg", "mandi_benchmark_price": 18.0, "perishability_days": 8},
    ]
    products = {}
    for pdata in products_data:
        p = Product(**pdata)
        db.add(p)
        db.commit()
        db.refresh(p)
        products[p.name] = p

    # 3. Seed demo farmers
    farmers_data = [
        {"name": "Subhash Mondal", "location": "Singur, Hooghly", "latitude": 22.8124, "longitude": 88.2312, "contact": "9831102931", "rating": 4.9, "farm_size_acres": 6.5, "state": "West Bengal", "pincode": "712409"},
        {"name": "Ramesh Ghosh", "location": "Bardhaman Rural", "latitude": 23.2324, "longitude": 87.8615, "contact": "9434218902", "rating": 4.8, "farm_size_acres": 12.0, "state": "West Bengal", "pincode": "713101"},
        {"name": "Animesh Biswas", "location": "Ranaghat, Nadia", "latitude": 23.1804, "longitude": 88.5801, "contact": "9732194821", "rating": 4.7, "farm_size_acres": 4.5, "state": "West Bengal", "pincode": "741201"},
        {"name": "Prabir Samanta", "location": "Arambagh, Hooghly", "latitude": 22.8821, "longitude": 87.7812, "contact": "9830561234", "rating": 4.9, "farm_size_acres": 8.0, "state": "West Bengal", "pincode": "712601"},
        {"name": "Debabrata Das", "location": "Uluberia, Howrah", "latitude": 22.4732, "longitude": 88.1102, "contact": "9647891230", "rating": 4.6, "farm_size_acres": 5.0, "state": "West Bengal", "pincode": "711315"}
    ]
    farmers = []
    for fdata in farmers_data:
        f = Farmer(**fdata)
        db.add(f)
        db.commit()
        db.refresh(f)
        farmers.append(f)

    # 4. Seed demo buyer
    demo_buyer = Buyer(
        name="Posta Wholesale Procurement Hub",
        address="Posta Market, Barabazar",
        city="Kolkata",
        phone_number="9830112233",
        pincode="700007",
        state="West Bengal"
    )
    db.add(demo_buyer)
    db.commit()

    # 5. Seed supplies
    supplies_data = [
        (farmers[0].id, products["Tomato"].id, 3500, 21.0, "Grade A"),
        (farmers[1].id, products["Tomato"].id, 4000, 23.0, "Grade A"),
        (farmers[2].id, products["Tomato"].id, 2200, 20.5, "Grade B"),
        (farmers[3].id, products["Tomato"].id, 3000, 22.5, "Grade A"),
        (farmers[1].id, products["Potato (Jyoti)"].id, 12000, 15.5, "Grade A"),
        (farmers[3].id, products["Potato (Jyoti)"].id, 15000, 16.0, "Grade A"),
        (farmers[0].id, products["Red Onion"].id, 4000, 27.5, "Grade A"),
        (farmers[2].id, products["Red Onion"].id, 3500, 28.5, "Grade A"),
        (farmers[0].id, products["Green Chilli"].id, 1200, 53.0, "Grade A"),
        (farmers[4].id, products["Cauliflower"].id, 3800, 18.5, "Grade B"),
    ]
    for f_id, p_id, qty, price, grade in supplies_data:
        s = Supply(
            farmer_id=f_id,
            product_id=p_id,
            quantity=qty,
            cleared_quantity=0.0,
            initial_quantity=qty,
            expected_price=price,
            quality_grade=grade,
            available_date=today + timedelta(days=1),
            harvest_date=today - timedelta(days=1)
        )
        db.add(s)

    # 6. Seed 60-day historical demand
    random.seed(42)
    for p_name, prod in products.items():
        base_vol = 7000.0 if "Potato" in p_name else (5500.0 if "Tomato" in p_name else 3500.0)
        base_price = prod.mandi_benchmark_price
        for day_offset in range(60, 0, -1):
            hist_date = today - timedelta(days=day_offset)
            dow = hist_date.weekday()
            surge = 1.18 if dow in (4, 5, 6) else 0.94
            trend_factor = 1.0 + ((60 - day_offset) * 0.003)
            qty = round(base_vol * surge * trend_factor + random.uniform(-300, 300), 1)
            mandi_p = round(base_price + random.uniform(-1.5, 1.8), 2)
            dh = DemandHistory(
                product_id=prod.id,
                date=hist_date,
                region="Kolkata Metro Hub",
                quantity_demanded=qty,
                average_mandi_price=mandi_p
            )
            db.add(dh)

    db.commit()


@router.post("/reset-demo-data", response_model=Dict[str, Any])
def reset_demo_database(
    payload: DemoResetRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Restores the standard FarmBuy AI demo database.
    Requires explicit confirmation.
    Preserves database schema and Admin accounts intact.
    """
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset confirmation flag is required."
        )

    _seed_demo_operational_data(db)

    return {
        "status": "success",
        "message": "FarmBuy AI demo dataset successfully restored! Database schema and Admin accounts preserved."
    }


# ============================================================================
# 3. ADMIN & OWNER OPERATIONAL DATA (Requires role in ['ADMIN', 'OWNER'])
# ============================================================================

@router.get("/farmers", response_model=List[FarmerOut])
def get_admin_farmers(
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """Admin & Owner: Lists all registered farmers with coordinates and ratings."""
    return db.query(Farmer).order_by(Farmer.id.desc()).all()


@router.get("/buyers", response_model=List[BuyerOut])
def get_admin_buyers(
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """Admin & Owner: Lists all registered buyers and wholesale enterprises."""
    return db.query(Buyer).order_by(Buyer.created_at.desc()).all()


@router.get("/supplies")
def get_admin_supplies(
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """Admin & Owner: Lists all farmer supplies across the system."""
    supplies = (
        db.query(Supply, Farmer, Product)
        .join(Farmer, Supply.farmer_id == Farmer.id)
        .join(Product, Supply.product_id == Product.id)
        .order_by(Supply.id.desc())
        .all()
    )
    results = []
    for s, f, p in supplies:
        results.append({
            "id": s.id,
            "farmer_id": f.id,
            "farmer_name": f.name,
            "farmer_contact": f.contact,
            "location": f.location,
            "product_id": p.id,
            "product_name": p.name,
            "category": p.category,
            "quantity_left_kg": s.quantity,
            "quantity_ordered_kg": s.cleared_quantity or 0.0,
            "expected_price": s.expected_price,
            "mandi_benchmark": p.mandi_benchmark_price,
            "quality_grade": s.quality_grade,
            "available_date": str(s.available_date) if s.available_date else None
        })
    return results


@router.get("/orders")
def get_admin_orders(
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """Admin & Owner: Lists all procurement contracts, tracking status, and line items."""
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    results = []
    for o in orders:
        product = db.query(Product).filter(Product.id == o.product_id).first()
        items = (
            db.query(OrderItem, Farmer)
            .join(Farmer, OrderItem.farmer_id == Farmer.id)
            .filter(OrderItem.order_id == o.id)
            .all()
        )
        item_list = []
        for itm, f in items:
            item_list.append({
                "farmer_id": f.id,
                "farmer_name": f.name,
                "location": f.location,
                "allocated_quantity_kg": itm.allocated_quantity,
                "price_per_kg": itm.price_per_kg,
                "subtotal": itm.subtotal
            })

        results.append({
            "id": o.id,
            "order_number": o.order_number,
            "buyer_name": o.buyer_name,
            "product_id": o.product_id,
            "product_name": product.name if product else "Produce",
            "total_quantity_kg": o.total_quantity,
            "agreed_price_per_kg": o.agreed_price_per_kg,
            "total_procurement_cost": o.total_procurement_cost,
            "logistics_cost": o.logistics_cost,
            "grand_total": round(o.total_procurement_cost + (o.logistics_cost or 0.0), 2),
            "estimated_distance_km": o.estimated_distance_km,
            "status": o.status,
            "created_at": o.created_at.strftime("%Y-%m-%d %I:%M %p") if o.created_at else "",
            "items": item_list
        })
    return results


@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """Admin & Owner: Overview operational statistics."""
    total_farmers = db.query(Farmer).count()
    total_buyers = db.query(Buyer).count()
    total_products = db.query(Product).count()
    total_admins = db.query(Admin).count()
    total_supplies = db.query(Supply).all()
    total_orders = db.query(Order).all()

    stock_left_kg = sum(s.quantity for s in total_supplies)
    stock_cleared_kg = sum((s.cleared_quantity or 0.0) for s in total_supplies)
    total_revenue = sum(o.total_procurement_cost for o in total_orders)

    return {
        "active_farmers": total_farmers,
        "farmers_count": total_farmers,
        "active_buyers": total_buyers,
        "buyers_count": total_buyers,
        "commodities_tracked": total_products,
        "team_admins_count": total_admins,
        "active_admins_count": total_admins,
        "max_team_admins": 6,
        "total_stock_left_kg": round(stock_left_kg, 1),
        "supplies_total_kg": round(stock_left_kg, 1),
        "total_stock_cleared_kg": round(stock_cleared_kg, 1),
        "supplies_count": len(total_supplies),
        "orders_count": len(total_orders),
        "orders_total_val": round(total_revenue, 2),
        "total_procurement_volume_inr": round(total_revenue, 2)
    }

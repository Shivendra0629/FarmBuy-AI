from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
import random

from ..database import get_db, IS_SQLITE
from ..models import Admin, Farmer, Buyer, Product, Supply, Order, OrderItem, Demand, DemandHistory
from ..schemas import (
    AdminOut,
    AdminCreateRequest,
    AdminUpdateIdRequest,
    AdminUpdatePasswordRequest,
    AdminStatusRequest,
    OwnerUpdateCredentialsRequest,
    DemoResetRequest,
    FarmerOut,
    FarmerUpdateRequest,
    BuyerOut,
    BuyerUpdateRequest,
    SupplyOut
)
from ..security import (
    hash_password,
    verify_password,
    require_admin,
    require_owner,
    OWNER_ADMIN_ID,
    get_owner_credentials,
    get_owner_admin_id,
    save_owner_credentials
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
    current_owner_id = get_owner_admin_id(db=db)
    owner_entry = AdminOut(
        id=0,
        name="Super Admin (Owner)",
        admin_user_id=current_owner_id,
        role="OWNER",
        is_active=1,
        created_at=None
    )
    db_admins = db.query(Admin).filter(Admin.role == "ADMIN").order_by(Admin.id.asc()).all()
    results = [owner_entry]
    for a in db_admins:
        results.append(AdminOut.model_validate(a))
    return results


@router.patch("/manage/owner/credentials", response_model=Dict[str, Any])
@router.put("/manage/owner/credentials", response_model=Dict[str, Any])
@router.post("/manage/owner/credentials", response_model=Dict[str, Any])
def update_owner_credentials(
    payload: OwnerUpdateCredentialsRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Updates the Super Admin User ID and/or Password in the database.
    Persists changes so new logins require the updated credentials.
    """
    new_id = payload.new_admin_user_id.strip() if payload.new_admin_user_id else None
    new_pwd = payload.new_password.strip() if payload.new_password else None

    if not new_id and not new_pwd:
        raise HTTPException(status_code=400, detail="Must provide new User ID or new Password.")

    if new_pwd and len(new_pwd) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long.")

    if new_id:
        # Check uniqueness against existing team admins
        existing = db.query(Admin).filter(Admin.admin_user_id.ilike(new_id), Admin.role != "OWNER").first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Admin ID '{new_id}' is already taken by a team admin.")

    # Save to database and runtime configuration
    creds = save_owner_credentials(new_admin_id=new_id, new_password=new_pwd, db=db)

    return {
        "status": "success",
        "message": "Super Admin credentials updated successfully! Please use your new credentials on next login.",
        "admin_user_id": creds["admin_user_id"]
    }


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
    current_count = db.query(Admin).filter(Admin.role == "ADMIN").count()
    if current_count >= 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum limit of 6 regular Admin accounts reached. To add another, please remove an existing admin."
        )

    # 2. Prevent collision with Owner ID
    current_owner_id = get_owner_admin_id()
    if clean_id.lower() == current_owner_id.lower():
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

    # 5. Determine next sequential slot starting strictly from 1 (1 to 6)
    existing_admins = db.query(Admin).filter(Admin.role == "ADMIN").all()
    existing_ids = {a.id for a in existing_admins}
    next_id = 1
    while next_id in existing_ids:
        next_id += 1

    try:
        new_admin = Admin(
            id=next_id,
            name=clean_name,
            admin_user_id=clean_id,
            password_hash=pwd_hash,
            role="ADMIN",
            is_active=1
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create admin: {str(e)}")

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

    if new_id.lower() == get_owner_admin_id(db=db).lower():
        raise HTTPException(status_code=400, detail="Cannot assign the Owner / Super Admin identifier.")

    # Verify uniqueness
    duplicate = db.query(Admin).filter(
        Admin.admin_user_id.ilike(new_id),
        Admin.id != admin_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail=f"Admin User ID '{new_id}' is already in use.")

    old_id = admin.admin_user_id
    try:
        admin.admin_user_id = new_id
        db.commit()
        db.refresh(admin)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update Admin ID: {str(e)}")

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

    try:
        admin.password_hash = hash_password(new_pwd)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update Admin password: {str(e)}")

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

    try:
        admin.is_active = 1 if payload.is_active in [1, True, "1", "true", "True"] else 0
        db.commit()
        db.refresh(admin)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update Admin status: {str(e)}")

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
    admin = db.query(Admin).filter(Admin.id == admin_id, Admin.role == "ADMIN").first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin account not found.")

    admin_name = admin.name
    admin_uid = admin.admin_user_id
    try:
        db.delete(admin)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete Admin account: {str(e)}")

    return {
        "status": "success",
        "message": f"Admin account '{admin_name}' (ID: {admin_uid}) has been revoked and removed."
    }


# ============================================================================
# 2. OWNER-ONLY DATA WIPE & RESET (Preserves schema & Admin accounts)
# ============================================================================

def _wipe_platform_operational_data(db: Session):
    """Wipes all operational farmer, buyer, supply, demand, and order data leaving platform 100% clean."""
    try:
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(Demand).delete()
        db.query(DemandHistory).delete()
        db.query(Supply).delete()
        db.query(Farmer).delete()
        db.query(Buyer).delete()

        # Reset SQLite autoincrement sequences so clean databases restart IDs from 1
        if IS_SQLITE:
            try:
                from sqlalchemy import text
                db.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('farmers', 'buyers', 'supplies', 'orders', 'order_items', 'demands', 'demand_history')"))
            except Exception:
                pass

        # Ensure baseline agricultural commodities exist so price intelligence works
        existing_prods = db.query(Product).count()
        if existing_prods == 0:
            products_data = [
                {"name": "Tomato", "category": "Vegetable", "unit": "kg", "mandi_benchmark_price": 22.0, "perishability_days": 7},
                {"name": "Potato (Jyoti)", "category": "Tuber", "unit": "kg", "mandi_benchmark_price": 16.5, "perishability_days": 45},
                {"name": "Red Onion", "category": "Allium", "unit": "kg", "mandi_benchmark_price": 28.0, "perishability_days": 25},
                {"name": "Green Chilli", "category": "Spice", "unit": "kg", "mandi_benchmark_price": 54.0, "perishability_days": 10},
                {"name": "Cauliflower", "category": "Vegetable", "unit": "kg", "mandi_benchmark_price": 18.0, "perishability_days": 8},
            ]
            for pdata in products_data:
                p = Product(**pdata)
                db.add(p)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database wipe failed: {str(e)}")


@router.post("/reset-demo-data", response_model=Dict[str, Any])
@router.post("/wipe-data", response_model=Dict[str, Any])
def reset_demo_database(
    payload: DemoResetRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_owner)
):
    """
    Owner only: Wipes all test farmers, buyers, supplies, and platform orders.
    Leaves the platform 100% clean with NO predefined or synthetic users.
    Preserves database schema and Admin accounts intact.
    """
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset confirmation flag is required."
        )

    _wipe_platform_operational_data(db)

    return {
        "status": "success",
        "message": "All farmer, buyer, supply, and order records wiped! Database is clean with zero synthetic/predefined records. Admin accounts are preserved."
    }


# ============================================================================
# 3. ADMIN & OWNER OPERATIONAL DATA (Requires role in ['ADMIN', 'OWNER'])
# ============================================================================

@router.get("/farmers")
def get_admin_farmers(
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """Admin & Owner: Lists all registered farmers with coordinates, phone, and ratings."""
    farmers = db.query(Farmer).order_by(Farmer.id.desc()).all()
    results = []
    for f in farmers:
        phone = f.contact or ""
        results.append({
            "id": f.id,
            "name": f.name,
            "phone_number": phone,
            "contact": phone,
            "address": f.address or f.location or "",
            "location": f.location or "",
            "state": f.state or "West Bengal",
            "pincode": f.pincode or "",
            "latitude": f.latitude,
            "longitude": f.longitude,
            "rating": f.rating,
            "farm_size_acres": f.farm_size_acres
        })
    return results


@router.put("/farmers/{farmer_id}", response_model=Dict[str, Any])
@router.patch("/farmers/{farmer_id}", response_model=Dict[str, Any])
def update_admin_farmer(
    farmer_id: int,
    payload: FarmerUpdateRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """
    Admin & Owner: Modifies details of a registered farmer.
    Both regular Admin and Super Admin (Owner) are fully authorized.
    """
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found.")

    if payload.name is not None and payload.name.strip():
        farmer.name = payload.name.strip()
    if payload.phone_number is not None and payload.phone_number.strip():
        farmer.contact = payload.phone_number.strip()
    if payload.address is not None and payload.address.strip():
        farmer.address = payload.address.strip()
    if payload.state is not None and payload.state.strip():
        farmer.state = payload.state.strip()
    if payload.pincode is not None and payload.pincode.strip():
        farmer.pincode = payload.pincode.strip()

    farmer.location = f"{farmer.address or 'Farm Gate'}, {farmer.state or 'West Bengal'} ({farmer.pincode or ''})"
    try:
        db.commit()
        db.refresh(farmer)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update farmer: {str(e)}")

    return {
        "status": "success",
        "message": f"Farmer #{farmer.id} ({farmer.name}) updated successfully.",
        "farmer": {
            "id": farmer.id,
            "name": farmer.name,
            "phone_number": farmer.contact,
            "address": farmer.address,
            "state": farmer.state,
            "pincode": farmer.pincode,
            "location": farmer.location
        }
    }


@router.delete("/farmers/{farmer_id}", response_model=Dict[str, Any])
def delete_admin_farmer(
    farmer_id: int,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """
    Admin & Owner: Removes a farmer and their listed supplies from the platform.
    Both regular Admin and Super Admin (Owner) are fully authorized.
    """
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found.")

    f_name = farmer.name
    try:
        # Delete associated supplies and order_items
        db.query(Supply).filter(Supply.farmer_id == farmer_id).delete()
        db.query(OrderItem).filter(OrderItem.farmer_id == farmer_id).delete()
        db.delete(farmer)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete farmer: {str(e)}")

    return {
        "status": "success",
        "message": f"Farmer '{f_name}' (ID: #{farmer_id}) and produce listings removed successfully."
    }


@router.get("/buyers", response_model=List[BuyerOut])
def get_admin_buyers(
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """Admin & Owner: Lists all registered buyers and wholesale enterprises."""
    return db.query(Buyer).order_by(Buyer.created_at.desc()).all()


@router.put("/buyers/{buyer_id}", response_model=Dict[str, Any])
@router.patch("/buyers/{buyer_id}", response_model=Dict[str, Any])
def update_admin_buyer(
    buyer_id: int,
    payload: BuyerUpdateRequest,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """
    Admin & Owner: Modifies details of a registered wholesale buyer.
    Both regular Admin and Super Admin (Owner) are fully authorized.
    """
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found.")

    if payload.name is not None and payload.name.strip():
        buyer.name = payload.name.strip()
    if payload.phone_number is not None and payload.phone_number.strip():
        buyer.phone_number = payload.phone_number.strip()
    if payload.address is not None and payload.address.strip():
        buyer.address = payload.address.strip()
    if payload.city is not None:
        buyer.city = payload.city.strip()
    if payload.state is not None and payload.state.strip():
        buyer.state = payload.state.strip()
    if payload.pincode is not None and payload.pincode.strip():
        buyer.pincode = payload.pincode.strip()

    try:
        db.commit()
        db.refresh(buyer)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update buyer: {str(e)}")

    return {
        "status": "success",
        "message": f"Buyer #{buyer.id} ({buyer.name}) updated successfully.",
        "buyer": {
            "id": buyer.id,
            "name": buyer.name,
            "phone_number": buyer.phone_number,
            "address": buyer.address,
            "city": buyer.city,
            "state": buyer.state,
            "pincode": buyer.pincode
        }
    }


@router.delete("/buyers/{buyer_id}", response_model=Dict[str, Any])
def delete_admin_buyer(
    buyer_id: int,
    db: Session = Depends(get_db),
    claims: Dict[str, Any] = Depends(require_admin)
):
    """
    Admin & Owner: Removes a wholesale buyer from the platform.
    Both regular Admin and Super Admin (Owner) are fully authorized.
    """
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found.")

    b_name = buyer.name
    try:
        # Clean associated demands
        db.query(Demand).filter(Demand.buyer_name == b_name).delete()
        # Clean associated orders and items
        buyer_orders = db.query(Order).filter(Order.buyer_name == b_name).all()
        for o in buyer_orders:
            db.query(OrderItem).filter(OrderItem.order_id == o.id).delete()
            db.delete(o)
        db.delete(buyer)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete buyer: {str(e)}")

    return {
        "status": "success",
        "message": f"Buyer '{b_name}' (ID: #{buyer_id}) removed successfully."
    }


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
            "commodity": p.name,
            "product_name": p.name,
            "category": p.category,
            "quantity_kg": s.quantity,
            "quantity_left_kg": s.quantity,
            "quantity_ordered_kg": s.cleared_quantity or 0.0,
            "price_per_kg": s.expected_price,
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
        prod_name = product.name if product else "Produce"
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
            "order_code": o.order_number,
            "buyer_name": o.buyer_name,
            "product_id": o.product_id,
            "product_name": prod_name,
            "commodity": prod_name,
            "total_quantity_kg": o.total_quantity,
            "total_quantity": o.total_quantity,
            "agreed_price_per_kg": o.agreed_price_per_kg,
            "total_procurement_cost": o.total_procurement_cost,
            "total_cost": o.total_procurement_cost,
            "logistics_cost": o.logistics_cost or 0.0,
            "grand_total": round(o.total_procurement_cost + (o.logistics_cost or 0.0), 2),
            "estimated_distance_km": o.estimated_distance_km or 0.0,
            "total_distance_km": o.estimated_distance_km or 0.0,
            "status": o.status,
            "created_at": o.created_at.strftime("%d %b %Y, %I:%M %p") if o.created_at else "",
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
    total_admins = db.query(Admin).filter(Admin.role == "ADMIN").count()
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

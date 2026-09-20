"""
FarmBuy AI — Zero-Data-Loss SQLite to PostgreSQL Migration Utility
Usage:
    python migrate_sqlite_to_postgres.py [optional_postgresql_database_url]
Or set DATABASE_URL environment variable and run:
    python migrate_sqlite_to_postgres.py
"""
import os
import sys
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, IS_SQLITE
from app.models import Product, Farmer, Buyer, Supply, Demand, DemandHistory, Order, OrderItem, Admin

def migrate():
    print("=" * 70)
    print("FARMBUY AI — SQLITE TO POSTGRESQL PRODUCTION MIGRATION")
    print("=" * 70)

    # 1. Source SQLite
    sqlite_path = os.path.join(current_dir, "agriconnect.db")
    if not os.path.exists(sqlite_path):
        print(f"[-] SQLite database file not found at: {sqlite_path}")
        print("[!] Nothing to migrate.")
        return

    sqlite_url = f"sqlite:///{sqlite_path.replace(os.sep, '/')}"
    print(f"[*] Source Database: {sqlite_url}")
    src_engine = create_engine(sqlite_url)
    SrcSession = sessionmaker(bind=src_engine)
    src_db = SrcSession()

    # 2. Target PostgreSQL
    target_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DATABASE_URL")
    if not target_url:
        print("[-] Target DATABASE_URL not provided.")
        print("[!] Usage: python migrate_sqlite_to_postgres.py <postgresql_url>")
        print("[!] Or set the DATABASE_URL environment variable.")
        return

    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql://", 1)

    print(f"[*] Target Database: {target_url.split('@')[-1] if '@' in target_url else target_url}")
    pg_connect_args = {"sslmode": "prefer"} if "sslmode" not in target_url else {}
    tgt_engine = create_engine(target_url, pool_pre_ping=True, connect_args=pg_connect_args)
    TgtSession = sessionmaker(bind=tgt_engine)

    # Create all schema tables on target if not present
    Base.metadata.create_all(bind=tgt_engine)
    tgt_db = TgtSession()

    try:
        # A. Products
        prods = src_db.query(Product).all()
        print(f"[*] Migrating {len(prods)} Products...")
        for p in prods:
            if not tgt_db.query(Product).filter(Product.name == p.name).first():
                tgt_db.add(Product(
                    name=p.name, category=p.category, unit=p.unit,
                    mandi_benchmark_price=p.mandi_benchmark_price, perishability_days=p.perishability_days
                ))
        tgt_db.commit()

        # B. Admins
        admins = src_db.query(Admin).all()
        print(f"[*] Migrating {len(admins)} Admin accounts...")
        for a in admins:
            if not tgt_db.query(Admin).filter(Admin.admin_user_id == a.admin_user_id).first():
                tgt_db.add(Admin(
                    name=a.name, admin_user_id=a.admin_user_id, password_hash=a.password_hash,
                    role=a.role, is_active=a.is_active, created_at=a.created_at
                ))
        tgt_db.commit()

        # C. Farmers
        farmers = src_db.query(Farmer).all()
        print(f"[*] Migrating {len(farmers)} Farmers...")
        farmer_id_map = {}
        for f in farmers:
            existing_f = tgt_db.query(Farmer).filter(Farmer.contact == f.contact).first()
            if not existing_f:
                new_f = Farmer(
                    name=f.name, address=f.address, location=f.location, pincode=f.pincode,
                    state=f.state, latitude=f.latitude, longitude=f.longitude, contact=f.contact,
                    rating=f.rating, farm_size_acres=f.farm_size_acres
                )
                tgt_db.add(new_f)
                tgt_db.commit()
                tgt_db.refresh(new_f)
                farmer_id_map[f.id] = new_f.id
            else:
                farmer_id_map[f.id] = existing_f.id

        # D. Buyers
        buyers = src_db.query(Buyer).all()
        print(f"[*] Migrating {len(buyers)} Buyers...")
        for b in buyers:
            if not tgt_db.query(Buyer).filter(Buyer.phone_number == b.phone_number).first():
                tgt_db.add(Buyer(
                    name=b.name, address=b.address, city=b.city,
                    phone_number=b.phone_number, pincode=b.pincode, state=b.state,
                    created_at=b.created_at
                ))
        tgt_db.commit()

        # E. Supplies
        supplies = src_db.query(Supply).all()
        print(f"[*] Migrating {len(supplies)} Produce Supplies...")
        for s in supplies:
            target_f_id = farmer_id_map.get(s.farmer_id, s.farmer_id)
            tgt_db.add(Supply(
                farmer_id=target_f_id, product_id=s.product_id, quantity=s.quantity,
                cleared_quantity=s.cleared_quantity, initial_quantity=s.initial_quantity,
                expected_price=s.expected_price, quality_grade=s.quality_grade,
                available_date=s.available_date, harvest_date=s.harvest_date
            ))
        tgt_db.commit()

        # F. Orders & Order Items
        orders = src_db.query(Order).all()
        print(f"[*] Migrating {len(orders)} Orders...")
        for o in orders:
            existing_o = tgt_db.query(Order).filter(Order.order_number == o.order_number).first()
            if not existing_o:
                new_o = Order(
                    order_number=o.order_number, buyer_name=o.buyer_name, product_id=o.product_id,
                    total_quantity=o.total_quantity, agreed_price_per_kg=o.agreed_price_per_kg,
                    total_procurement_cost=o.total_procurement_cost, estimated_distance_km=o.estimated_distance_km,
                    logistics_cost=o.logistics_cost, status=o.status,
                    collection_route_json=o.collection_route_json, created_at=o.created_at
                )
                tgt_db.add(new_o)
                tgt_db.commit()
                tgt_db.refresh(new_o)

                for it in o.items:
                    tgt_db.add(OrderItem(
                        order_id=new_o.id,
                        farmer_id=farmer_id_map.get(it.farmer_id, it.farmer_id),
                        allocated_quantity=it.allocated_quantity,
                        price_per_kg=it.price_per_kg,
                        subtotal=it.subtotal
                    ))
                tgt_db.commit()

        print("\n[SUCCESS] Migration completed successfully!")
        print(f"[*] PostgreSQL Products: {tgt_db.query(Product).count()}")
        print(f"[*] PostgreSQL Farmers:  {tgt_db.query(Farmer).count()}")
        print(f"[*] PostgreSQL Buyers:   {tgt_db.query(Buyer).count()}")
        print(f"[*] PostgreSQL Supplies: {tgt_db.query(Supply).count()}")
        print(f"[*] PostgreSQL Orders:   {tgt_db.query(Order).count()}")
        print(f"[*] PostgreSQL Admins:   {tgt_db.query(Admin).count()}")
        print("=" * 70)

    except Exception as err:
        tgt_db.rollback()
        print(f"\n[ERROR] Migration failed: {err}")
        raise
    finally:
        src_db.close()
        tgt_db.close()

if __name__ == "__main__":
    migrate()

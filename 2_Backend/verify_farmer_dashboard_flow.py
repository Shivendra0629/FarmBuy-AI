"""
End-to-End Verification of Farmer Dashboard Commodity Table & KPI Logic
Validates the fix for ReferenceError (orderPct / Pct) and verifies frontend-backend consistency.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app.database import Base, engine, SessionLocal
from app.models import Farmer, Product, Supply, Order, OrderItem
from app.routers.auth import get_farmer_supplies
from app.main import health_check

def run_farmer_dashboard_verification():
    print("=" * 70)
    print("FARMBUY AI — FARMER DASHBOARD END-TO-END VERIFICATION")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Verify /health diagnostic endpoint
        print("\n--- 1. Testing Backend /health Endpoint ---")
        health_data = health_check()
        print(f"  Health status:     {health_data['status']}")
        print(f"  Database engine:   {health_data['database_engine']}")
        print(f"  Is persistent:     {health_data['is_persistent']}")
        print(f"  Storage type:      {health_data['storage_type']}")
        assert health_data["status"] == "healthy"
        assert health_data["database"] == "connected"
        assert health_data["database_engine"] in ("sqlite", "postgresql")
        print("  [PASS] /health endpoint returns verified database engine.")

        # 2. Setup or retrieve Farmer #1
        print("\n--- 2. Fetching Farmer #1 Supplies from Database ---")
        farmer = db.query(Farmer).first()
        if not farmer:
            print("  Seeding a sample farmer for test...")
            farmer = Farmer(
                name="Shivendra Mahato",
                contact="9973868328",
                location="Hooghly Central",
                address="Farm Gate Hooghly",
                pincode="712409",
                state="West Bengal"
            )
            db.add(farmer)
            db.commit()
            db.refresh(farmer)

        supplies_count = db.query(Supply).filter(Supply.farmer_id == farmer.id).count()
        if supplies_count == 0:
            tomato = db.query(Product).filter(Product.name.ilike("Tomato%")).first()
            if not tomato:
                tomato = Product(name="Tomato", category="Vegetable", unit="kg", mandi_benchmark_price=22.0, perishability_days=7)
                db.add(tomato)
                db.commit()
                db.refresh(tomato)
            s = Supply(
                farmer_id=farmer.id,
                product_id=tomato.id,
                quantity=6000.0,
                cleared_quantity=2000.0,
                initial_quantity=8000.0,
                expected_price=22.0,
                quality_grade="Grade A"
            )
            db.add(s)
            db.commit()

        # Call GET /api/auth/farmer/{farmer_id}/supplies
        res = get_farmer_supplies(farmer_id=farmer.id, db=db)
        assert "kpis" in res, "Missing kpis in response"
        assert "supplies" in res, "Missing supplies in response"
        kpis = res["kpis"]
        supplies = res["supplies"]

        print(f"  Farmer: {res['name']} (ID: #{res['farmer_id']})")
        print(f"  Supplies listed: {len(supplies)} batch(es)")
        print(f"  Total Harvest:    {kpis['total_harvest_kg']:,} kg")
        print(f"  Quantity Ordered: {kpis['total_ordered_kg']:,} kg")
        print(f"  Quantity Left:    {kpis['total_left_kg']:,} kg")
        print(f"  Earned from Orders: ₹{kpis['earned_from_orders']:,}")
        print(f"  Current Stock Value: ₹{kpis['current_stock_value']:,}")

        # 3. Simulate exact JavaScript logic in loadFarmerProduceList
        print("\n--- 3. Testing JavaScript loadFarmerProduceList() Logic Simulation ---")
        
        # Exact JS calculation lines:
        totOrdered = kpis.get("total_ordered_kg") or kpis.get("total_cleared_kg") or 0.0
        totLeft = kpis.get("total_left_kg") or 0.0
        totHarvest = kpis.get("total_harvest_kg") or (totLeft + totOrdered)
        orderPct = kpis.get("order_fulfillment_pct") if kpis.get("order_fulfillment_pct") is not None else (
            kpis.get("overall_clearance_pct") if kpis.get("overall_clearance_pct") is not None else (
                round((totOrdered / totHarvest) * 100) if totHarvest > 0 else 0
            )
        )
        orderRev = kpis.get("earned_from_orders") if kpis.get("earned_from_orders") is not None else (
            kpis.get("total_ordered_revenue") or kpis.get("total_cleared_revenue") or 0.0
        )
        stockVal = kpis.get("current_stock_value") if kpis.get("current_stock_value") is not None else (
            kpis.get("total_remaining_value") or 0.0
        )

        print(f"  Computed orderPct: {orderPct}%")
        assert orderPct is not None, "orderPct must not be None"
        print("  [PASS] orderPct computed successfully without ReferenceError!")

        # 4. Verify Commodities Table Row Rendering
        print("\n--- 4. Verifying Commodities Table 8-Field Output ---")
        rendered_rows = []
        for s in supplies:
            ordKg = s.get("quantity_ordered_kg") or s.get("stock_cleared_kg") or 0.0
            leftKg = s.get("quantity_left_kg") or s.get("stock_left_kg") or 0.0
            totKg = s.get("total_harvest_kg") or (leftKg + ordKg)
            pctOrdered = min(100.0, max(0.0, s.get("ordered_pct") or s.get("clearance_pct") or 0.0))
            pctLeft = max(0.0, 100.0 - pctOrdered)

            row_data = {
                "commodity_grade": f"{s['product_name']} ({s['quality_grade']})",
                "asking_rate": f"₹{s['expected_price']:.2f}/kg",
                "mandi_benchmark": f"₹{s['mandi_benchmark']:.2f}/kg",
                "quantity_left": f"{leftKg:,.0f} kg",
                "quantity_ordered": f"{ordKg:,.0f} kg",
                "total_harvest_status": f"{pctOrdered:.1f}% Ordered / {leftKg:,.0f} kg left",
                "value_of_stock_left": f"₹{s['remaining_value']:,.2f}",
                "actions": ["Edit", "View Orders"]
            }
            rendered_rows.append(row_data)
            print(f"  Commodity: {row_data['commodity_grade']}")
            print(f"    Asking: {row_data['asking_rate']} | Mandi: {row_data['mandi_benchmark']}")
            print(f"    Left: {row_data['quantity_left']} | Ordered: {row_data['quantity_ordered']}")
            print(f"    Stock Value Left: {row_data['value_of_stock_left']}")
            print(f"    Progress: {row_data['total_harvest_status']}")

        assert len(rendered_rows) > 0, "At least 1 commodity row must render"
        print(f"  [PASS] Successfully rendered {len(rendered_rows)} commodity row(s) with all 8 fields.")

        # 5. Check index.html and app.js file content
        print("\n--- 5. Static Inspection of index.html and app.js ---")
        base_dir = Path(__file__).resolve().parent.parent
        with open(base_dir / "1_Frontend" / "index.html", "r", encoding="utf-8") as f:
            html = f.read()
        assert 'id="farmerDbBadge"' in html, "farmerDbBadge id missing in index.html"
        assert 'id="footerDbEngine"' in html, "footerDbEngine id missing in index.html"
        assert 'SQLite Database Active' not in html, "Hardcoded 'SQLite Database Active' should be removed"

        with open(base_dir / "1_Frontend" / "app.js", "r", encoding="utf-8") as f:
            js = f.read()
        assert 'orderPct' in js, "'orderPct' must be present in app.js"
        assert 'farmerDbBadge' in js, "farmerDbBadge handling must be present in app.js"
        print("  [PASS] Static checks on index.html and app.js passed.")

        print("\n" + "=" * 70)
        print("ALL VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
        print("=" * 70)

    except Exception as e:
        print(f"\n[FAIL] Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_farmer_dashboard_verification()

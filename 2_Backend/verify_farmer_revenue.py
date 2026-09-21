"""
Authoritative Automated Verification Script for Farmer Revenue & Valuation Logic.
Verifies all 8 user-specified scenarios directly against the database and router endpoints.
"""
import sys
import os

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from datetime import datetime, date
from app.database import Base, engine, SessionLocal
from app.models import Farmer, Product, Supply, Order, OrderItem
from app.routers.auth import get_farmer_supplies, get_farmer_orders
from app.routers.supply_intelligence import cancel_order

def run_tests():
    print("=" * 70)
    print("FARMBUY AI — AUTHORITATIVE REVENUE & VALUATION LOGIC VERIFICATION")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    passed_tests = 0
    total_tests = 8

    try:
        # Setup: Ensure Tomato product exists
        tomato = db.query(Product).filter(Product.name.ilike("Tomato%")).first()
        if not tomato:
            tomato = Product(
                name="Tomato",
                category="Vegetable",
                unit="kg",
                mandi_benchmark_price=22.0,
                perishability_days=7
            )
            db.add(tomato)
            db.commit()
            db.refresh(tomato)

        # Cleanup any previous test farmer with contact 9899999999
        old_farmer = db.query(Farmer).filter(Farmer.contact == "9899999999").first()
        if old_farmer:
            # Clean up old orders
            items = db.query(OrderItem).filter(OrderItem.farmer_id == old_farmer.id).all()
            for it in items:
                ord_id = it.order_id
                db.delete(it)
                db.query(Order).filter(Order.id == ord_id).delete()
            db.query(Supply).filter(Supply.farmer_id == old_farmer.id).delete()
            db.delete(old_farmer)
            db.commit()

        # =====================================================================
        # SCENARIO 1: Initial Farmer Registration with 8,000 kg Tomato @ ₹22/kg (No orders)
        # =====================================================================
        print("\n--- SCENARIO 1: Initial Produce Listing (8,000 kg @ ₹22/kg, No Orders) ---")
        test_farmer = Farmer(
            name="Ramesh Verification Farmer",
            contact="9899999999",
            location="Hooghly Central",
            address="Hooghly Farm Gate",
            pincode="712101",
            state="West Bengal"
        )
        db.add(test_farmer)
        db.commit()
        db.refresh(test_farmer)

        supply = Supply(
            farmer_id=test_farmer.id,
            product_id=tomato.id,
            quantity=8000.0,
            cleared_quantity=0.0,
            initial_quantity=8000.0,
            expected_price=22.0,
            quality_grade="Grade A",
            available_date=date.today(),
            harvest_date=date.today()
        )
        db.add(supply)
        db.commit()
        db.refresh(supply)

        res1 = get_farmer_supplies(farmer_id=test_farmer.id, db=db)
        kpis1 = res1["kpis"]
        sup1 = res1["supplies"][0]

        print(f"  Earned from Orders: ₹{kpis1['earned_from_orders']:,} (Expected: ₹0)")
        print(f"  Quantity Ordered:   {kpis1['total_ordered_kg']:,} kg (Expected: 0 kg)")
        print(f"  Quantity Left:      {kpis1['total_left_kg']:,} kg (Expected: 8,000 kg)")
        print(f"  Current Stock Value:₹{kpis1['current_stock_value']:,} (Expected: ₹1,76,000)")

        assert kpis1["earned_from_orders"] == 0.0, f"Expected earned 0, got {kpis1['earned_from_orders']}"
        assert kpis1["total_ordered_kg"] == 0.0, f"Expected ordered 0, got {kpis1['total_ordered_kg']}"
        assert kpis1["total_left_kg"] == 8000.0, f"Expected left 8000, got {kpis1['total_left_kg']}"
        assert kpis1["current_stock_value"] == 176000.0, f"Expected stock val 176000, got {kpis1['current_stock_value']}"
        assert sup1["remaining_value"] == 176000.0
        assert sup1["ordered_revenue"] == 0.0
        print("  [PASS] Scenario 1 Passed Successfully.")
        passed_tests += 1

        # =====================================================================
        # SCENARIO 2: Order Placed (2,000 kg Tomato @ ₹22/kg)
        # =====================================================================
        print("\n--- SCENARIO 2: Buyer Places Order (2,000 kg @ ₹22/kg = ₹44,000) ---")
        order1 = Order(
            order_number=f"ORD-TEST-{int(datetime.now().timestamp())}",
            buyer_name="Reliance Fresh Kolkata Depot",
            product_id=tomato.id,
            total_quantity=2000.0,
            agreed_price_per_kg=22.0,
            total_procurement_cost=44000.0,
            estimated_distance_km=15.0,
            logistics_cost=270.0,
            status="CONFIRMED",
            created_at=datetime.now()
        )
        db.add(order1)
        db.flush()

        item1 = OrderItem(
            order_id=order1.id,
            farmer_id=test_farmer.id,
            allocated_quantity=2000.0,
            price_per_kg=22.0,
            subtotal=44000.0
        )
        db.add(item1)

        # Deduct from supply
        supply.quantity = 8000.0 - 2000.0
        supply.cleared_quantity = 2000.0
        db.commit()

        res2 = get_farmer_supplies(farmer_id=test_farmer.id, db=db)
        kpis2 = res2["kpis"]
        sup2 = res2["supplies"][0]

        print(f"  Earned from Orders: ₹{kpis2['earned_from_orders']:,} (Expected: ₹44,000)")
        print(f"  Quantity Ordered:   {kpis2['total_ordered_kg']:,} kg (Expected: 2,000 kg)")
        print(f"  Quantity Left:      {kpis2['total_left_kg']:,} kg (Expected: 6,000 kg)")
        print(f"  Current Stock Value:₹{kpis2['current_stock_value']:,} (Expected: ₹1,32,000)")

        assert kpis2["earned_from_orders"] == 44000.0, f"Expected 44000, got {kpis2['earned_from_orders']}"
        assert kpis2["total_ordered_kg"] == 2000.0, f"Expected 2000, got {kpis2['total_ordered_kg']}"
        assert kpis2["total_left_kg"] == 6000.0, f"Expected 6000, got {kpis2['total_left_kg']}"
        assert kpis2["current_stock_value"] == 132000.0, f"Expected 132000, got {kpis2['current_stock_value']}"
        assert sup2["remaining_value"] == 132000.0
        assert sup2["ordered_revenue"] == 44000.0
        print("  [PASS] Scenario 2 Passed Successfully.")
        passed_tests += 1

        # =====================================================================
        # SCENARIO 3: Page Refresh Simulation (Independent Session Fetch)
        # =====================================================================
        print("\n--- SCENARIO 3: Page Refresh Simulation (Fresh Database Session) ---")
        db.close()
        db_refresh = SessionLocal()
        res3 = get_farmer_supplies(farmer_id=test_farmer.id, db=db_refresh)
        kpis3 = res3["kpis"]

        print(f"  Earned from Orders: ₹{kpis3['earned_from_orders']:,} (Persisted from DB)")
        print(f"  Current Stock Value:₹{kpis3['current_stock_value']:,} (Persisted from DB)")

        assert kpis3["earned_from_orders"] == 44000.0
        assert kpis3["total_ordered_kg"] == 2000.0
        assert kpis3["total_left_kg"] == 6000.0
        assert kpis3["current_stock_value"] == 132000.0
        print("  [PASS] Scenario 3 Passed (Zero data loss across simulated page refresh).")
        passed_tests += 1

        # =====================================================================
        # SCENARIO 4: Logout / Login Simulation
        # =====================================================================
        print("\n--- SCENARIO 4: Logout / Login Simulation ---")
        db_refresh.close()
        db_login = SessionLocal()
        # Simulate re-authenticating and loading farmer dashboard
        res4 = get_farmer_supplies(farmer_id=test_farmer.id, db=db_login)
        kpis4 = res4["kpis"]

        assert kpis4["earned_from_orders"] == 44000.0
        assert kpis4["total_left_kg"] == 6000.0
        assert kpis4["current_stock_value"] == 132000.0
        print("  [PASS] Scenario 4 Passed (State fully restored from persistent database).")
        passed_tests += 1

        # =====================================================================
        # SCENARIO 5: Multi-Device / Admin Inspection Simulation
        # =====================================================================
        print("\n--- SCENARIO 5: Multi-Device / Concurrent Client Simulation ---")
        db_device2 = SessionLocal()
        res5 = get_farmer_supplies(farmer_id=test_farmer.id, db=db_device2)
        kpis5 = res5["kpis"]

        assert kpis5["earned_from_orders"] == 44000.0
        assert kpis5["total_left_kg"] == 6000.0
        assert kpis5["current_stock_value"] == 132000.0
        print("  [PASS] Scenario 5 Passed (Multi-device queries return exact authoritative values).")
        passed_tests += 1

        # =====================================================================
        # SCENARIO 6: Order Cancellation Reversal
        # =====================================================================
        print("\n--- SCENARIO 6: Order Cancellation (Revenue Reversal & Stock Restored) ---")
        cancel_res = cancel_order(order_id=order1.id, db=db_login)
        print(f"  Cancellation Result: {cancel_res['message']}")

        res6 = get_farmer_supplies(farmer_id=test_farmer.id, db=db_login)
        kpis6 = res6["kpis"]
        sup6 = res6["supplies"][0]

        print(f"  Earned from Orders: ₹{kpis6['earned_from_orders']:,} (Expected: ₹0)")
        print(f"  Quantity Ordered:   {kpis6['total_ordered_kg']:,} kg (Expected: 0 kg)")
        print(f"  Quantity Left:      {kpis6['total_left_kg']:,} kg (Expected: 8,000 kg)")
        print(f"  Current Stock Value:₹{kpis6['current_stock_value']:,} (Expected: ₹1,76,000)")

        assert kpis6["earned_from_orders"] == 0.0, f"Expected 0, got {kpis6['earned_from_orders']}"
        assert kpis6["total_ordered_kg"] == 0.0, f"Expected 0, got {kpis6['total_ordered_kg']}"
        assert kpis6["total_left_kg"] == 8000.0, f"Expected 8000, got {kpis6['total_left_kg']}"
        assert kpis6["current_stock_value"] == 176000.0, f"Expected 176000, got {kpis6['current_stock_value']}"
        assert sup6["remaining_value"] == 176000.0
        assert sup6["ordered_revenue"] == 0.0
        print("  [PASS] Scenario 6 Passed (Cancelled order completely reversed, stock restored).")
        passed_tests += 1

        # =====================================================================
        # SCENARIO 7: Re-ordering after Cancellation (No Double Counting)
        # =====================================================================
        print("\n--- SCENARIO 7: Re-ordering After Cancellation (2,000 kg @ ₹22/kg) ---")
        order2 = Order(
            order_number=f"ORD-REORDER-{int(datetime.now().timestamp())}",
            buyer_name="Spencer's Retail Hub",
            product_id=tomato.id,
            total_quantity=2000.0,
            agreed_price_per_kg=22.0,
            total_procurement_cost=44000.0,
            estimated_distance_km=10.0,
            logistics_cost=180.0,
            status="CONFIRMED",
            created_at=datetime.now()
        )
        db_login.add(order2)
        db_login.flush()

        item2 = OrderItem(
            order_id=order2.id,
            farmer_id=test_farmer.id,
            allocated_quantity=2000.0,
            price_per_kg=22.0,
            subtotal=44000.0
        )
        db_login.add(item2)

        s_rec = db_login.query(Supply).filter(Supply.id == supply.id).first()
        s_rec.quantity = 8000.0 - 2000.0
        s_rec.cleared_quantity = 2000.0
        db_login.commit()

        res7 = get_farmer_supplies(farmer_id=test_farmer.id, db=db_login)
        kpis7 = res7["kpis"]

        print(f"  Earned from Orders: ₹{kpis7['earned_from_orders']:,} (Expected: ₹44,000)")
        print(f"  Quantity Left:      {kpis7['total_left_kg']:,} kg (Expected: 6,000 kg)")
        print(f"  Current Stock Value:₹{kpis7['current_stock_value']:,} (Expected: ₹1,32,000)")

        assert kpis7["earned_from_orders"] == 44000.0
        assert kpis7["total_ordered_kg"] == 2000.0
        assert kpis7["total_left_kg"] == 6000.0
        assert kpis7["current_stock_value"] == 132000.0
        print("  [PASS] Scenario 7 Passed (No duplicate counting with cancelled order).")
        passed_tests += 1

        # =====================================================================
        # SCENARIO 8: Multi-Order Aggregation (Second Order: 1,000 kg @ ₹22/kg)
        # =====================================================================
        print("\n--- SCENARIO 8: Multi-Order Aggregation (+1,000 kg @ ₹22/kg = ₹22,000) ---")
        order3 = Order(
            order_number=f"ORD-MULTI-{int(datetime.now().timestamp())}",
            buyer_name="BigBasket Fulfillment Hub",
            product_id=tomato.id,
            total_quantity=1000.0,
            agreed_price_per_kg=22.0,
            total_procurement_cost=22000.0,
            estimated_distance_km=20.0,
            logistics_cost=360.0,
            status="CONFIRMED",
            created_at=datetime.now()
        )
        db_login.add(order3)
        db_login.flush()

        item3 = OrderItem(
            order_id=order3.id,
            farmer_id=test_farmer.id,
            allocated_quantity=1000.0,
            price_per_kg=22.0,
            subtotal=22000.0
        )
        db_login.add(item3)

        s_rec = db_login.query(Supply).filter(Supply.id == supply.id).first()
        s_rec.quantity = 6000.0 - 1000.0
        s_rec.cleared_quantity = 3000.0
        db_login.commit()

        res8 = get_farmer_supplies(farmer_id=test_farmer.id, db=db_login)
        kpis8 = res8["kpis"]
        sup8 = res8["supplies"][0]

        orders_summary = get_farmer_orders(farmer_id=test_farmer.id, db=db_login)

        print(f"  Total Ordered:      {kpis8['total_ordered_kg']:,} kg (Expected: 3,000 kg)")
        print(f"  Quantity Left:      {kpis8['total_left_kg']:,} kg (Expected: 5,000 kg)")
        print(f"  Total Earned:       ₹{kpis8['earned_from_orders']:,} (Expected: ₹66,000)")
        print(f"  Current Stock Value:₹{kpis8['current_stock_value']:,} (Expected: ₹1,10,000)")
        print(f"  Orders History Rev: ₹{orders_summary['total_order_revenue']:,} (Active orders only)")

        assert kpis8["total_ordered_kg"] == 3000.0, f"Expected 3000, got {kpis8['total_ordered_kg']}"
        assert kpis8["total_left_kg"] == 5000.0, f"Expected 5000, got {kpis8['total_left_kg']}"
        assert kpis8["earned_from_orders"] == 66000.0, f"Expected 66000, got {kpis8['earned_from_orders']}"
        assert kpis8["current_stock_value"] == 110000.0, f"Expected 110000, got {kpis8['current_stock_value']}"
        assert sup8["remaining_value"] == 110000.0
        assert sup8["ordered_revenue"] == 66000.0
        assert orders_summary["total_order_revenue"] == 66000.0
        print("  [PASS] Scenario 8 Passed (Multi-orders properly aggregated without overwrite).")
        passed_tests += 1

        # Clean up test records
        db_login.query(OrderItem).filter(OrderItem.farmer_id == test_farmer.id).delete()
        db_login.query(Order).filter(Order.id.in_([order1.id, order2.id, order3.id])).delete()
        db_login.query(Supply).filter(Supply.farmer_id == test_farmer.id).delete()
        db_login.query(Farmer).filter(Farmer.id == test_farmer.id).delete()
        db_login.commit()

        print("\n" + "=" * 70)
        print(f"VERIFICATION COMPLETE: {passed_tests}/{total_tests} SCENARIOS PASSED!")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"\n[FAIL] Exception encountered: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()

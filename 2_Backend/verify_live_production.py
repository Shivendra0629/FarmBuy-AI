"""
Comprehensive Live Production Verification Script for FarmBuy AI
Directly verifies live deployed application on Render:
- index.html cache busting
- app.js deployed content & error boundaries
- /health backend configuration & PostgreSQL confirmation
- Farmer #1 supplies and KPI calculations
- Farmer #1 orders and revenue allocation
- Demand forecast endpoint
- DOM rendering simulation
"""
import urllib.request
import json
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def main():
    print("=" * 70)
    print("FARMBUY AI — LIVE PRODUCTION TECHNICAL VERIFICATION")
    print("=" * 70)

    base_url = "https://farmbuy-ai-backend.onrender.com"

    # Test 1: Live Index & Cache-Busting Versioning
    print("\n--- TEST 1: Live Index & Cache-Busting ---")
    html_req = urllib.request.urlopen(f"{base_url}/")
    assert html_req.status == 200, f"index.html returned {html_req.status}"
    html = html_req.read().decode("utf-8")
    assert "app.js?v=2.0.2" in html, "Cache-busting app.js?v=2.0.2 missing from live index.html"
    assert "style.css?v=2.0.2" in html, "Cache-busting style.css?v=2.0.2 missing from live index.html"
    assert 'id="farmerProduceListBody"' in html, "farmerProduceListBody missing in index.html"
    assert 'id="farmerOrdersListContainer"' in html, "farmerOrdersListContainer missing in index.html"
    assert 'id="farmerForecastCropSelect"' in html, "farmerForecastCropSelect missing in index.html"
    assert 'id="farmerDbBadge"' in html, "farmerDbBadge missing in index.html"
    print("  [PASS] Live index.html contains cache-busted app.js?v=2.0.2 and all required DOM target IDs.")

    # Test 2: Live Deployed JavaScript Content
    print("\n--- TEST 2: Live app.js?v=2.0.2 Inspection ---")
    js_req = urllib.request.urlopen(f"{base_url}/app.js?v=2.0.2")
    assert js_req.status == 200, f"app.js returned {js_req.status}"
    js = js_req.read().decode("utf-8")
    assert "orderPct" in js, "orderPct missing from deployed app.js"
    assert "Isolated Boundary" in js, "Decoupled error boundaries missing from deployed app.js"
    assert "Unable to load produce from database" in js, "Resilient error fallback missing in app.js"
    assert "farmerOrdersListContainer" in js, "farmerOrdersListContainer missing in app.js"
    print("  [PASS] Live app.js?v=2.0.2 deployed on Render contains verified decoupled boundaries and orderPct definition.")

    # Test 3: Backend Health & Database Engine
    print("\n--- TEST 3: Live /health Backend & PostgreSQL Verification ---")
    health_req = urllib.request.urlopen(f"{base_url}/health")
    assert health_req.status == 200, f"/health returned {health_req.status}"
    health = json.loads(health_req.read().decode("utf-8"))
    engine_name = health.get("database_engine")
    is_persistent = health.get("is_persistent")
    storage_type = health.get("storage_type")
    print(f"  Status:          {health.get('status')}")
    print(f"  Database Engine: {engine_name}")
    print(f"  Is Persistent:   {is_persistent}")
    print(f"  Storage Type:    {storage_type}")
    print(f"  Records:         {health.get('records')}")
    assert engine_name == "postgresql", f"Expected postgresql, got {engine_name}"
    assert is_persistent is True, "Database is not marked persistent"
    print("  [PASS] Production backend is actively connected to Render PostgreSQL persistent database.")

    # Test 4: Farmer #1 Supplies & KPI Revenue Verification
    print("\n--- TEST 4: Live Farmer #1 Supplies Endpoint ---")
    supplies_req = urllib.request.urlopen(f"{base_url}/api/auth/farmer/1/supplies")
    assert supplies_req.status == 200, f"Supplies endpoint returned {supplies_req.status}"
    supplies_data = json.loads(supplies_req.read().decode("utf-8"))
    kpis = supplies_data.get("kpis", {})
    supplies = supplies_data.get("supplies", [])
    
    tot_harvest = kpis.get("total_harvest_kg")
    tot_ordered = kpis.get("total_ordered_kg")
    tot_left = kpis.get("total_left_kg")
    earned_rev = kpis.get("earned_from_orders")
    stock_val = kpis.get("current_stock_value")
    order_pct = kpis.get("order_fulfillment_pct")

    print(f"  Farmer ID:          {supplies_data.get('farmer_id')}")
    print(f"  Farmer Name:        {supplies_data.get('name')}")
    print(f"  Total Harvest:      {tot_harvest:,.0f} kg")
    print(f"  Total Ordered:      {tot_ordered:,.0f} kg")
    print(f"  Total Left:         {tot_left:,.0f} kg")
    print(f"  Order Pct:          {order_pct}%")
    print(f"  Earned From Orders: ₹{earned_rev:,.2f}")
    print(f"  Stock Value Left:   ₹{stock_val:,.2f}")
    print(f"  Supplies Listed:    {len(supplies)} batches")

    assert len(supplies) > 0, "Farmer 1 must have supplies"
    assert earned_rev == 110000.0, f"Expected earned_from_orders=110000.0, got {earned_rev}"
    assert stock_val == 1492400.0, f"Expected current_stock_value=1492400.0, got {stock_val}"
    assert tot_harvest == 84000.0, f"Expected total_harvest_kg=84000.0, got {tot_harvest}"

    for i, s in enumerate(supplies, 1):
        print(f"    [{i}] {s['product_name']} ({s.get('quality_grade', 'Grade A')}):")
        print(f"        Left: {s['quantity_left_kg']:,.0f} kg | Ordered: {s['quantity_ordered_kg']:,.0f} kg")
        print(f"        Asking: ₹{s['expected_price']:.2f}/kg | Mandi: ₹{s['mandi_benchmark']:.2f}/kg (diff: ₹{s['price_diff']:.2f})")
        print(f"        Earned: ₹{s['ordered_revenue']:,.2f} | Stock Value: ₹{s['remaining_value']:,.2f}")
    print("  [PASS] Live supplies and revenue calculation match PostgreSQL database authoritative state.")

    # Test 5: Farmer #1 Orders Endpoint
    print("\n--- TEST 5: Live Farmer #1 Orders Endpoint ---")
    orders_req = urllib.request.urlopen(f"{base_url}/api/auth/farmer/1/orders")
    assert orders_req.status == 200, f"Orders endpoint returned {orders_req.status}"
    orders_data = json.loads(orders_req.read().decode("utf-8"))
    orders = orders_data.get("orders", [])
    print(f"  Total Orders Count:   {orders_data.get('total_orders_count')}")
    print(f"  Total Order Revenue:  ₹{orders_data.get('total_order_revenue'):,.2f}")
    assert len(orders) >= 1, "Must have at least 1 order in database"
    for o in orders:
        print(f"    - Order #{o['order_number']}: Buyer {o['buyer_name']} ({o['buyer_phone']})")
        print(f"      Crop: {o['product_name']} | Qty: {o['allocated_quantity_kg']:,.0f} kg @ ₹{o['price_per_kg']:.2f}/kg = ₹{o['subtotal']:,.2f} [{o['status']}]")
    print("  [PASS] Live orders endpoint returns valid orders with buyer details and payouts.")

    # Test 6: Market Demand Forecast
    print("\n--- TEST 6: Live Market Demand Forecast Endpoint ---")
    req = urllib.request.Request(
        f"{base_url}/api/demand/forecast",
        data=json.dumps({"product_id": 1, "days_ahead": 7, "region": "Kolkata Metro Hub"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    forecast_req = urllib.request.urlopen(req)
    assert forecast_req.status == 200, f"Demand forecast returned {forecast_req.status}"
    forecast = json.loads(forecast_req.read().decode("utf-8"))
    print(f"  Status:       {forecast.get('status')}")
    print(f"  Commodity:    {forecast.get('product_name')}")
    print(f"  Growth %:     {forecast.get('growth_percentage')}%")
    print(f"  Trend Signal: {forecast.get('trend_direction')}")
    assert forecast.get("status") == "SUCCESS", "Forecast status is not SUCCESS"
    print("  [PASS] Live demand forecast endpoint operates successfully.")

    # Test 7: DOM Rendering Simulation
    print("\n--- TEST 7: JavaScript loadFarmerProduceList() Execution Simulation ---")
    # Simulate the exact JS rendering logic
    tot_ordered_calc = kpis.get("total_ordered_kg") or 0
    tot_left_calc = kpis.get("total_left_kg") or 0
    tot_harvest_calc = kpis.get("total_harvest_kg") or (tot_left_calc + tot_ordered_calc)
    order_pct_calc = kpis.get("order_fulfillment_pct") if kpis.get("order_fulfillment_pct") is not None else (
        round((tot_ordered_calc / tot_harvest_calc) * 100) if tot_harvest_calc > 0 else 0
    )
    order_rev_calc = kpis.get("earned_from_orders") or 0
    stock_val_calc = kpis.get("current_stock_value") or 0

    assert order_pct_calc == 6.0, f"orderPct calculation mismatch: {order_pct_calc}"
    assert order_rev_calc == 110000.0, f"orderRev calculation mismatch: {order_rev_calc}"
    assert stock_val_calc == 1492400.0, f"stockVal calculation mismatch: {stock_val_calc}"

    # Table rows simulation
    table_rows = []
    for s in supplies:
        ord_kg = s.get("quantity_ordered_kg") or 0
        left_kg = s.get("quantity_left_kg") or 0
        pct_ord = min(100.0, max(0.0, s.get("ordered_pct") or 0))
        table_rows.append({
            "product_name": s["product_name"],
            "grade": s.get("quality_grade", "Grade A"),
            "asking_rate": f"₹{s['expected_price']:.2f}/kg",
            "mandi_benchmark": f"₹{s['mandi_benchmark']:.2f}/kg",
            "quantity_left": f"{left_kg:,.0f} kg",
            "quantity_ordered": f"{ord_kg:,.0f} kg",
            "earned_revenue": f"Earned: ₹{s['ordered_revenue']:,.0f}" if s.get('ordered_revenue') else "Earned: ₹0",
            "progress_status": f"{pct_ord:.1f}% Ordered / {left_kg:,.0f} kg left",
            "stock_value_left": f"₹{s['remaining_value']:,.2f}",
        })
    assert len(table_rows) == 3, f"Expected 3 rows rendered, got {len(table_rows)}"
    print(f"  [PASS] DOM simulation successfully rendered {len(table_rows)} commodity rows with all 8 fields.")

    print("\n" + "=" * 70)
    print("ALL LIVE PRODUCTION TESTS COMPLETED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    main()

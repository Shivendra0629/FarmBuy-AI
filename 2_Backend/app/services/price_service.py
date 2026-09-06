from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from ..models import Supply, Product, DemandHistory, Farmer


def get_price_insight(
    db: Session,
    product_id: int,
    required_quantity: float = 1000.0
) -> Dict[str, Any]:
    # 1. Product Validation
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Quantity Validation
    if required_quantity is None or required_quantity <= 0:
        raise HTTPException(status_code=400, detail="required_quantity must be greater than 0")

    product_name = product.name
    mandi_benchmark = float(product.mandi_benchmark_price)

    supplies = (
        db.query(Supply)
        .filter(
            Supply.product_id == product_id,
            Supply.expected_price.isnot(None),
            Supply.quantity > 0
        )
        .all()
    )

    if not supplies:
        return {
            "product_id": product_id,
            "product_name": product_name,
            "mandi_benchmark_price": round(mandi_benchmark, 2),
            "lowest_farmer_price": round(mandi_benchmark, 2),
            "average_farmer_price": round(mandi_benchmark, 2),
            "highest_farmer_price": round(mandi_benchmark, 2),
            "historical_price_30d_avg": round(mandi_benchmark, 2),
            "fair_market_band_min": round(mandi_benchmark * 0.92, 2),
            "fair_market_band_max": round(mandi_benchmark * 1.08, 2),
            "recommendation": "No farmer asking prices listed yet; use mandi benchmark price."
        }

    prices = [float(s.expected_price) for s in supplies]
    lowest_price = min(prices)
    highest_price = max(prices)
    average_price = sum(prices) / len(prices)

    # Check 30-day historical average if available
    history = (
        db.query(DemandHistory.average_mandi_price)
        .filter(DemandHistory.product_id == product_id)
        .all()
    )
    hist_avg = sum(h[0] for h in history) / len(history) if history else mandi_benchmark

    fair_band_min = round(min(lowest_price, mandi_benchmark * 0.93), 2)
    fair_band_max = round(max(average_price, mandi_benchmark * 1.05), 2)

    # Calculate price spread percentage relative to Mandi benchmark using the displayed prices
    displayed_mandi = round(mandi_benchmark, 2)
    displayed_avg = round(average_price, 2)
    diff_from_mandi = abs(displayed_mandi - displayed_avg)
    spread_pct = round((diff_from_mandi / max(0.01, displayed_mandi)) * 100.0, 1)

    if displayed_avg <= displayed_mandi:
        recommendation = (
            f"Favorable buyer window: Average farmer asking price (₹{displayed_avg:.2f}/kg) "
            f"is {spread_pct}% below government Mandi benchmark (₹{displayed_mandi:.2f}/kg)."
        )
    else:
        recommendation = (
            f"High demand premium: Average farmer asking price (₹{displayed_avg:.2f}/kg) "
            f"is {spread_pct}% above government Mandi benchmark (₹{displayed_mandi:.2f}/kg). Consider multi-farm volume discounts."
        )

    return {
        "product_id": product_id,
        "product_name": product_name,
        "mandi_benchmark_price": displayed_mandi,
        "lowest_farmer_price": round(lowest_price, 2),
        "average_farmer_price": displayed_avg,
        "highest_farmer_price": round(highest_price, 2),
        "historical_price_30d_avg": round(hist_avg, 2),
        "fair_market_band_min": fair_band_min,
        "fair_market_band_max": fair_band_max,
        "recommendation": recommendation
    }


def simulate_negotiation(
    db: Session,
    product_id: int,
    required_quantity: float,
    target_price: float,
    matched_farmer_ids: List[int]
) -> Dict[str, Any]:
    """
    Evaluates buyer's target price vs farmer expectations and Mandi price signals.
    Generates intelligent counter-offer advice and simulated farmer reception.
    """
    # 1. Product Validation
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Input Validations
    if required_quantity is None or required_quantity <= 0:
        raise HTTPException(status_code=400, detail="required_quantity must be greater than 0")
    if target_price is None or target_price <= 0:
        raise HTTPException(status_code=400, detail="target_price must be greater than 0")
    if not matched_farmer_ids:
        raise HTTPException(status_code=400, detail="matched_farmer_ids list cannot be empty")

    insight = get_price_insight(db, product_id, required_quantity)
    avg_price = insight["average_farmer_price"]
    min_price = insight["lowest_farmer_price"]
    mandi_price = insight["mandi_benchmark_price"]

    # Target price ratio vs average
    ratio = target_price / max(1.0, avg_price)

    farmers = (
        db.query(Farmer)
        .filter(Farmer.id.in_(matched_farmer_ids))
        .all()
    )

    if not farmers:
        raise HTTPException(status_code=404, detail="No farmers found for provided IDs")

    farmer_responses = []

    if ratio >= 0.98:
        likelihood = "HIGH"
        score = 95
        counter_offer = target_price
        savings = (avg_price - target_price) * required_quantity
        strategy_text = (
            f"Offer of ₹{target_price:.2f}/kg is fair and close to asking average (₹{avg_price:.2f}). "
            "High probability of 100% farmer acceptance without procurement delay."
        )
        for f in farmers:
            farmer_responses.append({
                "farmer_id": f.id,
                "farmer_name": f.name,
                "location": f.location,
                "response": "ACCEPTED",
                "message": f"Agrees to supply at ₹{target_price:.2f}/kg immediately.",
                "agreed_price": target_price
            })

    elif ratio >= 0.90:
        likelihood = "MODERATE"
        score = 72
        counter_offer = round(target_price + (avg_price - target_price) * 0.45, 2)
        savings = (avg_price - counter_offer) * required_quantity
        strategy_text = (
            f"Target price ₹{target_price:.2f}/kg is aggressive ({round((1 - ratio) * 100, 1)}% discount). "
            f"AI recommendation: Counter at ₹{counter_offer:.2f}/kg as a balanced compromise to close deal today."
        )
        for idx, f in enumerate(farmers):
            if idx % 2 == 0:
                farmer_responses.append({
                    "farmer_id": f.id,
                    "farmer_name": f.name,
                    "location": f.location,
                    "response": "ACCEPTED WITH VOLUME CLAUSE",
                    "message": f"Accepts ₹{counter_offer:.2f}/kg conditional on 100% pickup logistics handled.",
                    "agreed_price": counter_offer
                })
            else:
                farmer_responses.append({
                    "farmer_id": f.id,
                    "farmer_name": f.name,
                    "location": f.location,
                    "response": "COUNTER_OFFER",
                    "message": f"Counters at ₹{round(counter_offer + 0.5, 2)}/kg due to Grade A sorting.",
                    "agreed_price": round(counter_offer + 0.5, 2)
                })

    else:
        likelihood = "LOW / UNREALISTIC"
        score = 28
        counter_offer = round(max(min_price, avg_price * 0.92), 2)
        savings = (avg_price - counter_offer) * required_quantity
        strategy_text = (
            f"Target price ₹{target_price:.2f}/kg is below farmer cost baseline. "
            f"High risk of supply walkout. Minimum viable negotiation floor is ₹{counter_offer:.2f}/kg."
        )
        for f in farmers:
            farmer_responses.append({
                "farmer_id": f.id,
                "farmer_name": f.name,
                "location": f.location,
                "response": "REJECTED",
                "message": f"Cannot fulfill below ₹{counter_offer:.2f}/kg under current diesel & fertilizer rates.",
                "agreed_price": counter_offer
            })

    return {
        "product_id": product_id,
        "target_price": round(target_price, 2),
        "average_asking_price": round(avg_price, 2),
        "mandi_benchmark": round(mandi_price, 2),
        "farmer_acceptance_likelihood": likelihood,
        "acceptance_score": score,
        "recommended_counter_offer": round(counter_offer, 2),
        "potential_savings_total": round(max(0.0, savings), 2),
        "ai_negotiation_strategy": strategy_text,
        "farmer_responses": farmer_responses
    }
from fastapi import HTTPException
from sqlalchemy.orm import Session
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, Any, List

from ..models import Supply, Farmer, Product


def calculate_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2.0) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2.0) ** 2
    )
    c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
    return R * c


def match_supply(
    db: Session,
    product_id: int,
    required_quantity: float,
    buyer_lat: float = 22.5726,
    buyer_lon: float = 88.3639,
    strategy: str = "balanced"
) -> Dict[str, Any]:
    """
    Aggregates multiple nearby farmers to fulfill buyer demand.
    Supports strategies:
      - 'cost' (or 'lowest_cost'): prioritizes lowest asking price
      - 'distance' (or 'nearest'): prioritizes nearest farm gate proximity
      - 'balanced': optimal multi-factor trade-off (cost, distance, rating)
    """
    # 1. Product Validation
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Quantity Validation
    if required_quantity is None or required_quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="required_quantity must be greater than 0"
        )

    product_name = product.name

    # 3. Strategy Normalization & Validation
    strat = (strategy or "balanced").strip().lower()
    if strat in ("cost", "lowest_cost", "price", "cheapest"):
        normalized_strategy = "cost"
    elif strat in ("distance", "nearest", "proximity", "closest"):
        normalized_strategy = "distance"
    elif strat in ("balanced", "default"):
        normalized_strategy = "balanced"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy: '{strategy}'. Supported strategies are: 'balanced', 'cost', 'distance'"
        )

    # 4. Fetch available supplies
    supplies = (
        db.query(Supply, Farmer)
        .join(Farmer, Supply.farmer_id == Farmer.id)
        .filter(Supply.product_id == product_id, Supply.quantity > 0)
        .all()
    )

    if not supplies:
        return {
            "product_id": product_id,
            "product_name": product_name,
            "required_quantity": required_quantity,
            "matched_quantity": 0.0,
            "shortage": required_quantity,
            "fulfillment_percentage": 0.0,
            "status": "CRITICAL_SHORTAGE",
            "strategy_used": normalized_strategy,
            "farmers_count": 0,
            "farmers": [],
            "blended_price_per_kg": 0.0,
            "total_estimated_cost": 0.0
        }

    # Annotate candidates with distance
    candidates = []
    prices = []
    distances = []

    for supply, farmer in supplies:
        f_lat = farmer.latitude if farmer.latitude is not None else buyer_lat
        f_lon = farmer.longitude if farmer.longitude is not None else buyer_lon
        dist = calculate_haversine(buyer_lat, buyer_lon, f_lat, f_lon)

        candidates.append({
            "supply": supply,
            "farmer": farmer,
            "distance_km": dist,
            "price": supply.expected_price,
            "rating": getattr(farmer, "rating", 4.5)
        })
        prices.append(supply.expected_price)
        distances.append(dist)

    min_p, max_p = min(prices), max(prices)
    min_d, max_d = min(distances), max(distances)

    # Sort based on normalized strategy
    if normalized_strategy == "cost":
        # Strictly prioritize lowest price first, then closer distance as tie-breaker
        candidates.sort(key=lambda c: (c["price"], c["distance_km"]))
    elif normalized_strategy == "distance":
        # Strictly prioritize shortest distance first, then lower price as tie-breaker
        candidates.sort(key=lambda c: (c["distance_km"], c["price"]))
    else:  # balanced
        def balanced_score(c):
            # Normalize price (0=lowest, 1=highest)
            norm_p = (c["price"] - min_p) / (max_p - min_p) if max_p > min_p else 0.5
            # Normalize distance (0=closest, 1=farthest)
            norm_d = (c["distance_km"] - min_d) / (max_d - min_d) if max_d > min_d else 0.5
            # Rating factor
            norm_r = (c["rating"] - 3.0) / 2.0  # roughly 0 to 1
            # Lower score is better
            return 0.45 * norm_p + 0.35 * norm_d - 0.20 * norm_r

        candidates.sort(key=balanced_score)

    remaining = float(required_quantity)
    matched_farmers = []
    total_cost = 0.0

    for item in candidates:
        if remaining <= 0:
            break

        supply = item["supply"]
        farmer = item["farmer"]
        available_qty = float(supply.quantity)
        alloc_qty = min(available_qty, remaining)

        cost = alloc_qty * supply.expected_price
        total_cost += cost

        matched_farmers.append({
            "farmer_id": farmer.id,
            "farmer_name": farmer.name,
            "location": farmer.location,
            "latitude": farmer.latitude,
            "longitude": farmer.longitude,
            "contact": getattr(farmer, "contact", "+91-9830123456"),
            "rating": getattr(farmer, "rating", 4.8),
            "product": product_name,
            "quality_grade": getattr(supply, "quality_grade", "Grade A"),
            "available_quantity": available_qty,
            "matched_quantity": round(alloc_qty, 1),
            "expected_price": round(supply.expected_price, 2),
            "distance_km": round(item["distance_km"], 1),
            "subtotal": round(cost, 2)
        })

        remaining -= alloc_qty

    matched_total = round(required_quantity - max(0.0, remaining), 1)
    shortage = round(max(0.0, remaining), 1)
    fulfillment_pct = round((matched_total / max(1.0, required_quantity)) * 100.0, 1)

    if shortage == 0:
        status = "FULLY_MATCHED"
    elif matched_total > 0:
        status = "PARTIAL_SHORTAGE"
    else:
        status = "CRITICAL_SHORTAGE"

    blended_price = round(total_cost / max(1.0, matched_total), 2) if matched_total > 0 else 0.0

    return {
        "product_id": product_id,
        "product_name": product_name,
        "required_quantity": required_quantity,
        "matched_quantity": matched_total,
        "shortage": shortage,
        "fulfillment_percentage": fulfillment_pct,
        "status": status,
        "strategy_used": normalized_strategy,
        "farmers_count": len(matched_farmers),
        "farmers": matched_farmers,
        "blended_price_per_kg": blended_price,
        "total_estimated_cost": round(total_cost, 2)
    }
from fastapi import HTTPException
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from ..models import Farmer, Supply


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great circle distance, scaled by 1.22 for realistic road network curvature."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2.0) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2.0) ** 2
    )
    c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
    return R * c * 1.22  # Road network detour factor


def optimize_route(
    db: Session,
    farmer_ids: List[int],
    buyer_name: str = "Kolkata Central Wholesale Hub",
    buyer_lat: float = 22.5726,
    buyer_lon: float = 88.3639,
    farmer_quantities: Optional[Dict[Any, float]] = None,
    product_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Solves multi-stop collection Traveling Salesperson Problem (TSP)
    using Nearest-Neighbor with 2-Opt local refinement.
    Calculates carbon savings, fuel costs, and detailed waypoints for Leaflet map.
    Populates quantity_to_collect_kg from farmer_quantities or active supply records.
    """
    # 1. Validation
    if not farmer_ids:
        raise HTTPException(status_code=400, detail="farmer_ids list cannot be empty")

    farmers = (
        db.query(Farmer)
        .filter(Farmer.id.in_(farmer_ids))
        .all()
    )

    if not farmers:
        raise HTTPException(status_code=404, detail="No farmers found for provided IDs")

    valid_farmers = [
        f for f in farmers
        if f.latitude is not None and f.longitude is not None
    ]

    if not valid_farmers:
        raise HTTPException(status_code=400, detail="None of the specified farmers have valid coordinates")

    # Build quantity lookup for each farmer
    qty_lookup = {}
    if farmer_quantities:
        # User/Workflow passed specific matched quantities
        for k, v in farmer_quantities.items():
            try:
                qty_lookup[int(k)] = float(v)
            except (ValueError, TypeError):
                continue
    elif product_id:
        # Lookup produce supply for the specified product
        supplies = (
            db.query(Supply)
            .filter(
                Supply.farmer_id.in_([f.id for f in valid_farmers]),
                Supply.product_id == product_id
            )
            .all()
        )
        for s in supplies:
            qty_lookup[s.farmer_id] = float(s.quantity)
    else:
        # Fallback: sum of all available supplies for each farmer
        supplies = (
            db.query(Supply)
            .filter(Supply.farmer_id.in_([f.id for f in valid_farmers]))
            .all()
        )
        for s in supplies:
            qty_lookup[s.farmer_id] = qty_lookup.get(s.farmer_id, 0.0) + float(s.quantity)

    # Unoptimized baseline: Sending separate truck round-trips to each farmer
    unoptimized_dist = sum(
        2.0 * haversine_km(buyer_lat, buyer_lon, f.latitude, f.longitude)
        for f in valid_farmers
    )

    # Nearest Neighbor Heuristic
    unvisited = valid_farmers.copy()
    current_lat, current_lon = buyer_lat, buyer_lon
    ordered_farmers = []

    while unvisited:
        nearest = min(
            unvisited,
            key=lambda f: haversine_km(current_lat, current_lon, f.latitude, f.longitude)
        )
        ordered_farmers.append(nearest)
        current_lat, current_lon = nearest.latitude, nearest.longitude
        unvisited.remove(nearest)

    # 2-Opt Improvement for small stop sequences
    if len(ordered_farmers) > 3:
        improved = True
        while improved:
            improved = False
            for i in range(len(ordered_farmers) - 1):
                for j in range(i + 1, len(ordered_farmers)):
                    prev_lat = buyer_lat if i == 0 else ordered_farmers[i - 1].latitude
                    prev_lon = buyer_lon if i == 0 else ordered_farmers[i - 1].longitude
                    next_lat = buyer_lat if j == len(ordered_farmers) - 1 else ordered_farmers[j + 1].latitude
                    next_lon = buyer_lon if j == len(ordered_farmers) - 1 else ordered_farmers[j + 1].longitude

                    d_current = (
                        haversine_km(prev_lat, prev_lon, ordered_farmers[i].latitude, ordered_farmers[i].longitude) +
                        haversine_km(ordered_farmers[j].latitude, ordered_farmers[j].longitude, next_lat, next_lon)
                    )
                    d_swapped = (
                        haversine_km(prev_lat, prev_lon, ordered_farmers[j].latitude, ordered_farmers[j].longitude) +
                        haversine_km(ordered_farmers[i].latitude, ordered_farmers[i].longitude, next_lat, next_lon)
                    )
                    if d_swapped < d_current - 0.5:
                        ordered_farmers[i:j+1] = reversed(ordered_farmers[i:j+1])
                        improved = True

    # Speed and loading constants for consistent time calculation
    COMMERCIAL_SPEED_KMH = 40.0
    LOADING_TIME_PER_FARM_MINS = 20

    waypoints = []
    route_legs = []
    polylines = [[buyer_lat, buyer_lon]]
    total_distance = 0.0
    cum_dist = 0.0

    # Start waypoint (Hub)
    waypoints.append({
        "stop_number": 0,
        "type": "DEPOT",
        "id": None,
        "name": buyer_name,
        "location": "Delivery Depot",
        "latitude": buyer_lat,
        "longitude": buyer_lon,
        "quantity_to_collect_kg": 0.0,
        "distance_from_prev_km": 0.0,
        "cumulative_distance_km": 0.0
    })

    curr_lat, curr_lon = buyer_lat, buyer_lon
    curr_name = buyer_name

    for idx, farmer in enumerate(ordered_farmers, start=1):
        d_leg = haversine_km(curr_lat, curr_lon, farmer.latitude, farmer.longitude)
        total_distance += d_leg
        cum_dist += d_leg

        est_leg_mins = int(round((d_leg / COMMERCIAL_SPEED_KMH) * 60.0 + LOADING_TIME_PER_FARM_MINS))

        route_legs.append({
            "from_name": curr_name,
            "to_name": f"{farmer.name} ({farmer.location})",
            "distance_km": round(d_leg, 1),
            "estimated_time_mins": est_leg_mins
        })

        f_qty = qty_lookup.get(farmer.id, 0.0)

        waypoints.append({
            "stop_number": idx,
            "type": "FARMER",
            "id": farmer.id,
            "name": farmer.name,
            "location": farmer.location,
            "latitude": farmer.latitude,
            "longitude": farmer.longitude,
            "quantity_to_collect_kg": round(f_qty, 1),
            "distance_from_prev_km": round(d_leg, 1),
            "cumulative_distance_km": round(cum_dist, 1)
        })

        polylines.append([farmer.latitude, farmer.longitude])
        curr_lat, curr_lon = farmer.latitude, farmer.longitude
        curr_name = farmer.name

    # Return to Depot Leg
    return_dist = haversine_km(curr_lat, curr_lon, buyer_lat, buyer_lon)
    total_distance += return_dist
    cum_dist += return_dist
    ret_mins = int(round((return_dist / COMMERCIAL_SPEED_KMH) * 60.0))

    route_legs.append({
        "from_name": curr_name,
        "to_name": f"{buyer_name} (Hub Return)",
        "distance_km": round(return_dist, 1),
        "estimated_time_mins": ret_mins
    })

    waypoints.append({
        "stop_number": len(ordered_farmers) + 1,
        "type": "DEPOT",
        "id": None,
        "name": buyer_name,
        "location": "Delivery Depot",
        "latitude": buyer_lat,
        "longitude": buyer_lon,
        "quantity_to_collect_kg": 0.0,
        "distance_from_prev_km": round(return_dist, 1),
        "cumulative_distance_km": round(cum_dist, 1)
    })
    polylines.append([buyer_lat, buyer_lon])

    # Ensure displayed numbers are mathematically consistent within rounding precision
    total_distance_km = round(total_distance, 1)
    unoptimized_dist_km = round(unoptimized_dist, 1)
    distance_saved_km = round(max(0.0, unoptimized_dist_km - total_distance_km), 1)

    carbon_reduction_kg = round(distance_saved_km * 0.26, 1)
    fuel_cost = round((total_distance_km / 4.5) * 92.0, 0)
    total_transit_hours = round(sum(leg["estimated_time_mins"] for leg in route_legs) / 60.0, 1)

    return {
        "buyer_hub": {
            "name": buyer_name,
            "latitude": buyer_lat,
            "longitude": buyer_lon
        },
        "stops_count": len(ordered_farmers),
        "total_distance_km": total_distance_km,
        "estimated_transit_hours": total_transit_hours,
        "estimated_fuel_cost_inr": fuel_cost,
        "unoptimized_single_trip_distance_km": unoptimized_dist_km,
        "distance_saved_km": distance_saved_km,
        "carbon_reduction_kg": carbon_reduction_kg,
        "collection_waypoints": waypoints,
        "route_legs": route_legs,
        "polyline_coordinates": polylines
    }
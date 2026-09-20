from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import date, datetime


# Product Schemas
class ProductBase(BaseModel):
    name: str
    category: Optional[str] = None
    unit: str = "kg"
    mandi_benchmark_price: float = 22.0
    perishability_days: int = 7


class ProductOut(ProductBase):
    id: int

    class Config:
        from_attributes = True


# Farmer Schemas
class FarmerBase(BaseModel):
    name: str
    location: str
    state: str = "West Bengal"
    latitude: float
    longitude: float
    contact: Optional[str] = None
    rating: float = 4.8
    farm_size_acres: float = 5.0


class FarmerOut(FarmerBase):
    id: int
    address: Optional[str] = None
    pincode: Optional[str] = None
    phone_number: Optional[str] = None

    class Config:
        from_attributes = True


# Buyer Schemas
class BuyerBase(BaseModel):
    name: str
    address: str
    city: Optional[str] = ""
    phone_number: str
    pincode: str
    state: str = "West Bengal"


class BuyerOut(BuyerBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Auth & Login Request Schemas
class FarmerLoginRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Farmer full name")
    address: str = Field(..., min_length=2, description="Village, town, or street address")
    phone_number: str = Field(..., min_length=6, description="Contact phone number")
    commodity: str = Field(..., min_length=2, description="Crop or commodity name (e.g. Potato, Tomato, Wheat)")
    quantity_kg: float = Field(..., gt=0, description="Available quantity in kg")
    price_per_kg: float = Field(..., gt=0, description="Farmer desired price per kg (INR)")
    pincode: str = Field(..., min_length=4, description="Area postal pincode")
    state: str = Field("West Bengal", min_length=2, description="State name")


class FarmerLoginRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Farmer registered full name")
    phone_number: str = Field(..., min_length=6, description="Registered phone number")


class BuyerLoginRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Buyer or company name")
    address: str = Field(..., min_length=2, description="Delivery or warehouse address")
    city: Optional[str] = Field("", description="City or district name")
    phone_number: str = Field(..., min_length=6, description="Contact phone number")
    pincode: str = Field(..., min_length=4, description="Area postal pincode")
    state: str = Field("West Bengal", min_length=2, description="State name")


class BuyerLoginRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Buyer or enterprise registered name")
    phone_number: str = Field(..., min_length=6, description="Registered contact phone number")


class AdminLoginRequest(BaseModel):
    admin_user_id: str = Field(..., min_length=2, description="Admin user identifier")
    password: str = Field(..., min_length=1, description="Admin password")


class AdminCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Admin full name or team label")
    admin_user_id: str = Field(..., min_length=3, max_length=50, description="Unique admin user ID")
    password: str = Field(..., min_length=4, description="Initial admin password")


class AdminUpdateIdRequest(BaseModel):
    admin_user_id: Optional[str] = None
    new_admin_user_id: Optional[str] = None


class AdminUpdatePasswordRequest(BaseModel):
    new_password: Optional[str] = None
    password: Optional[str] = None


class AdminStatusRequest(BaseModel):
    is_active: Union[int, bool] = Field(..., description="Active flag: 1/0 or true/false")


class OwnerUpdateCredentialsRequest(BaseModel):
    new_admin_user_id: Optional[str] = Field(None, min_length=3, max_length=50, description="New Super Admin User ID")
    new_password: Optional[str] = Field(None, min_length=4, description="New Super Admin Password")


class AdminOut(BaseModel):
    id: int
    name: str
    admin_user_id: str
    role: str
    is_active: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FarmerUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, description="Farmer full name")
    phone_number: Optional[str] = Field(None, min_length=6, description="Contact phone number")
    address: Optional[str] = Field(None, min_length=2, description="Village or address")
    state: Optional[str] = Field(None, min_length=2, description="State")
    pincode: Optional[str] = Field(None, min_length=4, description="Postal pincode")


class BuyerUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, description="Buyer or enterprise name")
    phone_number: Optional[str] = Field(None, min_length=6, description="Contact phone number")
    address: Optional[str] = Field(None, min_length=2, description="Depot or warehouse address")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, min_length=2, description="State")
    pincode: Optional[str] = Field(None, min_length=4, description="Postal pincode")


class DemoResetRequest(BaseModel):
    confirm: bool = Field(..., description="Confirmation flag to proceed with demo data reset")


class FarmerAddSupplyRequest(BaseModel):
    farmer_id: int
    commodity: str
    quantity_kg: float
    price_per_kg: float
    quality_grade: str = "Grade A"


class FarmerUpdateSupplyRequest(BaseModel):
    farmer_id: int
    supply_id: int
    commodity: str = Field(..., min_length=2, description="Crop or commodity name")
    quantity_kg: float = Field(..., gt=0, description="Available quantity in kg")
    price_per_kg: float = Field(..., gt=0, description="Desired asking price per kg (INR)")
    quality_grade: Optional[str] = "Grade A"


class FarmerClearStockRequest(BaseModel):
    farmer_id: int
    supply_id: int
    cleared_quantity_kg: Optional[float] = Field(None, gt=0, description="Quantity cleared/ordered in kg")
    ordered_quantity_kg: Optional[float] = Field(None, gt=0, description="Quantity ordered in kg")
    selling_price_per_kg: Optional[float] = Field(None, gt=0, description="Actual realized/ordered price per kg")
    notes: Optional[str] = Field(None, description="Buyer or order fulfillment note")


class AuthResponse(BaseModel):
    status: str
    user_type: str  # "farmer", "buyer", "admin", "owner"
    user_id: Any
    name: str
    phone_number: Optional[str] = None
    address: Optional[str] = ""
    pincode: Optional[str] = ""
    state: Optional[str] = ""
    role: Optional[str] = None
    access_token: Optional[str] = None
    message: str
    details: Optional[Dict[str, Any]] = None


# Supply Schemas
class SupplyBase(BaseModel):
    farmer_id: int
    product_id: int
    quantity: float
    expected_price: float
    quality_grade: str = "Grade A"
    available_date: Optional[date] = None


class SupplyOut(SupplyBase):
    id: int
    farmer_name: Optional[str] = None
    product_name: Optional[str] = None
    location: Optional[str] = None

    class Config:
        from_attributes = True


# Demand Forecast Schemas
class ForecastRequest(BaseModel):
    product_id: int = Field(..., gt=0, description="Valid product ID")
    days_ahead: int = Field(7, ge=1, le=60, description="Forecast horizon in days (1-60)")
    region: str = Field("Kolkata Metro Hub", min_length=2, max_length=100)


class DailyForecastItem(BaseModel):
    day: int
    date: str
    predicted_demand_kg: float
    lower_bound_kg: float
    upper_bound_kg: float
    confidence_score: float


class ForecastResponse(BaseModel):
    status: str
    product_id: int
    product_name: str
    region: str
    forecast_days: int
    trend_direction: str  # e.g., "SURGING (+14.2%)", "STABLE (+0.9%)", "CONTRACTING (-6.1%)"
    growth_percentage: float
    historical_data: List[Dict[str, Any]]
    forecast: List[DailyForecastItem]
    insights: List[str]


# Matching Schemas
class SupplyMatchRequest(BaseModel):
    product_id: int = Field(..., gt=0, description="Valid product ID")
    required_quantity: float = Field(..., gt=0, description="Required procurement quantity in kg (must be > 0)")
    buyer_lat: float = Field(22.5726, ge=-90.0, le=90.0, description="Buyer hub latitude")
    buyer_lon: float = Field(88.3639, ge=-180.0, le=180.0, description="Buyer hub longitude")
    strategy: str = Field("balanced", description="Matching strategy: 'balanced', 'cost' (or 'lowest_cost'), 'distance' (or 'nearest')")


class MatchedFarmerItem(BaseModel):
    farmer_id: int
    farmer_name: str
    location: str
    latitude: float
    longitude: float
    contact: Optional[str] = None
    rating: float
    product: str
    quality_grade: str
    available_quantity: float
    matched_quantity: float
    expected_price: float
    distance_km: float
    subtotal: float


class SupplyMatchResponse(BaseModel):
    product_id: int
    product_name: str
    required_quantity: float
    matched_quantity: float
    shortage: float
    fulfillment_percentage: float
    status: str  # "FULLY_MATCHED", "PARTIAL_SHORTAGE", "CRITICAL_SHORTAGE"
    strategy_used: str
    farmers_count: int
    farmers: List[MatchedFarmerItem]
    blended_price_per_kg: float
    total_estimated_cost: float


# Price Intelligence & Negotiation Schemas
class PriceInsightResponse(BaseModel):
    product_id: int
    product_name: str
    mandi_benchmark_price: float
    lowest_farmer_price: float
    average_farmer_price: float
    highest_farmer_price: float
    historical_price_30d_avg: float
    fair_market_band_min: float
    fair_market_band_max: float
    recommendation: str


class NegotiationRequest(BaseModel):
    product_id: int = Field(..., gt=0, description="Valid product ID")
    required_quantity: float = Field(..., gt=0, description="Required quantity in kg (must be > 0)")
    target_price: float = Field(..., gt=0, description="Target price per kg (must be > 0)")
    matched_farmer_ids: List[int] = Field(..., min_items=1, description="List of matched farmer IDs")


class NegotiationResponse(BaseModel):
    product_id: int
    target_price: float
    average_asking_price: float
    mandi_benchmark: float
    farmer_acceptance_likelihood: str  # "HIGH", "MODERATE", "LOW / UNREALISTIC"
    acceptance_score: int  # 0 to 100
    recommended_counter_offer: float
    potential_savings_total: float
    ai_negotiation_strategy: str
    farmer_responses: List[Dict[str, Any]]


# Logistics & Route Schemas
class RouteOptimizationRequest(BaseModel):
    farmer_ids: List[int] = Field(..., min_items=1, description="List of farmer IDs to collect from")
    farmer_quantities: Optional[Dict[str, float]] = Field(None, description="Optional map of farmer_id -> quantity_kg to collect")
    product_id: Optional[int] = Field(None, gt=0, description="Optional product ID to look up quantities if not provided")
    buyer_name: str = Field("Kolkata Central Wholesale Hub", min_length=2)
    buyer_lat: float = Field(22.5726, ge=-90.0, le=90.0, description="Buyer depot latitude")
    buyer_lon: float = Field(88.3639, ge=-180.0, le=180.0, description="Buyer depot longitude")


class RouteWaypoint(BaseModel):
    stop_number: int
    type: str  # "DEPOT" or "FARMER"
    id: Optional[int] = None
    name: str
    location: str
    latitude: float
    longitude: float
    quantity_to_collect_kg: float
    distance_from_prev_km: float
    cumulative_distance_km: float


class RouteLeg(BaseModel):
    from_name: str
    to_name: str
    distance_km: float
    estimated_time_mins: int


class RouteOptimizationResponse(BaseModel):
    buyer_hub: Dict[str, Any]
    stops_count: int
    total_distance_km: float
    estimated_transit_hours: float
    estimated_fuel_cost_inr: float
    unoptimized_single_trip_distance_km: float
    distance_saved_km: float
    carbon_reduction_kg: float
    collection_waypoints: List[RouteWaypoint]
    route_legs: List[RouteLeg]
    polyline_coordinates: List[List[float]]


# Order & Fulfillment Schemas
class OrderCreateRequest(BaseModel):
    buyer_name: str = Field(..., min_length=2)
    product_id: int = Field(..., gt=0, description="Valid product ID")
    total_quantity: float = Field(..., gt=0, description="Total quantity in kg (must be > 0)")
    agreed_price_per_kg: float = Field(..., gt=0, description="Agreed price per kg (must be > 0)")
    farmer_allocations: List[Dict[str, Any]] = Field(..., min_items=1, description="List of farmer allocations")
    route_summary: Optional[Dict[str, Any]] = None


class OrderResponse(BaseModel):
    order_number: str
    status: str
    buyer_name: str
    product_name: str
    total_quantity: float
    agreed_price_per_kg: float
    total_procurement_cost: float
    logistics_distance_km: float
    logistics_cost: float
    grand_total: float
    farmers_involved: int
    created_at: str
    tracking_steps: List[Dict[str, Any]]
    farmer_items: Optional[List[Dict[str, Any]]] = None

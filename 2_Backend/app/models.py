from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    location = Column(String, nullable=False)
    pincode = Column(String, nullable=True)
    state = Column(String, default="West Bengal")
    latitude = Column(Float, nullable=False, default=22.8124)
    longitude = Column(Float, nullable=False, default=88.2312)
    contact = Column(String, nullable=True)
    rating = Column(Float, default=4.8)
    farm_size_acres = Column(Float, default=5.0)

    supplies = relationship("Supply", back_populates="farmer")


class Buyer(Base):
    __tablename__ = "buyers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=True, default="")
    phone_number = Column(String, nullable=False)
    pincode = Column(String, nullable=False)
    state = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=True)
    unit = Column(String, default="kg")
    mandi_benchmark_price = Column(Float, default=22.0)
    perishability_days = Column(Integer, default=7)

    supplies = relationship("Supply", back_populates="product")
    demands = relationship("Demand", back_populates="product")
    demand_history = relationship("DemandHistory", back_populates="product")


class Supply(Base):
    __tablename__ = "supplies"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Float, nullable=False)  # Current stock left in kg
    cleared_quantity = Column(Float, default=0.0)  # Stock cleared / sold in kg
    initial_quantity = Column(Float, nullable=True)  # Total initial harvest batch in kg
    expected_price = Column(Float, nullable=False)  # in INR/kg
    quality_grade = Column(String, default="Grade A")  # Grade A, Grade B, Grade C
    available_date = Column(Date, nullable=True)
    harvest_date = Column(Date, nullable=True)

    farmer = relationship("Farmer", back_populates="supplies")
    product = relationship("Product", back_populates="supplies")


class Demand(Base):
    __tablename__ = "demands"

    id = Column(Integer, primary_key=True, index=True)
    buyer_name = Column(String, nullable=False)
    buyer_type = Column(String, default="Wholesaler")  # Retail Chain, Wholesaler, Processor
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    required_quantity = Column(Float, nullable=False)
    required_date = Column(Date, nullable=True)
    delivery_location = Column(String, nullable=False)
    delivery_lat = Column(Float, default=22.5726)  # Default Kolkata Wholesale Hub
    delivery_lon = Column(Float, default=88.3639)
    max_target_price = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    product = relationship("Product", back_populates="demands")


class DemandHistory(Base):
    __tablename__ = "demand_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    date = Column(Date, nullable=False)
    region = Column(String, default="Kolkata Metro Hub")
    quantity_demanded = Column(Float, nullable=False)
    average_mandi_price = Column(Float, nullable=False)

    product = relationship("Product", back_populates="demand_history")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, nullable=False)
    buyer_name = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    total_quantity = Column(Float, nullable=False)
    agreed_price_per_kg = Column(Float, nullable=False)
    total_procurement_cost = Column(Float, nullable=False)
    estimated_distance_km = Column(Float, default=0.0)
    logistics_cost = Column(Float, default=0.0)
    status = Column(String, default="CONFIRMED")  # CONFIRMED, DISPATCHED, COLLECTING, DELIVERED
    collection_route_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False)
    allocated_quantity = Column(Float, nullable=False)
    price_per_kg = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    farmer = relationship("Farmer")
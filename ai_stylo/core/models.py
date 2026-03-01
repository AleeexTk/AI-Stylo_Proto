from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(String, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Profile(Base):
    __tablename__ = "profiles"
    user_id = Column(String, primary_key=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), primary_key=True)
    style_preset = Column(String, default="casual")
    budget_min = Column(Float, default=50.0)
    budget_max = Column(Float, default=600.0)
    theme_color = Column(String, default="#4A90E2")
    counters = Column(JSON, default=dict)
    skills = Column(JSON, default=dict)
    seen_events = Column(Integer, default=0)
    meta_data = Column(JSON, default=dict)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(String, ForeignKey("merchants.id"))
    user_id = Column(String)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    type = Column(String)
    payload = Column(JSON)

class TryOnJob(Base):
    __tablename__ = "tryon_jobs"
    id = Column(String, primary_key=True)
    merchant_id = Column(String, ForeignKey("merchants.id"))
    user_id = Column(String)
    status = Column(String)  # pending, avatar_analysis, rendering, completed, failed
    avatar_url = Column(String)
    item_url = Column(String)
    outfit_id = Column(String, nullable=True)
    cache_key = Column(String)
    result_url = Column(String, nullable=True)
    error = Column(String, nullable=True)
    
    # Avatar pipeline state
    meta_data = Column(JSON, default=dict)       # Renamed from 'metadata' (reserved)
    scene_json = Column(JSON, default=dict)      # Full scene description for render
    progress = Column(Float, default=0.0)       # 0.0 -> 1.0 (Analysis -> Warp -> Render -> Done)
    model_version = Column(String, default="v1.1-autumn")
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True) # Usually SKU or brand_id
    merchant_id = Column(String, ForeignKey("merchants.id"), primary_key=True)
    title = Column(String)
    brand = Column(String)
    price = Column(Float)
    currency = Column(String, default="UAH")
    image_url = Column(String) # Main high-res image
    url = Column(String) # Link to original product card
    description = Column(String)
    category = Column(String) # e.g. "Dresses"
    meta_data = Column(JSON, default=dict) # sizes, colors, material, etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class Item:
    id: str
    title: str
    brand: str
    price: float
    image: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    category: str = ""
    old_price: Optional[float] = None
    luxury_index: float = 0.0

@dataclass
class Profile:
    user_id: str
    theme_color: str = "#4A90E2"
    style_preset: str = "casual"
    budget_min: float = 50.0
    budget_max: float = 600.0
    affinities: Dict[str, float] = field(default_factory=dict)
    counters: Dict[str, int] = field(default_factory=dict)
    skills: Dict[str, Any] = field(default_factory=dict)
    seen_events: int = 0
    similarity_history: List[float] = field(default_factory=list)

@dataclass
class Outfit:
    slots: Dict[str, Optional[Item]]
    total_price: float
    reasons: List[str] = field(default_factory=list)
    discounted_amount: float = 0.0

@dataclass
class Event:
    ts: str
    type: str
    payload: Dict[str, Any]

from typing import List, Dict, Any, Optional
from ..contracts import Item, Outfit

class OutfitScorer:
    def __init__(self, profile: Dict[str, Any]):
        self.profile = profile

    def score_item(self, item: Item) -> float:
        score = 1.0
        
        # 1. Budget Alignment
        min_b = self.profile.get("budget_min", 0)
        max_b = self.profile.get("budget_max", 10000)
        if min_b <= item.price <= max_b:
            score += 0.5
        elif item.price > max_b:
            score -= 0.5
            
        # 2. Brand Affinity
        affinities = self.profile.get("affinities", {})
        brand_weight = affinities.get(item.brand, 0.0)
        score += brand_weight
        
        # 3. Luxury/Smart modifiers
        # Check for luxury skill influence
        if self.profile.get("skills", {}).get("luxury_seeker"):
            score += (item.luxury_index * 0.5)
            
        return score

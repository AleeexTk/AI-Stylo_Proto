import random
from typing import List, Dict, Optional
from ..contracts import Item, Outfit
from .scoring import OutfitScorer

class OutfitGenerator:
    def __init__(self, catalog_items: List[Item]):
        self.catalog = catalog_items

    def generate(self, profile: Dict[str, Any], count: int = 1) -> List[Outfit]:
        scorer = OutfitScorer(profile)
        
        outfits = []
        for _ in range(count):
            slots = {
                "top": self._pick_best(scorer, "top"),
                "bottom": self._pick_best(scorer, "bottom"),
                "shoes": self._pick_best(scorer, "shoes"),
                "accessory": self._pick_best(scorer, "accessory")
            }
            
            total_price = sum(it.price for it in slots.values() if it)
            discounted = sum((it.old_price - it.price) for it in slots.values() if it and it.old_price)
            
            reasons = self._generate_reasons(slots, profile)
            
            outfits.append(Outfit(
                slots=slots,
                total_price=total_price,
                reasons=reasons,
                discounted_amount=discounted
            ))
        return outfits

    def _pick_best(self, scorer: OutfitScorer, category: str) -> Optional[Item]:
        candidates = [it for it in self.catalog if it.category == category]
        if not candidates:
            return None
            
        # Quick and dirty: score them and pick from top 3
        candidates.sort(key=lambda it: scorer.score_item(it), reverse=True)
        return random.choice(candidates[:3])

    def _generate_reasons(self, slots: Dict[str, Optional[Item]], profile: Dict[str, Any]) -> List[str]:
        reasons = []
        # Example explainability logic
        has_luxury = profile.get("skills", {}).get("luxury_seeker")
        if has_luxury:
            reasons.append("Підібрано з урахуванням вашого інтересу до преміальних брендів.")
        
        reasons.append(f"Стиль: {profile.get('style_preset', 'casual').capitalize()}.")
        return reasons

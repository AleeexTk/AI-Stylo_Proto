from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class BrandFitProfile:
    brand: str
    bias: float  # -1.0 (runs small) to 1.0 (runs large)
    size_grid: Dict[str, float] # Size name to reference width/chest ratio

class SizeEngine:
    """
    Движок интеллектуального подбора размера (B2B Sizing).
    Поддерживает 3 уровня точности:
    Level 1: Анкета / Преференции
    Level 2: Параметры тела (рост, вес)
    Level 3: Фото-анализ (Evo-DNA)
    """
    
    def __init__(self):
        self.brand_profiles = {
            "Zara": BrandFitProfile("Zara", -0.5, {"S": 0.12, "M": 0.14, "L": 0.16}),
            "Mango": BrandFitProfile("Mango", 0.0, {"S": 0.13, "M": 0.15, "L": 0.17}),
            "H&M": BrandFitProfile("H&M", 0.2, {"S": 0.14, "M": 0.16, "L": 0.18})
        }

    def suggest_size(self, avatar_profile: Dict[str, Any], product_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рекомендует оптимальный размер на основе профиля пользователя и метаданных товара.
        """
        brand = product_metadata.get("brand", "Generic")
        profile = self.brand_profiles.get(brand, BrandFitProfile(brand, 0.0, {"S": 0.13, "M": 0.15, "L": 0.17}))
        
        # Level 3: Анализ по фото (shoulder_norm)
        shoulder_norm = avatar_profile.get("shoulder_norm", 0.1)
        
        # Базовый подбор по сетке с учетом bias бренда
        effective_norm = shoulder_norm - (profile.bias * 0.01)
        
        suggested = "M" # Default
        best_diff = float('inf')
        
        for size, ref_val in profile.size_grid.items():
            diff = abs(effective_norm - ref_val)
            if diff < best_diff:
                best_diff = diff
                suggested = size
                
        # Расчет уверенности
        confidence = avatar_profile.get("confidence", 0.5)
        
        return {
            "suggested_size": suggested,
            "confidence": confidence,
            "fit_notes": f"Based on {brand} fit profile. Brand runs {'small' if profile.bias < 0 else 'large' if profile.bias > 0 else 'true to size'}."
        }

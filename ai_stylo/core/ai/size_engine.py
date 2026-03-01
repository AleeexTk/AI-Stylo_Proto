from typing import Dict, Any, Optional
import json

class SizeEngine:
    """Професійне серце розрахунку розмірів та примірки (Fit Analysis) з підтримкою багатьох брендів."""
    
    def __init__(self):
        # Реєстр брендів (Merchant Registry)
        self.brand_registry = {
            "default": {
                "name": "AI-Stylo Standard",
                "bias": 1.0, # 1.0 = true to size
                "grids": {
                    "top": {"S": [80, 95], "M": [96, 110], "L": [111, 125], "XL": [126, 145]},
                    "bottom": {"S": [70, 85], "M": [86, 95], "L": [96, 110]}
                }
            },
            "zara_style": {
                "name": "Zara (Slim Fit Focus)",
                "bias": 0.92, # Маломірить
                "grids": {
                    "top": {"S": [75, 90], "M": [91, 105], "L": [106, 120], "XL": [121, 135]}
                }
            },
            "nike_fit": {
                "name": "Nike (Athletic/Oversize)",
                "bias": 1.1, # Більшомірить
                "grids": {
                    "top": {"S": [85, 100], "M": [101, 115], "L": [116, 130], "XL": [131, 155]}
                }
            }
        }

    def analyze_fit(self, avatar_profile: Dict[str, Any], garment_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Глибокий аналіз посадки з урахуванням специфіки бренду."""
        sw = avatar_profile.get("measurements", {}).get("shoulder_width", 0)
        completeness = avatar_profile.get("completeness", 0)
        pose_type = avatar_profile.get("pose_type", "unknown")
        body_type = avatar_profile.get("body_type", "standard")

        # 1. Визначення контексту бренду
        brand_id = garment_metadata.get("brand_id", "default") if garment_metadata else "default"
        brand = self.brand_registry.get(brand_id, self.brand_registry["default"])
        
        # 2. Розрахунок Confidence
        confidence = completeness
        if pose_type == "angled": confidence *= 0.85

        # 3. Dynamic Size Matching with Bias
        category = garment_metadata.get("category", "top") if garment_metadata else "top"
        grid = brand["grids"].get(category, self.brand_registry["default"]["grids"]["top"])
        
        recommended_size = "M" 
        fit_hint = "standard_fit"
        
        # Застосовуємо Bias бренду до замірів користувача
        effective_sw = sw * (1.0 / brand["bias"])
        
        for size, limits in grid.items():
            if limits[0] <= effective_sw <= limits[1]:
                recommended_size = size
                break
        
        # 4. Просунуті підказки (Fit Logic)
        if brand["bias"] < 1.0:
            fit_hint = f"runs_small_by_brand"
        elif brand["bias"] > 1.1:
            fit_hint = f"relaxed_oversize_fit"

        if body_type == "v-shape" and category == "top":
            fit_hint += "_tight_shoulders"

        return {
            "brand_name": brand["name"],
            "recommended_size": recommended_size,
            "fit_hint": fit_hint,
            "confidence": round(confidence, 2),
            "bias_factor": brand["bias"],
            "engine_version": "1.1.0-multi-tenant"
        }

    def generate_fit_heatmap(self, avatar_profile: Dict[str, Any], garment_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Генерує теплову карту напруги тканини (Fit Heatmap) на сітці 10x30."""
        grid = avatar_profile.get("grid_map", [])
        if not grid: return {"heatmap": [], "max_tension": 0.0}

        sw = avatar_profile.get("measurements", {}).get("shoulder_width", 0)
        brand_id = garment_metadata.get("brand_id", "default") if garment_metadata else "default"
        brand = self.brand_registry.get(brand_id, self.brand_registry["default"])
        
        # Ефект натягу: чим більше реальні розміри перевищують сітку бренду, тим вище напруга
        # Беремо M як базу (100px)
        standard_w = brand["grids"].get("top", {}).get("M", [90, 110])[1]
        tension_base = (sw / standard_w) * (1.0 / brand["bias"])
        
        heatmap = []
        max_tension = 0.0
        
        for r_idx, row in enumerate(grid):
            row_tension = []
            for c_idx, point in enumerate(row):
                # Простий розрахунок напруги: 
                # Плечі (перші 5 рядків сітки) та боки (стовпчики 0-2 та 7-9) мають вищу напругу
                local_tension = tension_base
                
                # Додаємо 'анатомічні зони' ( Shoulder Stress )
                if r_idx < 5: local_tension *= 1.25 # Напруга в плечах
                if c_idx < 2 or c_idx > 7: local_tension *= 1.15 # Напруга в швах
                
                # Рандомізація для ефекту 'живої' тканини (Micro-folds)
                local_tension *= (0.95 + (0.1 * ((r_idx + c_idx) % 3) / 3))
                
                val = round(min(1.0, local_tension - 0.5), 3)
                if val > max_tension: max_tension = val
                row_tension.append(val)
            heatmap.append(row_tension)

        return {
            "heatmap": heatmap,
            "max_tension": max_tension,
            "hotspots": ["shoulders", "chest"] if max_tension > 0.8 else []
        }

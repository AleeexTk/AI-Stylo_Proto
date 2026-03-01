from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class BodyGrid(BaseModel):
    """Сетка 10x30 для оценки плотности и композиции (Evo-Grid)."""
    rows: int = 30
    cols: int = 10
    data: List[List[float]] = [] # Плотность или занятость 0..1

class AvatarProfileModel(BaseModel):
    """
    Структурированный антропометрический слепок пользователя.
    Используется как кэш для повторных примерок и основа для подбора размера.
    """
    user_id: str
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # 📐 Нормализованные замеры (relative to bbox_height or growth)
    # shoulder_norm = shoulder_width / bbox_height
    shoulder_norm: float = 0.0
    hip_norm: float = 0.0
    torso_ratio: float = 0.0
    
    # 👤 Классификация
    body_type: str = "rectangle" # v-shape, pear, rectangle, athletic
    pose_type: str = "front"     # front, angled, side
    
    # 🦴 Качество данных
    completeness: float = 0.0    # 0..1 (наличие всех ключевых точек)
    confidence: float = 0.0      # Доверие к анализу (зависит от позы и освещения)
    
    # 🌐 Геометрические данные
    keypoints: Dict[str, Any] = {}
    grid_10x30: Optional[BodyGrid] = None

    def suggest_size(self, brand_grid: Dict[str, List[float]], category: str = "top") -> Dict[str, Any]:
        """
        MVP эвристика: маппинг нормализованных плеч на сетку бренда.
        """
        if self.shoulder_norm == 0 or self.confidence < 0.5:
            return {"size": "M", "confidence": 0.0, "reason": "low_data_quality"}
            
        # Пример логики: бренд даёт диапазоны для shoulder_norm
        # В реале тут будет сложный маппинг с учетом brand_bias
        for size, (min_s, max_s) in brand_grid.items():
            if min_s <= self.shoulder_norm <= max_s:
                return {
                    "size": size,
                    "confidence": self.confidence,
                    "fit_hint": "regular_fit",
                    "reason": "shoulder_match"
                }
        
        return {"size": "L" if self.shoulder_norm > 0.15 else "S", "confidence": 0.5}

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "alex",
                "shoulder_norm": 0.12,
                "body_type": "athletic",
                "completeness": 0.95
            }
        }

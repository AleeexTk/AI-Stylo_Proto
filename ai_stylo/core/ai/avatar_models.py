from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class KeyPoint(BaseModel):
    name: str
    x: float
    y: float
    z: float
    visibility: float

class AvatarProfile(BaseModel):
    """Цифровий антропометричний профіль користувача (Evo-DNA)."""
    user_id: str
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # 📐 Пропорції та розміри (Estimates)
    height_ratio: float = 1.0  # Коефіцієнт зросту до ширини
    shoulder_width: float = 0.0 # В пікселях або відносних одиницях
    torso_length: float = 0.0
    
    # 👤 Тип фігури (Classification)
    body_type: str = "athletic"  # casual, athletic, slim, curvy
    pose_type: str = "standing_front" # front, side, seated
    
    # 🦴 Скелетна модель (2D/3D Keypoints)
    keypoints: Dict[str, List[float]] = {} 
    
    # 📏 Антропометрія (Internal)
    measurements: Dict[str, float] = {}

    def suggest_size(self, category: str = "top") -> str:
        """Алгоритм підбору розміру на основі антропометрії (MVP Heuristics)."""
        sw = self.measurements.get("shoulder_width", 0)
        if sw == 0: return "M" # Default
        
        # Базовий мапінг на стандартні розміри (умовні пікселі/одиниці)
        if category == "top":
            if sw > 150: return "XL"
            elif sw > 120: return "L"
            elif sw > 90: return "M"
            else: return "S"
        return "M"

    def update_vibe(self) -> str:
        """Визначає 'стильовий вайб' на основі пропорцій."""
        ratio = self.measurements.get("aspect_ratio", 1.0)
        if ratio > 1.3: return "tall_and_slim"
        return "standard_build"

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "sanya",
                "body_type": "athletic",
                "pose_type": "standing_front",
                "size_recommendations": {"top": "L", "bottom": "34"}
            }
        }

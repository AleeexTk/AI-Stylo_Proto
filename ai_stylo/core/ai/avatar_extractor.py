import io
import time
import os
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image
import numpy as np

from ai_stylo.core.ai.grid_mapper import GridMapper

# Lazy imports for MediaPipe to avoid startup delay
mp_vision = None
mp_base = None

def _load_mp_tasks():
    global mp_vision, mp_base
    if mp_vision is None:
        try:
            from mediapipe.tasks.python import vision as _vision
            from mediapipe.tasks.python.core import base_options as _base
            mp_vision = _vision
            mp_base = _base
        except ImportError:
            return False
    return True

class AvatarExtractor:
    """Модуль видобутку антропометричних даних користувача (Avatar Extraction)."""
    
    def __init__(self, model_path: str = "models/pose_landmarker.task"):
        self.model_path = model_path
        self._landmarker = None
        self._segmenter = None

    def _init_tasks(self):
        if not _load_mp_tasks(): return
        if self._landmarker is None and os.path.exists(self.model_path):
            try:
                options = mp_vision.PoseLandmarkerOptions(
                    base_options=mp_base.BaseOptions(model_asset_path=self.model_path),
                    running_mode=mp_vision.RunningMode.IMAGE,
                    output_segmentation_masks=True
                )
                self._landmarker = mp_vision.PoseLandmarker.create_from_options(options)
            except Exception as e:
                print(f"⚠️ AvatarExtractor: Pose task init failed: {e}")

    def extract(self, image_bytes: bytes, user_id: str = "guest") -> Dict[str, Any]:
        """Виконує повний цикл нормалізації, сегментації та детекції пози."""
        self._init_tasks()
        
        # 🟢 1. Normalization (PIL)
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        
        # 🟢 2. Pose & Segmentation (MediaPipe)
        avatar_profile = {
            "user_id": user_id,
            "timestamp": time.time(),
            "body_type": "standard", # Default
            "pose_type": "unknown",
            "keypoints": {},
            "measurements": {}
        }

        if self._landmarker:
            import mediapipe as mp
            # Конвертація для MediaPipe
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.array(img))
            result = self._landmarker.detect(mp_image)
            
            if result.pose_landmarks:
                landmarks = result.pose_landmarks[0]
                # Беремо ключові точки для антропометрії
                # Плечі: 11 (L), 12 (R)
                # Таз: 23 (L), 24 (R)
                ls, rs = landmarks[11], landmarks[12]
                lh, rh = landmarks[23], landmarks[24]
                
                # Розрахунок ширини плечей (відносно ширини картинки)
                shoulder_width = abs(ls.x - rs.x) * w
                hip_width = abs(lh.x - rh.x) * w
                
                avatar_profile["measurements"] = {
                    "shoulder_width": round(shoulder_width, 1),
                    "hip_width": round(hip_width, 1),
                    "aspect_ratio": round(h/w, 2)
                }
                
                # Визначення типу пози
                if abs(ls.z - rs.z) < 0.1:
                    avatar_profile["pose_type"] = "front"
                else:
                    avatar_profile["pose_type"] = "angled"

                # Зберігаємо всі 17 keypoints для GridMapper
                all_kp: List[Optional[Tuple[float, float]]] = []
                for lm in landmarks[:17]:
                    if lm.visibility > 0.3:
                        all_kp.append((lm.x * w, lm.y * h))
                    else:
                        all_kp.append(None)
                # Дополняем до 17 если меньше
                while len(all_kp) < 17:
                    all_kp.append(None)

                avatar_profile["keypoints"] = {
                    "shoulders": [ls.x, ls.y, rs.x, rs.y],
                    "hips": [lh.x, lh.y, rh.x, rh.y],
                    "all": [[round(p[0]/w, 3), round(p[1]/h, 3)] if p else None for p in all_kp]
                }

                # 🌐 Grid 10×30 через GridMapper
                gm = GridMapper()
                grid_result = gm.map(all_kp, image_w=w, image_h=h)

                avatar_profile["grid_map"]      = grid_result.grid_points
                avatar_profile["grid_labels"]   = grid_result.grid_labels
                avatar_profile["grid_zones"]    = {k: list(v) for k, v in grid_result.zones.items()}
                avatar_profile["completeness"]  = grid_result.completeness
                avatar_profile["partial"]       = grid_result.partial
                avatar_profile["pose_type"]     = grid_result.pose_type
                avatar_profile["detected_zones"] = grid_result.detected_zones

                # Body Type Estimate
                ratio = shoulder_width / hip_width if hip_width > 0 else 1.0
                if ratio > 1.2:   avatar_profile["body_type"] = "v-shape"
                elif ratio < 0.9: avatar_profile["body_type"] = "pear"
                else:             avatar_profile["body_type"] = "rectangle"

        return avatar_profile

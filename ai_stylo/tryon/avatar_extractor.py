import io
import time
import numpy as np
import cv2
from typing import Optional, Dict, Any, List
from PIL import Image
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from .avatar_models import AvatarProfileModel, BodyGrid

class AvatarExtractor:
    """
    Модуль анализа аватара (B2B Core).
    Переводит фото в структурированную схему тела (Evo-DNA).
    """
    
    def __init__(self, model_path: str = "models/pose_landmarker.task"):
        self.model_path = model_path
        self._detector = None
        self._init_detector()

    def _init_detector(self):
        try:
            base_options = python.BaseOptions(model_asset_path=self.model_path)
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                output_segmentation_masks=True
            )
            self._detector = vision.PoseLandmarker.create_from_options(options)
        except Exception as e:
            print(f"Warning: MediaPipe Pose initialization failed: {e}")
            self._detector = None

    def extract_from_bytes(self, image_bytes: bytes, user_id: str = "guest") -> AvatarProfileModel:
        """
        Выполняет анализ фото и возвращает структурированный профиль.
        """
        start_time = time.time()
        
        # 1. Загрузка изображения
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image from bytes.")
        
        h, w, _ = img.shape
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        
        if self._detector is None:
            return self._get_fallback_profile(user_id, w, h)

        # 2. Детекция
        detection_result = self._detector.detect(mp_image)
        
        if not detection_result.pose_landmarks:
            return self._get_fallback_profile(user_id, w, h, confidence=0.0)

        landmarks = detection_result.pose_landmarks[0]
        
        # 3. Расчет метрик
        # Левое плечо (11), правое плечо (12)
        l_sh = landmarks[11]
        r_sh = landmarks[12]
        shoulder_width_norm = abs(l_sh.x - r_sh.x)
        
        # 4. Генерация Evo-Grid (10x30)
        grid_data = self._generate_grid_from_segmentation(detection_result, 10, 30)
        
        # 5. Сборка профиля
        profile = AvatarProfileModel(
            user_id=user_id,
            shoulder_norm=round(shoulder_width_norm, 4),
            body_type="athletic" if shoulder_width_norm > 0.15 else "rectangle",
            completeness=self._calculate_completeness(landmarks),
            confidence=round(np.mean([lm.visibility for lm in landmarks]), 2),
            grid_10x30=BodyGrid(data=grid_data),
            keypoints={
                "left_shoulder": [l_sh.x, l_sh.y],
                "right_shoulder": [r_sh.x, r_sh.y],
                "left_hip": [landmarks[23].x, landmarks[23].y],
                "right_hip": [landmarks[24].x, landmarks[24].y]
            }
        )
        
        print(f"Extraction completed in {time.time() - start_time:.3f}s")
        return profile

    def _generate_grid_from_segmentation(self, result, cols: int, rows: int) -> List[List[float]]:
        """Генерация карты занятости на основе сегментационной маски."""
        if not result.segmentation_masks:
            return [[0.0] * cols for _ in range(rows)]
            
        mask = result.segmentation_masks[0].numpy_view()
        # Изменяем размер маски до 10x30
        grid = cv2.resize(mask, (cols, rows), interpolation=cv2.INTER_AREA)
        # Нормализуем в 0-1 и конвертируем в список
        return (grid / grid.max() if grid.max() > 0 else grid).tolist()

    def _calculate_completeness(self, landmarks) -> float:
        """Оценка полноты видимости фигуры (0.0 - 1.0)."""
        critical_points = [0, 11, 12, 23, 24, 27, 28] # Нос, плечи, бедра, лодыжки
        visibility = [landmarks[i].visibility for i in critical_points]
        return round(float(np.mean(visibility)), 2)

    def _get_fallback_profile(self, user_id, w, h, confidence=0.5) -> AvatarProfileModel:
        """Резервный профиль при ошибке детекции."""
        grid_data = [[0.0] * 10 for _ in range(30)]
        return AvatarProfileModel(
            user_id=user_id,
            shoulder_norm=0.1,
            body_type="rectangle",
            completeness=0.0,
            confidence=confidence,
            grid_10x30=BodyGrid(data=grid_data),
            keypoints={}
        )

    def validate_pose(self, profile: AvatarProfileModel) -> bool:
        """Качественный фильтр для B2B SDK."""
        if profile.confidence < 0.5: return False
        if profile.shoulder_norm < 0.05: return False
        return True

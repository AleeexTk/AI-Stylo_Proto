import numpy as np
import cv2
import os
from typing import Dict, List, Any, Optional

class WarpingEngine:
    """
    Движок реалистичного варпинга одежды (B2B Pro Mode).
    Использует Thin Plate Spline (TPS) для деформации ткани по точкам скелета.
    """
    
    def process_garment(self, item_img: Any) -> Any:
        """
        Препроцессинг изображения одежды (удаление фона, нормализация).
        В MVP возвращает изображение як є.
        """
        return item_img

    def align_garment(self, item_img: Any, landmarks: Dict[str, List[float]]) -> Any:
        """
        Аліас для warp_item_to_pose для роботи з Pipeline.
        """
        # PIL до numpy
        if hasattr(item_img, 'resize'): 
             import numpy as np
             from PIL import Image
             # Convert PIL to OpenCV (RGBA -> BGRA)
             item_np = np.array(item_img.convert("RGBA"))
             item_np = cv2.cvtColor(item_np, cv2.COLOR_RGBA2BGRA)
             
             # Warp
             warped_np = self.warp_item_to_pose(item_np, landmarks, (800, 600))
             
             # До PIL
             return Image.fromarray(cv2.cvtColor(warped_np, cv2.COLOR_BGRA2RGBA))
        
        return item_img

    def warp_item_to_pose(self, item_img: np.ndarray, landmarks: Dict[str, List[float]], target_size: tuple) -> np.ndarray:
        """
        Трансформирует одежду, используя ключевые точки (плечи, бедра, локти).
        """
        h_t, w_t = target_size
        h_i, w_i = item_img.shape[:2]
        
        # Точки на аватаре (Куда тянем)
        l_sh = landmarks.get("left_shoulder", [0.3, 0.2])
        r_sh = landmarks.get("right_shoulder", [0.7, 0.2])
        l_hp = landmarks.get("left_hip", [0.35, 0.6])
        r_hp = landmarks.get("right_hip", [0.65, 0.6])
        
        # Целевые точки в пикселях
        dst_pts = np.float32([
            [l_sh[0] * w_t, l_sh[1] * h_t],
            [r_sh[0] * w_t, r_sh[1] * h_t],
            [l_hp[0] * w_t, l_hp[1] * h_t],
            [r_hp[0] * w_t, r_hp[1] * h_t],
            [((l_sh[0] + r_sh[0])/2) * w_t, ((l_sh[1] + l_hp[1])/2) * h_t] # Центр груди
        ])
        
        # Точки на одежде (Откуда тянем - стандартная сетка для худи/футболок)
        src_pts = np.float32([
            [w_i * 0.2, h_i * 0.1], # Левое плечо
            [w_i * 0.8, h_i * 0.1], # Правое плечо
            [w_i * 0.2, h_i * 0.9], # Левый низ
            [w_i * 0.8, h_i * 0.9], # Правый низ
            [w_i * 0.5, h_i * 0.5]  # Центр
        ])
        
        # Используем TPS (Thin Plate Spline) если доступно, или мощную аффинную трансформацию
        # Для MVP используем Perspective Transform для лучшего объема чем Affine
        matrix = cv2.getPerspectiveTransform(src_pts[:4], dst_pts[:4])
        warped = cv2.warpPerspective(item_img, matrix, (w_t, h_t), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0,0))
        
        return warped

class CompositeRenderer:
    """
    Генератор финального изображения с учетом освещения и альфа-каналов.
    """
    
    def render(self, base_img: np.ndarray, warped_item: np.ndarray) -> np.ndarray:
        """
        Альфа-композиция с улучшенным смешиванием краев.
        """
        if warped_item.shape[2] == 4:
            # Разделяем каналы
            b, g, r, a = cv2.split(warped_item)
            overlay_color = cv2.merge((b, g, r))
            mask = a / 255.0
            
            # Размываем маску для мягких краев
            mask = cv2.GaussianBlur(mask, (3, 3), 0)
            
            result = base_img.copy()
            for c in range(3):
                result[:, :, c] = (base_img[:, :, c] * (1 - mask) + overlay_color[:, :, c] * mask)
            return result.astype(np.uint8)
        else:
            # Fallback для JPEG без альфы
            gray = cv2.cvtColor(warped_item, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
            mask = cv2.GaussianBlur(mask, (5, 5), 0) / 255.0
            
            result = base_img.copy()
            for c in range(3):
                result[:, :, c] = (base_img[:, :, c] * (1 - mask) + warped_item[:, :, c] * mask)
            return result.astype(np.uint8)

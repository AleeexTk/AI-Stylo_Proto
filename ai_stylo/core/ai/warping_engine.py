import numpy as np
from PIL import Image
import cv2

class WarpingEngine:
    """Двигун геометричної деформації одягу під скелет користувача."""
    
    def __init__(self):
        pass

    def process_garment(self, garment_img: Image.Image) -> Image.Image:
        """Видаляє фон з фото товару (Fast Shop Scraper logic)."""
        # В ідеалі тут u2net, але для швидкості - адаптивний поріг
        garment_cv = cv2.cvtColor(np.array(garment_img), cv2.COLOR_RGB2RGBA)
        gray = cv2.cvtColor(garment_cv, cv2.COLOR_RGBA2GRAY)
        _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        
        # Очищення маски
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        garment_cv[:, :, 3] = mask
        
        return Image.fromarray(garment_cv, 'RGBA')

    def get_garment_points(self, garment_img: Image.Image, category: str = "top") -> np.ndarray:
        """Визначає 4 ключові точки на самому одязі (кути трапеції торсу)."""
        w, h = garment_img.size
        # [Top-Left, Top-Right, Bottom-Left, Bottom-Right]
        if category == "top":
            return np.array([
                [w*0.15, h*0.1], [w*0.85, h*0.1], 
                [w*0.2, h*0.9], [w*0.8, h*0.9]
            ], dtype=np.float32)
        return np.array([[0,0], [w,0], [0,h], [w,h]], dtype=np.float32)

    def align_garment(self, garment: Image.Image, body_kp: dict, category: str = "top") -> Image.Image:
        """Поєднує одяг з тілом користувача через 4-точковий Perspective Warp."""
        s = body_kp.get("shoulders", [0,0,0,0])
        h = body_kp.get("hips", [0,0,0,0])
        
        # Цільові точки на тілі: [ls, rs, lh, rh]
        dst_pts = np.array([
            [s[0], s[1]], [s[2], s[3]], 
            [h[0], h[1]], [h[2], h[3]]
        ], dtype=np.float32)
        
        src_pts = self.get_garment_points(garment, category)
        
        # Використовуємо Perspective Transform замість афінного (для 4 точок)
        garment_cv = cv2.cvtColor(np.array(garment), cv2.COLOR_RGB2RGBA)
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        
        canvas_h, canvas_w = 512, 512 # Default target resize for SD
        warped_cv = cv2.warpPerspective(garment_cv, matrix, (canvas_w, canvas_h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0,0))
        
        return Image.fromarray(warped_cv, 'RGBA')

    def simple_affine_warp(self, garment_img: Image.Image, src_points: np.ndarray, dst_points: np.ndarray) -> Image.Image:
        """Геометрична деформація (Warp) через афінне перетворення (Fallback)."""
        garment_cv = cv2.cvtColor(np.array(garment_img), cv2.COLOR_RGB2RGBA)
        matrix = cv2.getAffineTransform(src_points[:3].astype(np.float32), dst_points[:3].astype(np.float32))
        h, w = garment_cv.shape[:2]
        warped_cv = cv2.warpAffine(garment_cv, matrix, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0,0))
        return Image.fromarray(warped_cv, 'RGBA')

    def tps_warp(self, garment_img: Image.Image, src_points: np.ndarray, dst_points: np.ndarray) -> Image.Image:
        """
        Більш складний Thin Plate Spline для реалістичних складок (Phase 2).
        Дозволяє нелінійно 'натягувати' тканину.
        """
        # TODO: Імплементувати TPS для фінальної версії
        return garment_img

import base64
import requests
import os
import random
import io
import json
import hashlib
import time
import cv2
import numpy as np
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont, ImageOps
from ai_stylo.core.ai.avatar_extractor import AvatarExtractor
from ai_stylo.core.ai.avatar_models import AvatarProfile
from ai_stylo.core.ai.warping_engine import WarpingEngine
from ai_stylo.core.ai.size_engine import SizeEngine

# Lazy loading heavy AI libs to prevent crash on non-AI envs
torch = None
diffusers = None
FaceDetector = None
BaseOptions = None

def _try_load_ai_libs():
    global torch, diffusers, FaceDetector, BaseOptions
    if torch is None:
        try:
            import torch as _torch
            torch = _torch
            from diffusers import StableDiffusionInpaintPipeline as _SDIP
            diffusers = _SDIP
            
            # MediaPipe Tasks API for Python 3.13+
            try:
                from mediapipe.tasks.python import vision
                from mediapipe.tasks.python.core import base_options
                FaceDetector = vision.FaceDetector
                BaseOptions = base_options.BaseOptions
            except Exception:
                pass
        except ImportError:
            pass

class VPConfig(BaseModel):
    ollama_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
    sd_url: str = os.getenv("SD_API_URL", "http://127.0.0.1:7860")
    local_model_id: str = os.getenv("LOCAL_VTON_MODEL", "runwayml/stable-diffusion-inpainting")
    use_local_ai: bool = os.getenv("ENABLE_LOCAL_AI", "0") == "1"
    fallback_image_url: str = "https://picsum.photos/id/{id}/600/800"
    # Динамічний вибір пристрою нижче

class VirtualTryOnPipeline:
    def __init__(self, config: Optional[VPConfig] = None):
        self.config = config or VPConfig()
        self._local_pipe = None
        self._face_app = None
        self._avatar_extractor = AvatarExtractor() 
        self._warping_engine = WarpingEngine() # Новий геометричний двигун
        self._size_engine = SizeEngine() # Аналітичне ядро розмірів
        
    def _init_local_core(self):
        """Ініціалізація локальної моделі з бронебійним фолбеком на CPU."""
        _try_load_ai_libs()
        if torch and diffusers and self._local_pipe is None:
            can_cuda = torch.cuda.is_available() and os.getenv("USE_CUDA", "1") == "1"
            target_device = "cuda" if can_cuda else "cpu"
            print(f"🧬 EvoPyramid: Attempting load on {target_device}...")
            
            try:
                dtype = torch.float16 if target_device == "cuda" else torch.float32
                self._local_pipe = diffusers.from_pretrained(
                    self.config.local_model_id,
                    torch_dtype=dtype,
                    use_safetensors=True,
                    low_cpu_mem_usage=True,
                    safety_checker=None,
                    requires_safety_checker=False
                ).to(target_device)
            except Exception as e:
                print(f"⚠️ {target_device.upper()} load failed: {e}. Switching to CPU fallback...")
                try:
                    # Чистий CPU запуск (найбільш сумісний)
                    self._local_pipe = diffusers.from_pretrained(
                        self.config.local_model_id,
                        torch_dtype=torch.float32,
                        low_cpu_mem_usage=True,
                        safety_checker=None,
                        requires_safety_checker=False
                    ).to("cpu")
                    print("✅ CPU Fallback successful.")
                except Exception as e2:
                    print(f"❌ Critical AI fail: {e2}")

    def _init_face_analyzer(self):
        """Ініціалізація аналізатора обличчя через MediaPipe Tasks."""
        _try_load_ai_libs()
        if FaceDetector and self._face_app is None:
            print("🧬 EvoPyramid: Loading Face Analytics System (MediaPipe Tasks)...")
            try:
                # Це потребує .tflite файлу. Якщо його немає — краще просто вийти тихо.
                # Але ми спробуємо базову ініціалізацію якщо можливо.
                # Для простоти прототипу, якщо FaceDetector не знайдено — ми використовуємо Smart Fallback в самому колажі.
                pass
            except Exception as e:
                print(f"❌ Face analyzer fail: {e}")

    def get_avatar_profile(self, photo_bytes: bytes, user_id: str = "guest", garment_metadata: Optional[dict] = None) -> dict:
        """Вилучає антропометричні дані, проводить Fit-аналіз та генерує теплову карту."""
        profile = self._avatar_extractor.extract(photo_bytes, user_id)
        # Додаємо аналіз розміру та теплову карту
        profile["fit_analysis"] = self._size_engine.analyze_fit(profile, garment_metadata)
        profile["fit_heatmap"] = self._size_engine.generate_fit_heatmap(profile, garment_metadata)
        return profile

    def get_size_analysis(self, avatar_data: dict, garment_metadata: Optional[dict] = None) -> dict:
        """Публічний доступ до аналітики розміру."""
        return self._size_engine.analyze_fit(avatar_data, garment_metadata)

    def generate_look(self, gender: str, user_desc: str, background_desc: str, items: List[str], photo_bytes: Optional[bytes] = None, user_id: str = "guest") -> Optional[bytes]:
        """
        Головний архітектурний Orchestrator.
        1. Preprocess: Вилучення анатомів (Avatar DNA)
        2. Mode Selection: Вибір між Local AI та Fallback
        3. Execution: Генерація образу
        """
        try:
            # 🟢 STAGE 1: [0.1] BIO_SCAN & ASSET_LOCK
            avatar_data = {}
            if photo_bytes:
                print(f"🛰️ [0.1] BIO_SCAN: Scanning skeletal structure for {user_id}...")
                avatar_data = self.get_avatar_profile(photo_bytes, user_id)
                fit = avatar_data.get("fit_analysis", {})
                print(f"🧬 [0.2] DNA_SYNC: Body type {avatar_data.get('body_type')} | Target size: {fit.get('recommended_size')} (Conf: {fit.get('confidence')})")

            # 🟢 STAGE 2: [0.4] GENERATIVE_CORE
            if self.config.use_local_ai:
                print(f"🚀 [0.5] GARMENT_WARP: Aligning assets to bone structure...")
                garment_url = items[0] if items and items[0].startswith("http") else None
                return self._generate_local_vton(gender, user_desc, background_desc, items, photo_bytes or b"", avatar_data, garment_url)

            # 🔵 STAGE 3: [0.9] EVOPYRAMID_FALLBACK
            print("🧬 [0.9] EVOPYRAMID_RENDER: Executing high-speed composite engine...")
            return self._generate_evo_composite(gender=gender, items=items, photo_bytes=photo_bytes, user_id=user_id)
            
        except Exception as e:
            print(f"🚨 Pipeline Orchestrator Critical Error: {e}")
            return self._generate_evo_composite(gender, items, photo_bytes, user_id)

    def _generate_local_vton(self, gender: str, desc: str, bg: str, items: List[str], photo_bytes: bytes, avatar_data: dict, garment_url: Optional[str] = None) -> Optional[bytes]:
        """Локальна генерація з використанням анатомічного маскування та варпінгу одягу."""
        if not photo_bytes: 
            return self._generate_evo_composite(gender, items)
            
        try:
            base_img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
            orig_w, orig_h = base_img.size
            
            # --- 🟢 STAGE: Garment Prep (Warping) ---
            warped_garment = None
            if garment_url:
                try:
                    g_resp = requests.get(garment_url, timeout=5)
                    g_img = Image.open(io.BytesIO(g_resp.content)).convert("RGBA")
                    g_processed = self._warping_engine.process_garment(g_img)
                    warped_garment = self._warping_engine.align_garment(g_processed, avatar_data.get("keypoints", {}))
                except Exception as ge:
                    print(f"⚠️ Garment Warping failed: {ge}")

            # --- PREP: Масштабування для SD 1.5 ---
            target_size = 512
            scale = target_size / min(orig_w, orig_h)
            new_w, new_h = (int(orig_w * scale) // 8) * 8, (int(orig_h * scale) // 8) * 8
            working_img = base_img.copy().resize((new_w, new_h), Image.LANCZOS)
            
            # 🟢 STAGE: Neural Masking (Anatomic Focus)
            kp = avatar_data.get("keypoints", {})
            mask = Image.new("L", (new_w, new_h), 0)
            draw = ImageDraw.Draw(mask)
            
            # Визначаємо зону тулуба на основі keypoints
            if "shoulders" in kp and "hips" in kp:
                s, h_k = kp["shoulders"], kp["hips"]
                # Координати: [ls.x, ls.y, rs.x, rs.y]
                # Створюємо ROI для маски
                bx1 = min(s[0], s[2], h_k[0], h_k[2]) * new_w
                by1 = min(s[1], s[3]) * new_h
                bx2 = max(s[0], s[2], h_k[0], h_k[2]) * new_w
                by2 = max(h_k[1], h_k[3]) * new_h
                # Розширюємо межі для 'природного' накладання
                draw.rectangle([bx1*0.8, by1*0.85, bx2*1.2, by2*1.15], fill=255)
                print("🦴 Anatomic Mask Applied: Pose-Focused")
            else:
                # Fallback маска: 70% центру
                draw.rectangle([new_w*0.1, new_h*0.25, new_w*0.9, new_h*0.95], fill=255)

            # Якщо є варплений одяг - накладаємо його як 'підказку' для AI
            if warped_garment:
                warped_resized = warped_garment.resize((new_w, new_h), Image.LANCZOS)
                working_img.paste(warped_resized, (0,0), warped_resized)

            # --- STAGE: Neural Rendering ---
            if not self._local_pipe: self._init_local_core()
            
            body_type = avatar_data.get("body_type", "standard")
            prompt = f"professional digital fashion, {gender} with {body_type} body, wearing {', '.join(items)}, {desc}, {bg}, realistic shadows and lighting, high quality fabric"
            negative_prompt = "cartoon, anime, bad hands, deformed, blurred face"
            
            output = self._local_pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=working_img,
                mask_image=mask,
                num_inference_steps=20,
                guidance_scale=8.0
            ).images[0]

            final_image = output.resize((orig_w, orig_h), Image.LANCZOS)
            buf = io.BytesIO()
            final_image.save(buf, format="PNG")
            return buf.getvalue()

        except Exception as e:
            print(f"❌ Local VTON Process Error: {e}")
            return self._generate_evo_composite(gender=gender, items=items, photo_bytes=photo_bytes, avatar_data=avatar_data)

    def _generate_external_sd(self, gender: str, items: List[str], photo_bytes: Optional[bytes], bg: str) -> Optional[bytes]:
        items_str = ", ".join(items) if items else "stylish outfit"
        gender_term = "man" if gender == "male" else "woman"
        sd_prompt = f"fashion photo, {gender_term}, wearing {items_str}, {bg}, high quality"
        
        try:
            endpoint = "/sdapi/v1/img2img" if photo_bytes else "/sdapi/v1/txt2img"
            sd_payload = {
                "prompt": sd_prompt,
                "negative_prompt": "ugly, lowres, text",
                "steps": 20,
                "width": 800,
                "height": 1000,
            }
            if photo_bytes:
                sd_payload["init_images"] = [base64.b64encode(photo_bytes).decode("utf-8")]
                sd_payload["denoising_strength"] = 0.55
                
            resp = requests.post(f"{self.config.sd_url}{endpoint}", json=sd_payload, timeout=10)
            resp.raise_for_status()
            return base64.b64decode(resp.json()["images"][0])
        except Exception as e:
            print(f"⚠️ SD API Failed, falling back to Evo engine: {e}")
            return self._generate_evo_composite(gender=gender, items=items, photo_bytes=photo_bytes)

    def _generate_evo_composite(self, gender: str, items: List[str], photo_bytes: Optional[bytes] = None, user_id: str = "guest", avatar_data: Optional[dict] = None) -> Optional[bytes]:
        """Власний двигун EvoPyramid: Створення преміального футуристичного колажу образу з ВАРПІНГОМ."""
        W, H = 800, 1000
        canvas = Image.new('RGB', (W, H), color='#0d0d12')
        draw = ImageDraw.Draw(canvas)
        
        # 🟢 1. Технічна сітка
        grid_color = '#001a22'
        for x in range(0, W, 40): draw.line([x, 0, x, H], fill=grid_color, width=1)
        for y in range(0, H, 40): draw.line([0, y, W, y], fill=grid_color, width=1)
        
        try:
            if photo_bytes:
                avatar_raw = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
            else:
                avatar_ids = [1005, 1011] if gender == 'male' else [1027, 342]
                avatar_url = self.config.fallback_image_url.format(id=random.choice(avatar_ids))
                avatar_raw = Image.open(io.BytesIO(requests.get(avatar_url, timeout=5).content)).convert("RGB")
            
            # Рендеримо головне фото (аватар)
            avatar_display = ImageOps.fit(avatar_raw, (550, 750))
            aw, ah = avatar_display.size
            canvas.paste(avatar_display, (125, 100))
            
            # --- 🧬 РЕАЛЬНИЙ ВАРПІНГ (LIGHT MODE) ---
            if avatar_data and items:
                # Беремо перший товар (CHEST)
                item_url = next((it for it in items if it.startswith("http")), None)
                if item_url:
                    try:
                        resp = requests.get(item_url, timeout=5)
                        item_img = cv2.imdecode(np.frombuffer(resp.content, np.uint8), cv2.IMREAD_UNCHANGED)
                        
                        # Отримуємо точки для варпінгу (ми знаємо, що аватар зміщено на 125, 100)
                        kp = avatar_data.get("keypoints", {})
                        if kp:
                            # Нормалізовані точки MediaPipe -> Координати на канвасі
                            # (x_norm * canvas_w + off_x, y_norm * canvas_h + off_y)
                            # Але AvatarExtractor працює з вхідним фото, а ми тут використовуємо 'fit' 550x750.
                            # Тому використовуємо точки відносно 1.0 і масштабуємо до aw, ah.
                            processed_kp = {
                                "left_shoulder": [kp["shoulders"][0], kp["shoulders"][1]],
                                "right_shoulder": [kp["shoulders"][2], kp["shoulders"][3]],
                                "left_hip": [kp["hips"][0], kp["hips"][1]],
                                "right_hip": [kp["hips"][2], kp["hips"][3]]
                            }
                            
                            # OpenCV warping
                            from ai_stylo.core.ai.warping_engine import CompositeRenderer as CR
                            warped_np = self._warping_engine.warp_item_to_pose(item_img, processed_kp, (ah, aw))
                            
                            # Накладання
                            warped_pil = Image.fromarray(cv2.cvtColor(warped_np, cv2.COLOR_BGRA2RGBA))
                            canvas.paste(warped_pil, (125, 100), warped_pil)
                            print(f"✅ EVO_WARP_SYNC: Success for {item_url}")
                    except Exception as e:
                        print(f"⚠️ EVO_WARP_FAIL: {e}")

            # 🟢 2. HUD Елементи
            draw.rectangle([120, 95, 680, 855], outline='#00f3ff', width=3)
            scan_y = int(time.time() * 100) % 750 + 100
            draw.line([125, scan_y, 675, scan_y], fill='#ff00ff', width=2)
            draw.text((130, scan_y-15), "NEURAL_SYNCING_GARMENT...", fill='#ff00ff')

        except Exception as e:
            print(f"🚨 Composite Error: {e}")
            draw.text((300, 480), "BIO_LINK_ERROR", fill='#ff0000')

        # 🟢 4. Текст та Мета-дані
        draw.text((310, 30), ">>> EVO_PYRAMID_GENESIS_CORE <<<", fill='#00f3ff')
        draw.text((50, H-60), f"DNA_GENDER: {gender.upper() if gender else 'UNK'}", fill='#00f3ff')
        draw.text((50, H-40), f"PROTOCOL: V1.1.0 NEURAL_WARP", fill='#00f3ff')
        
        # 5. Слоти екіпірування
        slot_pos = [(35, 150), (35, 450), (W-185, 150), (W-185, 450)]
        slot_names = ["HEAD", "CHEST", "LEGS", "FEET"]
        for i, pos in enumerate(slot_pos):
            # Фон слота
            draw.rectangle([pos[0], pos[1], pos[0]+150, pos[1]+150], outline='#ff00ff' if i==1 else '#330033', width=2)
            draw.rectangle([pos[0]+2, pos[1]+2, pos[0]+148, pos[1]+148], outline='#330033', width=1)
            
            draw.text((pos[0]+10, pos[1]-25), slot_names[i], fill='#ff00ff' if i==1 else '#660066')
            label = items[i] if i < len(items) else "VOID"
            if len(label) > 16: label = label[:13] + "..."
            draw.text((pos[0]+5, pos[1]+155), label.upper() if label else "VOID", fill='#ffffff')
            
            # Лінії зв'язку до аватару
            draw.line([pos[0]+150 if pos[0]<W/2 else pos[0], pos[1]+75, 400, 400+i*50], fill='#00f3ff', width=1)

        # 🟢 6. Прогрес-бар внизу
        draw.rectangle([150, 910, 650, 940], outline='#00ff00', width=2)
        bar_w = int(500 * (0.98))
        draw.rectangle([155, 915, 155+bar_w, 935], fill='#00ff00')
        draw.text((320, 890), "NEURAL_SYNC: OPTIMAL [100%]", fill='#00ff00')

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

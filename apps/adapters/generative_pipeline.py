import base64
import requests
import os
from typing import Optional, List
from pydantic import BaseModel

class VPConfig(BaseModel):
    ollama_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
    sd_url: str = os.getenv("SD_API_URL", "http://127.0.0.1:7860")
    sd_steps: int = int(os.getenv("SD_STEPS", "20"))
    sd_cfg: float = float(os.getenv("SD_CFG", "7.0"))
    sd_width: int = int(os.getenv("SD_WIDTH", "800"))
    sd_height: int = int(os.getenv("SD_HEIGHT", "1000"))
    sd_negative_prompt: str = os.getenv("SD_NEGATIVE_PROMPT", "ugly, deformed, lowres, bad anatomy, bad hands, text, watermark")


class VirtualTryOnPipeline:
    def __init__(self, config: Optional[VPConfig] = None):
        self.config = config or VPConfig()
        
    def generate_look(self, gender: str, user_desc: str, background_desc: str, items: List[str], photo_bytes: Optional[bytes] = None) -> Optional[bytes]:
        # 1. Запитуємо Ollama згенерувати промпт
        items_str = ", ".join(items) if items else "stylish casual outfit"
        gender_term = "man" if gender == "male" else "woman"
        
        ollama_payload = {
            "model": self.config.ollama_model,
            "stream": False,
            "messages": [{
                "role": "system",
                "content": "You are an expert Stable Diffusion prompt engineer for fashion photography. Given the user details, output ONLY a comma-separated list of highly detailed English keywords for image generation. No explanations, no markdown formatting."
            }, {
                "role": "user",
                "content": f"Subject: a fashionable {gender_term}. Looks: {user_desc}. Wearing: {items_str}. Setting: {background_desc}. Style: photorealistic, 8k, highly detailed."
            }]
        }
        
        print(f"🧠 Asking Ollama for prompt...")
        try:
            chat_resp = requests.post(f"{self.config.ollama_url}/api/chat", json=ollama_payload, timeout=30)
            chat_resp.raise_for_status()
            sd_prompt = chat_resp.json().get("message", {}).get("content", "").strip()
            # Basic cleanup if model outputted quotes or newlines
            sd_prompt = sd_prompt.replace('\n', ' ').strip('"').strip("'")
            print(f"✅ Ollama Prompt: {sd_prompt}")
        except Exception as e:
            print(f"⚠️ Ollama Error: {e}. Falling back to basic prompt.")
            # Fallback prompt
            sd_prompt = f"high quality fashion photo, {gender_term}, {user_desc}, wearing {items_str}, {background_desc}, 8k, photorealistic"

        # 2. Відправляємо на локальний SD (A1111)
        endpoint = "/sdapi/v1/img2img" if photo_bytes else "/sdapi/v1/txt2img"
        sd_payload = {
            "prompt": sd_prompt,
            "negative_prompt": self.config.sd_negative_prompt,
            "steps": self.config.sd_steps,
            "cfg_scale": self.config.sd_cfg,
            "width": self.config.sd_width,
            "height": self.config.sd_height,
        }
        
        if photo_bytes:
            # Add init image for img2img
            b64_image = base64.b64encode(photo_bytes).decode("utf-8")
            sd_payload["init_images"] = [b64_image]
            sd_payload["denoising_strength"] = 0.55 # allow some variation but keep face/pose
            
        print(f"🎨 Sending to SD WebUI ({endpoint})...")
        try:
            resp = requests.post(f"{self.config.sd_url}{endpoint}", json=sd_payload, timeout=120)
            resp.raise_for_status()
            result_json = resp.json()
            images = result_json.get("images", [])
            if not images:
                raise ValueError("No images returned from SD API")
            
            # SD returns base64 strings
            img_b64 = images[0]
            # Sometimes it has prefix "data:image/png;base64,"
            if img_b64.startswith("data:image"):
                img_b64 = img_b64.split(",", 1)[1]
                
            return base64.b64decode(img_b64)
            
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection Error: Could not connect to SD at {self.config.sd_url}")
            return None
        except Exception as e:
            print(f"❌ SD Generation Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(e.response.text)
            return None

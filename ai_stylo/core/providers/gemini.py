import os
import json
from typing import Optional, Dict, Any, List

try:
    import google.generativeai as genai
except ImportError:
    genai = None

class GeminiProvider:
    """
    Stabilized Gemini 1.5 provider with optional package handling.
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        if genai is None:
            # We don't raise here yet to allow the system to start with mock/ollama
            self.client = None
            return

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            self.client = None
            return

        genai.configure(api_key=self.api_key)
        self.model_name = model or os.getenv("GEMINI_MODEL", "gemini-1.5-pro-latest")
        self.client = genai.GenerativeModel(self.model_name)

    def is_available(self) -> bool:
        return self.client is not None

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        if not self.is_available():
            return "Gemini not available (API key or package missing)."
        
        try:
            response = self.client.generate_content(
                prompt,
                generation_config={"temperature": temperature},
            )
            return getattr(response, "text", "") or ""
        except Exception as e:
            return f"Gemini Error: {str(e)}"

    def summarize_session(self, chat_history: List[str], user_profile: Dict[str, Any]) -> str:
        history_text = "\n".join(chat_history[-20:])
        prompt = f"Summarize user style preferences based on chat history and profile: {history_text}\nProfile: {json.dumps(user_profile)}"
        return self.generate_text(prompt, temperature=0.3)

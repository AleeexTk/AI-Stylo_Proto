from typing import Dict, Any, Optional, Literal
from ..providers.gemini import GeminiProvider

# Mock or existing Ollama provider could be imported here
class MockOllamaProvider:
    def generate(self, prompt: str) -> str:
        return f"Ollama Mock: {prompt[:50]}..."

class Router:
    """
    Self-healing router that falls back to Ollama/Local if Gemini is unavailable.
    Based on AI-Stylo v1.0 specifications.
    """
    def __init__(self, ollama: Optional[Any] = None, gemini: Optional[GeminiProvider] = None):
        self.ollama = ollama or MockOllamaProvider()
        self.gemini = gemini or GeminiProvider()

    def route(self, user_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        msg = (user_message or "").lower()
        
        # 1. Outfit Selection (Handled by Catalog/Outfit Service)
        if any(word in msg for word in ["образ", "лук", "комплект", "outfit"]):
            return {"action": "generate_outfit", "provider": "local_engine"}

        # 2. Deep Qualitative Analysis (Prefer Gemini)
        if (len(user_message) > 200 or "почему" in msg or "анализ" in msg) and self.gemini.is_available():
            return {
                "action": "gemini_analysis", 
                "provider": "gemini",
                "result": self.gemini.generate_text(user_message)
            }

        # 3. Fast Response / Fallback (Ollama/Local)
        return {
            "action": "fast_chat", 
            "provider": "ollama",
            "result": self.ollama.generate(user_message)
        }

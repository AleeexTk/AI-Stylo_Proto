from typing import Protocol, Dict, Any, Optional

class TryOnProvider(Protocol):
    def generate(self, avatar_url: str, item_url: str, options: Optional[Dict[str, Any]] = None) -> str:
        """Returns the result image URL."""
        ...

class FalProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate(self, avatar_url: str, item_url: str, options: Optional[Dict[str, Any]] = None) -> str:
        # Placeholder for real Fal.ai logic
        print(f"[Fal] Processing Try-On for {avatar_url} with {item_url}")
        return f"https://fal.ai/results/fake_result_{hash(avatar_url + item_url)}.png"

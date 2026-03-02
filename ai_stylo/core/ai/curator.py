import json
import logging
from typing import Any, Dict, List, Optional
from ai_stylo.adapters.ollama_adapter import OllamaAdapter

logger = logging.getLogger("ai_stylo.curator")

class CatalogCurator:
    """
    AI-Curator for Stylescape.
    Evaluates incoming items against the brand's aesthetic guidelines (Dark Avant-Garde, Cyber-Grunge, Contemporary).
    Translates Ukrainian descriptions and generates appropriate tags.
    """

    AESTHETIC_GUIDELINES = """
    # Stylescape Brand Guidelines
    Vibe: Dark Avant-Garde, Cyber-Grunge, High-End Streetwear, Contemporary Minimalist.
    Acceptable Categories: Statement pieces, oversized silhouettes, distressed textures, techwear, architectural cuts, monochrome palettes (black, dark grey, washed tones) with rare striking accents (like red or chrome).
    Unacceptable: Basic fast-fashion (generic t-shirts without statement design), bright floral patterns (unless ironically dark), generic athleisure, cheap-looking materials, "cute" or "preppy" styles.
    """

    def __init__(self, ollama_adapter: OllamaAdapter):
        self.ollama = ollama_adapter

    def curate_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes raw item data (from Kasta, Gepur, etc.), analyzes it via LLM,
        and returns a structured decision.
        """
        title = item_data.get("title", "")
        description = item_data.get("description", "")
        brand = item_data.get("brand", "")
        price = item_data.get("price", 0)
        
        prompt = f"""
        You are the Head Buyer and Art Director for Stylescape, an avant-garde virtual try-on boutique.
        Your task is to evaluate a new clothing item and decide if it fits the boutique's aesthetic.

        {self.AESTHETIC_GUIDELINES}

        # Item to Evaluate:
        Title (Original): {title}
        Brand: {brand}
        Description: {description}
        Price: {price} UAH

        # Instructions:
        1. Evaluate if the item fits the Stylescape vibe based on its title and description.
        2. Decide "APPROVE" or "REJECT".
        3. If APPROVED:
           - Translate Title to English (name_en) and Ukrainian (name_uk).
           - Translate Description to English (description_en) and Ukrainian (description_uk).
           - Generate 3-5 relevant style tags (e.g., "cyberpunk", "avant-garde", "minimalist").
           - Determine the most fitting category (Tops, Bottoms, Dresses, Outerwear, Accessories, Suits).
           - Determine gender (male, female, unisex).

        Respond STRICTLY in JSON format with the following schema:
        {{
            "decision": "APPROVE" or "REJECT",
            "reason": "Short explanation of the decision",
            "name_en": "Translated title",
            "name_uk": "Translated title or original if already UK",
            "description_en": "Translated desc",
            "description_uk": "Translated desc or original",
            "tags": ["tag1", "tag2"],
            "category": "Tops/Bottoms/etc.",
            "gender": "male/female/unisex"
        }}
        """

        messages = [
            {"role": "system", "content": "You are a highly opinionated fashion curator. You only output valid JSON."},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Curating item: {title} ({brand})")
        
        try:
            # We don't use tools here, just JSON mode for structured extraction.
            # Assuming OllamaAdapter has a way to enforce JSON or we parse it.
            response = self.ollama.chat(messages=messages, tools=[])
            content = response.get("message", {}).get("content", "")
            
            # Simple cleanup to parse JSON out of potential markdown blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()

            result_data = json.loads(content)
            
            # Ensure required fields exist even if LLM hallucinated
            if "decision" not in result_data:
                result_data["decision"] = "REJECT"
                result_data["reason"] = "JSON parse failure - missing decision flag."

            return result_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Curator JSON: {content}")
            return {"decision": "REJECT", "reason": "AI failed to format response correctly."}
        except Exception as e:
            logger.error(f"Curator AI error: {str(e)}")
            return {"decision": "REJECT", "reason": f"System error: {str(e)}"}

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from ai_stylo.core.contracts import Item
from ai_stylo.adapters.ollama_adapter import OllamaAdapter

@dataclass
class SelectorMap:
    domain: str
    container: str  # Selector for the product block
    title: str
    price: str
    image: str
    link: str
    size_options: Optional[str] = None
    material: Optional[str] = None

class AgenticInterface:
    """
    Universal Management Layer for external fashion sites.
    Handles DOM mapping, selector learning, and item extraction.
    """
    def __init__(self, ollama_adapter: OllamaAdapter):
        self.ollama = ollama_adapter
        self.selector_cache: Dict[str, SelectorMap] = {}
        self.logger = logging.getLogger("ai_stylo.agentic")

    def map_external_site(self, url: str, dom_snapshot: str) -> SelectorMap:
        """
        Learns selectors for a new domain using a DOM snapshot fragment.
        In production, this result is cached indexed by domain.
        """
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        if domain in self.selector_cache:
            return self.selector_cache[domain]

        self.logger.info(f"Learning selectors for domain: {domain}")
        
        # We ask the LLM to identify the CSS selectors from a DOM fragment
        system_prompt = (
            "You are a DOM Parser Expert. Analyze the following HTML/DOM fragment and identify CSS selectors "
            "for a fashion product item. You must return a JSON object with: "
            "'container', 'title', 'price', 'image', 'link', 'size_options'."
        )
        
        # We take a sample of the DOM to avoid token overflow
        dom_fragment = dom_snapshot[:4000] 
        
        response = self.ollama.chat(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"DOM Fragment:\n{dom_fragment}"}
        ])
        
        try:
            # Attempt to parse response as JSON
            raw_text = response.get("message", {}).get("content", "{}")
            # Cleaning possible markdown code blocks
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[-1].split("```")[0]
            elif "```" in raw_text:
                 raw_text = raw_text.split("```")[-1].split("```")[0]
            
            data = json.loads(raw_text.strip())
            
            s_map = SelectorMap(
                domain=domain,
                container=data.get("container", ".product-item"),
                title=data.get("title", "h1, .title"),
                price=data.get("price", ".price"),
                image=data.get("image", "img"),
                link=data.get("link", "a"),
                size_options=data.get("size_options")
            )
            self.selector_cache[domain] = s_map
            return s_map
        except Exception as e:
            self.logger.error(f"Failed to learn selectors: {e}")
            # Fallback to generic selectors
            return SelectorMap(domain, ".product", ".title", ".price", "img", "a")

    def extract_items(self, dom_snapshot: str, site_map: SelectorMap) -> List[Item]:
        """
        Extracts structured data from a DOM snapshot using a site map.
        In an actual extension context, this logic would likely live in JavaScript (Content Script).
        This Python version uses BeautifulSoup to simulate normalization.
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(dom_snapshot, 'html.parser')
        
        items = []
        containers = soup.select(site_map.container)
        
        self.logger.info(f"Extracting items from {site_map.domain} (found {len(containers)} containers)")
        
        for idx, container in enumerate(containers):
            try:
                title_elem = container.select_one(site_map.title)
                price_elem = container.select_one(site_map.price)
                image_elem = container.select_one(site_map.image)
                link_elem = container.select_one(site_map.link)
                
                title = title_elem.get_text(strip=True) if title_elem else "Unknown Item"
                image = image_elem.get('src', '') if image_elem else ""
                link = link_elem.get('href', '') if link_elem else ""
                
                price_text = price_elem.get_text(strip=True) if price_elem else "0.0"
                # Simple price parsing: remove currency symbols and non-digits (except decimal)
                import re
                price_digits = re.sub(r'[^\d.]', '', price_text)
                price = float(price_digits) if price_digits else 0.0
                
                item = Item(
                    id=f"{site_map.domain}_{idx}",
                    title=title,
                    brand=site_map.domain,
                    price=price,
                    image=image,
                    description=f"Auto-extracted from {site_map.domain}",
                    tags=[site_map.domain, "extracted"]
                )
                items.append(item)
            except Exception as e:
                self.logger.warning(f"Failed to extract item {idx}: {e}")
                
        return items

    def build_action_manifest(self, site_map: SelectorMap) -> Dict[str, Any]:
        """
        Returns a set of 'Agentic Actions' that the Chrome Extension can execute on the page.
        """
        return {
            "can_purchase": True,
            "actions": [
                {
                    "id": "add_to_cart",
                    "selector": site_map.link, # Or a more specific CTA selector if known
                    "label": "Add to Basket",
                    "requires_size": bool(site_map.size_options)
                },
                {
                    "id": "check_fit",
                    "label": "Check My Size",
                    "local_processing": True
                }
            ]
        }

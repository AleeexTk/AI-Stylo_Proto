import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
import json
import re

class CatalogImporter:
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    async def import_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

class GepurImporter(CatalogImporter):
    """
    Importer for gepur.com
    """
    async def import_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Try to find JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            ld_data = {}
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if data.get('@type') == 'Product':
                        ld_data = data
                        break
                except:
                    continue
            
            title = ld_data.get('name') or soup.find('h1').text.strip()
            price = 0.0
            if 'offers' in ld_data:
                price = float(ld_data['offers'].get('price', 0))
            
            brand = ld_data.get('brand', {}).get('name') or "Gepur"
            
            # Image
            image = ld_data.get('image')
            if isinstance(image, list): image = image[0]
            if not image:
                img_tag = soup.find('img', class_='main-product-image') or soup.find('meta', property='og:image')
                image = img_tag.get('content') if img_tag else ""

            description = ld_data.get('description') or ""
            
            return {
                "id": url.split('/')[-1].split('-')[-1], # Extract ID from slug
                "merchant_id": self.merchant_id,
                "title": title,
                "brand": brand,
                "price": price,
                "image_url": image,
                "url": url,
                "description": description,
                "category": "Casual", # Default or extract from breadcrumbs
                "metadata": {
                    "source": "scraper",
                    "id_raw": ld_data.get('sku') or url.split('/')[-1]
                }
            }

class VovkImporter(CatalogImporter):
    """
    Importer for vovk.com
    """
    async def import_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            title = soup.find('h1').text.strip()
            
            # Price extraction - looks for text with '₴' or similar
            price_text = ""
            price_elem = soup.find(class_='product-price') or soup.find(class_='price')
            if price_elem:
                price_text = price_elem.text
            else:
                # Fallback: search anywhere for price pattern
                match = re.search(r'(\d[\d\s]+)\s*₴', resp.text)
                if match:
                    price_text = match.group(1)
            
            price = float(re.sub(r'[^\d.]', '', price_text.replace(' ', '')) or 0)
            
            # Image
            img_tag = soup.find('meta', property='og:image')
            image = img_tag.get('content') if img_tag else ""
            
            return {
                "id": url.strip('/').split('/')[-1],
                "merchant_id": self.merchant_id,
                "title": title,
                "brand": "VOVK",
                "price": price,
                "image_url": image,
                "url": url,
                "description": soup.find(id='tab-description').text.strip() if soup.find(id='tab-description') else "",
                "category": "Casual",
                "metadata": {"source": "scraper"}
            }

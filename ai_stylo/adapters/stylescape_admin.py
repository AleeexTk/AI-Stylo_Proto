import json
import logging
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

logger = logging.getLogger("ai_stylo.stylescape_admin")

class StylescapeAdminClient:
    """
    Client for interacting with the Stylescape Admin API.
    Used by AI-Stylo (AI-Curator) to automatically populate the catalog or update products.
    """
    BASE_URL = "https://stylescape-api-709179367220.us-central1.run.app/api/v1/admin"
    VALID_CATEGORIES = {"Tops", "Bottoms", "Dresses", "Outerwear", "Accessories", "Suits"}
    
    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as response:
                result = response.read()
                return json.loads(result) if result else {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            logger.error(f"Stylescape API Error [{e.code}]: {error_body}")
            raise Exception(f"Stylescape API Error {e.code}: {error_body}")

    def create_product(self, product_data: Dict[str, Any]) -> str:
        """Step 1: Create the base product."""
        result = self._request("POST", "/products", payload=product_data)
        product_id = result.get("id") or result.get("productId")
        if not product_id and isinstance(result, str):
            product_id = result
        return product_id

    def get_image_upload_url(self, product_id: str, filename: str, image_type: str = "front", content_type: str = "image/jpeg") -> Dict[str, Any]:
        """Step 2: Get a signed URL to upload an image."""
        payload = {
            "content_type": content_type,
            "filename": filename,
            "image_type": image_type
        }
        return self._request("POST", f"/products/{product_id}/images/upload-url", payload=payload)

    def upload_image_to_signed_url(self, signed_url: str, image_bytes: bytes, content_type: str) -> None:
        """Step 2.5: Upload the actual binary bytes to Google Cloud Storage via the signed URL."""
        headers = {"Content-Type": content_type}
        req = urllib.request.Request(signed_url, data=image_bytes, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req) as response:
                logger.info(f"Image uploaded to GCP Storage successfully. Status: {response.status}")
        except urllib.error.HTTPError as e:
            logger.error(f"GCP Storage Upload Error [{e.code}]: {e.read().decode('utf-8')}")
            raise Exception(f"Failed to upload image to GCP Storage: {e.code}")

    def link_image_to_product(self, product_id: str, image_url: str, is_primary: bool = True, image_type: str = "front") -> Dict[str, Any]:
        """Step 3: Tell the backend about the finished image upload."""
        payload = {
            "is_primary": is_primary,
            "type": image_type,
            "url": image_url
        }
        return self._request("POST", f"/products/{product_id}/images", payload=payload)

    def import_and_upload_item(self, standardized_item: Any, source_image_url: str) -> str:
        """
        AI-Curator Macro: Creates the product, downloads the image from source,
        uploads it to Stylescape, and links it.
        """
        # 1. Map to Stylescape Schema
        product_payload = {
            "name": getattr(standardized_item, "title", "AI-Curated Item"),
            "description": getattr(standardized_item, "description", ""),
            "name_en": getattr(standardized_item, "title", ""),
            "name_uk": getattr(standardized_item, "title", ""),
            "description_en": getattr(standardized_item, "description", ""),
            "description_uk": getattr(standardized_item, "description", ""),
            "external_url": getattr(standardized_item, "url", ""),
            "brand": getattr(standardized_item, "brand", "AI-Stylo Curated"),
            "category": getattr(standardized_item, "category", "tops").lower(),
            "price": {
                "amount": getattr(standardized_item, "price", 0),
                "currency": getattr(standardized_item, "currency", "UAH")
            },
            "images": [],
            "gender": getattr(standardized_item, "gender", "unisex"),
            "look": False,
            "tryon_compatible": True,
            "tryon_image_url": "",
            "tags": getattr(standardized_item, "tags", [])
        }
        
        # 2. Create product
        product_id = self.create_product(product_payload)
        logger.info(f"Created product {product_id} in Admin DB.")

        # 3. Download source image
        try:
            req = urllib.request.Request(source_image_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                image_bytes = response.read()
                content_type = response.headers.get_content_type() or "image/jpeg"
        except Exception as e:
            logger.error(f"Failed to download source image from {source_image_url}: {e}")
            return product_id # Return ID even if image fails

        # 4. Get Upload URL
        filename = f"{product_id}_front.jpg"
        upload_data = self.get_image_upload_url(product_id, filename=filename, content_type=content_type)
        signed_url = upload_data.get("uploadUrl", upload_data.get("upload_url"))
        final_image_url = upload_data.get("imageUrl", upload_data.get("image_url"))

        if not signed_url or not final_image_url:
            logger.error(f"Invalid upload URL response: {upload_data}")
            return product_id

        # 5. Upload bytes to GCP
        self.upload_image_to_signed_url(signed_url, image_bytes, content_type)

        # 6. Link image to product
        self.link_image_to_product(product_id, final_image_url, is_primary=True, image_type="front")
        logger.info(f"Successfully linked image {final_image_url} to product {product_id}.")

        return product_id

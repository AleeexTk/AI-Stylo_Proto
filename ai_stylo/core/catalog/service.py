from typing import List, Optional
from sqlalchemy.orm import Session
from ..models import Product
from datetime import datetime, timezone

class CatalogService:
    def __init__(self, db: Session):
        self.db = db

    def upsert_product(self, product_data: dict) -> Product:
        """
        Create or update a product in the catalog.
        """
        product_id = product_data.get("id")
        merchant_id = product_data.get("merchant_id")
        
        product = self.db.query(Product).filter(
            Product.id == product_id,
            Product.merchant_id == merchant_id
        ).first()
        
        if not product:
            product = Product(id=product_id, merchant_id=merchant_id)
            self.db.add(product)
            
        product.title = product_data.get("title", product.title)
        product.brand = product_data.get("brand", product.brand)
        product.price = product_data.get("price", product.price)
        product.currency = product_data.get("currency", "UAH")
        product.image_url = product_data.get("image_url", product.image_url)
        product.url = product_data.get("url", product.url)
        product.description = product_data.get("description", product.description)
        product.category = product_data.get("category", product.category)
        product.meta_data = product_data.get("metadata", product.meta_data)
        product.created_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return product

    def get_products(self, merchant_id: str, category: Optional[str] = None) -> List[Product]:
        query = self.db.query(Product).filter(Product.merchant_id == merchant_id)
        if category:
            query = query.filter(Product.category == category)
        return query.all()

    def get_product(self, merchant_id: str, product_id: str) -> Optional[Product]:
        return self.db.query(Product).filter(
            Product.merchant_id == merchant_id,
            Product.id == product_id
        ).first()

    def get_all(self, limit: int = 100) -> List[Product]:
        return self.db.query(Product).limit(limit).all()

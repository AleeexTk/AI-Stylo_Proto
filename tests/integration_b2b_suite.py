import sys
import os
from pathlib import Path
import io
import unittest
from PIL import Image

# Setup path so we can import apps
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from ai_stylo.core.ai.size_engine import SizeEngine
from ai_stylo.core.ai.warping_engine import WarpingEngine
from ai_stylo.core.scraping.catalog_scraper import CatalogScraper
from ai_stylo.adapters.generative_pipeline import VirtualTryOnPipeline

class TestB2BPipeline(unittest.TestCase):
    """
    Автоматизований тест тех-стеку B2B AI-Stylo.
    Перевіряє взаємодію бекенд-модулів (Scraper, SizeEngine, Warping, Pipeline).
    """

    def setUp(self):
        self.size_engine = SizeEngine()
        self.warping_engine = WarpingEngine()
        self.scraper = CatalogScraper()
        self.pipeline = VirtualTryOnPipeline()

    def test_01_size_engine_multi_brand(self):
        """Перевірка логіки мульті-брендових розмірів."""
        print("\n🧪 Testing SizeEngine: Multi-Brand logic...")
        mock_avatar = {
            "measurements": {"shoulder_width": 100},
            "completeness": 0.9,
            "pose_type": "straight",
            "body_type": "standard"
        }
        
        # Test Nike (Oversize bias 1.1) -> should be M
        res_nike = self.size_engine.analyze_fit(mock_avatar, {"brand_id": "nike_fit"})
        print(f"   [NIKE] Rec size: {res_nike['recommended_size']} | Fit: {res_nike['fit_hint']}")
        self.assertEqual(res_nike["recommended_size"], "S") # 100/1.1 = 90. 90 in Nike grid [85, 100] is S
        
        # Test Zara (Slim bias 0.92) -> should be M/L
        res_zara = self.size_engine.analyze_fit(mock_avatar, {"brand_id": "zara_style"})
        print(f"   [ZARA] Rec size: {res_zara['recommended_size']} | Fit: {res_zara['fit_hint']}")
        # 100/0.92 = 108. 108 in Zara grid is L ([106, 120])
        self.assertEqual(res_zara["recommended_size"], "L")

    def test_02_tension_heatmap_generation(self):
        """Перевірка генерації теплової карти."""
        print("\n🧪 Testing Heatmap: Grid 10x30 tension...")
        # Mock grid 10x30
        mock_grid = [[[c/10, r/30] for c in range(10)] for r in range(30)]
        avatar = {
            "measurements": {"shoulder_width": 120}, # Large shoulders
            "grid_map": mock_grid
        }
        heatmap_res = self.size_engine.generate_fit_heatmap(avatar, {"brand_id": "zara_style"})
        heatmap = heatmap_res["heatmap"]
        
        self.assertEqual(len(heatmap), 30)
        self.assertEqual(len(heatmap[0]), 10)
        print(f"   Heatmap generated: {len(heatmap)}x{len(heatmap[0])} sectors")
        print(f"   Max tension: {heatmap_res['max_tension']} | Hotspots: {heatmap_res['hotspots']}")

    def test_03_catalog_scraper(self):
        """Перевірка скрапера на публічному сайті."""
        print("\n🧪 Testing Scraper: Product extraction...")
        # Використовуємо актуальний URL зі списку demo або перевірений
        test_url = "https://gepur.com/product/49230" 
        product = self.scraper.scrape_product(test_url)
        if product:
            print(f"   Scraped: {product['name']} | Price: {product['price']} | Cat: {product['category']}")
            self.assertIn("image", product)
        else:
            print("   ⚠️ Scraper failed (Check connection or URL)")

    def test_04_warping_integrity(self):
        """Перевірка цілісності геометричного варпінгу."""
        print("\n🧪 Testing WarpingEngine: Perspective Align...")
        g_img = Image.new("RGBA", (500, 500), color=(255, 0, 0, 255))
        kp = {
            "shoulders": [100, 100, 400, 100],
            "hips": [120, 400, 380, 400]
        }
        warped = self.warping_engine.align_garment(g_img, kp)
        # Очікуємо 512x512 (стандарт SD)
        self.assertEqual(warped.size, (512, 512))
        print(f"   Warping completed on RGBA asset (Target: 512x512).")

if __name__ == "__main__":
    unittest.main()

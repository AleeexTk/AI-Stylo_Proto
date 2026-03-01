import uuid
import time
import requests
import io
import numpy as np
import cv2
from sqlalchemy.orm import Session
from typing import Optional
from ai_stylo.core.models import TryOnJob, Product
from .cache import TryOnCache
from .providers.base import TryOnProvider
from .avatar_extractor import AvatarExtractor
from ..core.ai.warping_engine import WarpingEngine, CompositeRenderer
from ..core.ai.size_engine import SizeEngine

class JobStatus:
    PENDING = "pending"
    ANALYSIS = "avatar_analysis"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"

class TryOnJobManager:
    def __init__(self, db: Session, provider: TryOnProvider, cache: TryOnCache):
        self.db = db
        self.provider = provider
        self.cache = cache
        self.extractor = AvatarExtractor()
        self.warper = WarpingEngine()
        self.renderer = CompositeRenderer()
        self.size_engine = SizeEngine()

    def create_job(self, merchant_id: str, user_id: str, avatar_url: str, item_url: str, outfit_id: str) -> TryOnJob:
        cache_key = self.cache.get_key(avatar_url, outfit_id)
        cached_result = self.cache.get(cache_key)
        
        if cached_result:
            return TryOnJob(
                id=f"cached_{cache_key[:8]}",
                merchant_id=merchant_id,
                user_id=user_id,
                status=JobStatus.COMPLETED,
                avatar_url=avatar_url,
                item_url=item_url,
                cache_key=cache_key,
                result_url=cached_result,
                progress=1.0
            )
            
        job_id = str(uuid.uuid4())
        job = TryOnJob(
            id=job_id,
            merchant_id=merchant_id,
            user_id=user_id,
            status=JobStatus.PENDING,
            avatar_url=avatar_url,
            item_url=item_url,
            cache_key=cache_key,
            progress=0.05,
            model_version="v1.1-autumn"
        )
        self.db.add(job)
        self.db.commit()
        return job

    def process_job(self, job_id: str):
        job = self.db.query(TryOnJob).filter(TryOnJob.id == job_id).first()
        if not job or job.status == JobStatus.COMPLETED:
            return
            
        try:
            # 1. Анализ аватара (STAGE_ANALYSIS)
            if job.status == JobStatus.PENDING:
                print(f"[{job_id}] Phase: Analysis...")
                response = requests.get(job.avatar_url, timeout=10)
                profile = self.extractor.extract_from_bytes(response.content, user_id=job.user_id)
                
                # Sizing Logic Integration
                product = self.db.query(Product).filter(Product.url == job.item_url).first()
                product_meta = product.meta_data if product else {"brand": "Generic"}
                size_suggestion = self.size_engine.suggest_size(profile.dict(), product_meta)
                
                job.meta_data = {
                    "avatar_profile": profile.dict(),
                    "size_recommendation": size_suggestion
                }
                job.status = JobStatus.ANALYSIS
                job.progress = 0.3
                self.db.commit()

            # 2. Рендеринг (Warp -> Composite)
            if job.status == JobStatus.ANALYSIS:
                print(f"[{job_id}] Phase: Rendering...")
                profile_data = job.meta_data.get("avatar_profile", {})
                landmarks = profile_data.get("keypoints", {})
                
                avatar_resp = requests.get(job.avatar_url, timeout=10)
                item_resp = requests.get(job.item_url, timeout=10)
                
                avatar_img = cv2.imdecode(np.frombuffer(avatar_resp.content, np.uint8), cv2.IMREAD_COLOR)
                item_img = cv2.imdecode(np.frombuffer(item_resp.content, np.uint8), cv2.IMREAD_UNCHANGED)
                
                warped = self.warper.warp_item_to_pose(item_img, landmarks, (avatar_img.shape[0], avatar_img.shape[1]))
                result_img = self.renderer.render(avatar_img, warped)
                
                result_path = f"tmp/result_{job_id}.jpg"
                cv2.imwrite(result_path, result_img)
                
                job.status = JobStatus.COMPLETED
                job.result_url = f"file:///{result_path}"
                job.progress = 1.0
                self.cache.set(job.cache_key, job.result_url)
                
        except Exception as e:
            print(f"Error processing job {job_id}: {e}")
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.progress = 0.0
        
        self.db.commit()

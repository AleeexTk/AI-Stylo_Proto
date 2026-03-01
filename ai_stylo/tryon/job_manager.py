import uuid
from sqlalchemy.orm import Session
from typing import Optional
from ai_stylo.core.models import TryOnJob
from .cache import TryOnCache
from .providers.base import TryOnProvider

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

    def enrich_job_with_avatar(self, job_id: str, avatar_profile: dict):
        """Обновление метаданных аватара перед основным рендером (Evo-DNA Sync)."""
        job = self.db.query(TryOnJob).filter(TryOnJob.id == job_id).first()
        if job:
            job.meta_data = {"avatar_profile": avatar_profile}
            job.status = JobStatus.ANALYSIS
            job.progress = 0.25
            self.db.commit()

    def process_job(self, job_id: str):
        job = self.db.query(TryOnJob).filter(TryOnJob.id == job_id).first()
        if not job or job.status == JobStatus.COMPLETED:
            return
            
        try:
            # 1. Если статус PENDING - нужен анализ (STAGE_ANALYSIS: 0.2)
            if job.status == JobStatus.PENDING:
                # В B2B здесь может быть вызов AvatarExtractor
                job.status = JobStatus.ANALYSIS
                job.progress = 0.2
                self.db.commit()

            # 2. Основная генерация (STAGE_RENDER: 0.8)
            if job.status == JobStatus.ANALYSIS:
                # Построение промпта на основе avatar_profile (если есть)
                profile = job.meta_data.get("avatar_profile", {})
                
                job.status = JobStatus.RENDERING
                job.progress = 0.5
                self.db.commit()
                
                # Вызов провайдера
                result_url = self.provider.generate(job.avatar_url, job.item_url)
                
                job.status = JobStatus.COMPLETED
                job.result_url = result_url
                job.progress = 1.0
                self.cache.set(job.cache_key, result_url)
                
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.progress = 0.0 # Error fallback
        
        self.db.commit()

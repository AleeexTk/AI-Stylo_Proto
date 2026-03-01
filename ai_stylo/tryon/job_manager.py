import uuid
from sqlalchemy.orm import Session
from typing import Optional
from ai_stylo.core.models import TryOnJob
from .cache import TryOnCache
from .providers.base import TryOnProvider

class JobStatus:
    PENDING = "pending"
    PROCESSING = "processing"
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
            job = TryOnJob(
                id=f"cached_{cache_key[:8]}_{uuid.uuid4().hex[:4]}",
                merchant_id=merchant_id,
                user_id=user_id,
                status=JobStatus.COMPLETED,
                avatar_url=avatar_url,
                item_url=item_url,
                cache_key=cache_key,
                result_url=cached_result
            )
            self.db.add(job)
            self.db.commit()
            return job
            
        job_id = str(uuid.uuid4())
        job = TryOnJob(
            id=job_id,
            merchant_id=merchant_id,
            user_id=user_id,
            status=JobStatus.PENDING,
            avatar_url=avatar_url,
            item_url=item_url,
            cache_key=cache_key
        )
        self.db.add(job)
        self.db.commit()
        return job

    def get_job_status(self, job_id: str) -> Optional[TryOnJob]:
        return self.db.query(TryOnJob).filter(TryOnJob.id == job_id).first()

    def process_job(self, job_id: str):
        job = self.get_job_status(job_id)
        if not job or job.status != JobStatus.PENDING:
            return
            
        job.status = JobStatus.PROCESSING
        self.db.commit()
        
        try:
            result_url = self.provider.generate(job.avatar_url, job.item_url)
            job.status = JobStatus.COMPLETED
            job.result_url = result_url
            self.cache.set(job.cache_key, result_url)
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
        
        self.db.commit()

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uvicorn
import os
from dotenv import load_dotenv

from ai_stylo.core.database import get_db, init_db
from ai_stylo.core.events.service import EventService
from ai_stylo.core.profile.service import ProfileService
from ai_stylo.core.skills.engine import SkillEngine
from ai_stylo.core.skills.base_skills import BASE_SKILLS
from ai_stylo.core.catalog.service import CatalogService
from ai_stylo.core.catalog.importers import GepurImporter, VovkImporter
from ai_stylo.core.outfits.generator import OutfitGenerator
from ai_stylo.core.analytics.aggregator import AnalyticsAggregator
from ai_stylo.tryon.job_manager import TryOnJobManager, JobStatus
from ai_stylo.tryon.cache import TryOnCache
from ai_stylo.tryon.providers.base import FalProvider

load_dotenv()
init_db() # Create tables if they don't exist

app = FastAPI(title="AI-Stylo API Gateway v1.0", version="1.0.0")

# Shared resources (Stateless or Global Cache)
skill_engine = SkillEngine(BASE_SKILLS)
tryon_provider = FalProvider(api_key=os.getenv("FAL_KEY", "fake"))
tryon_cache = TryOnCache()

# Pydantic Models
class EventLogged(BaseModel):
    merchant_id: str
    user_id: str
    type: str
    payload: Optional[Dict[str, Any]] = None

class CatalogImportRequest(BaseModel):
    merchant_id: str
    brand: str # gepur, vovk
    url: str

@app.get("/health")
async def health():
    return {"status": "online", "version": "1.0.0"}

@app.post("/catalog/import")
async def import_product(req: CatalogImportRequest, db: Session = Depends(get_db)):
    importers = {
        "gepur": GepurImporter("gepur"),
        "vovk": VovkImporter("vovk")
    }
    
    importer = importers.get(req.brand.lower())
    if not importer:
        raise HTTPException(status_code=400, detail="Brand importer not supported")
        
    data = await importer.import_from_url(req.url)
    if not data:
        raise HTTPException(status_code=404, detail="Failed to extract product data")
    
    catalog_service = CatalogService(db)
    product = catalog_service.upsert_product(data)
    
    return {"status": "success", "product_id": product.id, "title": product.title}

@app.post("/events")
async def log_event(event: EventLogged, db: Session = Depends(get_db)):
    event_service = EventService(db)
    profile_service = ProfileService(db)
    
    # 1. Log event
    logged = event_service.log(event.merchant_id, event.user_id, event.type, event.payload)
    
    # 2. Update profile (logic like skills)
    profile = profile_service.get_profile(event.merchant_id, event.user_id)
    
    # Explicit projection to avoid ORM state issues
    profile_data = {
        "counters": dict(profile.counters or {}),
        "skills": dict(profile.skills or {}),
        "seen_events": profile.seen_events or 0,
        "similarity_history": list(profile.meta_data.get("similarity_history", []))
    }
    
    history_data = [
        {"type": e.type, "payload": e.payload, "ts": e.ts.isoformat()} 
        for e in event_service.get_history(event.merchant_id, event.user_id)
    ]
    
    skill_engine.process_events(profile_data, history_data)
    
    # Sync back to ORM object
    profile.counters = profile_data["counters"]
    profile.skills = profile_data["skills"]
    profile.seen_events = profile_data["seen_events"]
    
    db.commit()
    return {"ok": True, "event_id": logged.id}

@app.get("/profile/{merchant_id}/{user_id}")
async def get_profile(merchant_id: str, user_id: str, db: Session = Depends(get_db)):
    profile_service = ProfileService(db)
    return profile_service.get_profile(merchant_id, user_id)

@app.post("/outfits/generate")
async def generate_outfits(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    merchant_id = data.get("merchant_id", "default")
    user_id = data.get("user_id", "anonymous")
    
    profile_service = ProfileService(db)
    event_service = EventService(db)
    catalog_service = CatalogService(db)
    profile = profile_service.get_profile(merchant_id, user_id)
    
    # Projection for scorer/generator
    profile_data = {
        "budget_min": profile.budget_min,
        "budget_max": profile.budget_max,
        "style_preset": profile.style_preset,
        "affinities": profile.meta_data.get("affinities", {}),
        "skills": profile.skills or {}
    }
    
    generator = OutfitGenerator(catalog_service.get_all())
    outfits = generator.generate(profile_data, count=3)
    
    event_service.log(merchant_id, user_id, "generate_outfits")
    db.commit()
    
    return {"user_id": user_id, "outfits": outfits}

class TryOnRequest(BaseModel):
    merchant_id: str
    user_id: str
    avatar_url: str
    item_url: str
    outfit_id: str

@app.post("/tryon/jobs")
async def create_tryon_job(req: TryOnRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    manager = TryOnJobManager(db, tryon_provider, tryon_cache)
    job = manager.create_job(req.merchant_id, req.user_id, req.avatar_url, req.item_url, req.outfit_id)
    
    if job.status == JobStatus.PENDING:
        background_tasks.add_task(manager.process_job, job.id)
    
    return job

@app.get("/tryon/jobs/{job_id}")
async def get_tryon_status(job_id: str, db: Session = Depends(get_db)):
    manager = TryOnJobManager(db, tryon_provider, tryon_cache)
    job = manager.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/merchant/analytics/summary/{merchant_id}")
async def get_analytics(merchant_id: str, db: Session = Depends(get_db)):
    event_service = EventService(db)
    aggregator = AnalyticsAggregator(event_service)
    # We pass merchant_id to aggregator later or filter history here
    history = event_service.get_history(merchant_id, limit=1000)
    # Simple summary for now
    return {
        "merchant_id": merchant_id,
        "total_events": len(history),
        "outfits": len([e for e in history if e.type == "generate_outfits"])
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

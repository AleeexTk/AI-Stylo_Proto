from typing import List, Dict, Any

class AnalyticsAggregator:
    def __init__(self, event_service: Any):
        self.events = event_service

    def get_summary(self) -> Dict[str, Any]:
        history = self.events.get_history(limit=1000)
        
        total_events = len(history)
        outfits_generated = len([e for e in history if e.type == "generate_outfits"])
        tryon_jobs = len([e for e in history if e.type == "tryon_job_create"])
        
        return {
            "total_interactions": total_events,
            "outfits_generated": outfits_generated,
            "tryon_usage": tryon_jobs,
            "conversion_rate_estimate": (tryon_jobs / outfits_generated) if outfits_generated > 0 else 0
        }

    def get_segments(self, profiles: List[dict]) -> Dict[str, int]:
        segments = {"Minimalist": 0, "Trendsetter": 0, "Classic": 0, "Newbie": 0}
        
        for p in profiles:
            likes = p.get("counters", {}).get("likes", 0)
            if likes > 10:
                segments["Trendsetter"] += 1
            elif likes > 5:
                segments["Minimalist"] += 1
            else:
                segments["Newbie"] += 1
        return segments

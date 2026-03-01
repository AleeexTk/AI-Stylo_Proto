from dataclasses import dataclass
from typing import Callable, Dict, Optional, List, Any
from datetime import datetime

def now_iso():
    return datetime.utcnow().isoformat()

@dataclass
class SkillDef:
    id: str
    title: str
    desc: str
    icon: str
    unlock_when: Callable[[dict], bool]
    progress_fn: Callable[[dict], float]
    levels: Optional[List[float]] = None

class SkillEngine:
    def __init__(self, skill_defs: Dict[str, SkillDef]):
        self.skill_defs = skill_defs

    def ensure_state(self, profile: dict):
        profile.setdefault("counters", {})
        profile.setdefault("skills", {})
        profile.setdefault("seen_events", 0)

    def process_events(self, profile: dict, events: List[dict]):
        self.ensure_state(profile)
        start = int(profile.get("seen_events", 0))
        new_events = events[start:]
        
        for e in new_events:
            self._handle_event(profile, e)
            
        profile["seen_events"] = start + len(new_events)
        self.update_skills(profile)

    def _handle_event(self, profile: dict, event: dict):
        etype = event.get("type", "")
        # Basic mapping - can be extended via config
        mapping = {
            "swipe_like": "likes",
            "swipe_dislike": "dislikes",
            "wishlist_add": "wishlist_add",
            "wishlist_remove": "wishlist_remove",
            "buy_outfit": "buy_outfit",
            "generate_outfits": "generate_outfits",
            "query": "queries",
            "deal_action": "deal_actions",
            "luxury_action": "luxury_actions"
        }
        counter_key = mapping.get(etype)
        if counter_key:
            profile["counters"][counter_key] = profile["counters"].get(counter_key, 0) + 1

    def update_skills(self, profile: dict):
        for sid, sdef in self.skill_defs.items():
            if sid not in profile["skills"]:
                if sdef.unlock_when(profile):
                    profile["skills"][sid] = {
                        "id": sid,
                        "title": sdef.title,
                        "desc": sdef.desc,
                        "icon": sdef.icon,
                        "unlocked_at": now_iso(),
                        "progress": 0.0,
                        "level": 1,
                    }

            if sid in profile["skills"]:
                progress = max(0.0, min(1.0, sdef.progress_fn(profile)))
                profile["skills"][sid]["progress"] = progress
                
                if sdef.levels:
                    lvl = 1
                    for threshold in sdef.levels:
                        if progress >= threshold:
                            lvl += 1
                    profile["skills"][sid]["level"] = lvl

    @staticmethod
    def get_visible_skills(profile: dict, min_progress: float = 0.01):
        skills = [s for s in profile.get("skills", {}).values() if s.get("progress", 0) >= min_progress]
        return sorted(skills, key=lambda x: x["progress"], reverse=True)

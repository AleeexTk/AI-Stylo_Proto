from dataclasses import dataclass
from typing import Callable, Dict, Optional, List, Any
from datetime import datetime, timezone

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@dataclass
class SkillDef:
    id: str
    title: str
    desc: str
    icon: str
    unlock_when: Callable[[dict], bool]
    progress_fn: Callable[[dict], float]
    levels: Optional[List[float]] = None

def ensure_skill_state(profile: dict):
    profile.setdefault("counters", {})
    profile.setdefault("skills", {})
    profile.setdefault("seen_events", 0)

def inc(profile: dict, key: str, by: int = 1):
    profile["counters"][key] = int(profile["counters"].get(key, 0) + by)

def process_new_events(profile: dict, events: List[dict]):
    ensure_skill_state(profile)
    start = int(profile.get("seen_events", 0))
    new = events[start:]
    if not new: return

    mapping = {
        "swipe_like": "likes",
        "swipe_dislike": "dislikes",
        "wishlist_add": "wishlist_add",
        "wishlist_remove": "wishlist_remove",
        "buy_outfit": "buy_outfit",
        "generate_outfit": "generate_outfits",
        "query": "queries",
        "deal_action": "deal_actions",
        "luxury_action": "luxury_actions"
    }

    for e in new:
        t = e.get("type", "")
        counter_key = mapping.get(t)
        if counter_key:
            inc(profile, counter_key, 1)

    profile["seen_events"] = start + len(new)

def unlock_and_update_skills(profile: dict, skill_defs: Dict[str, SkillDef]):
    ensure_skill_state(profile)
    for sid, sdef in skill_defs.items():
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
            p = float(max(0.0, min(1.0, sdef.progress_fn(profile))))
            profile["skills"][sid]["progress"] = p
            if sdef.levels:
                lvl = 1
                for th in sdef.levels:
                    if p >= th: lvl += 1
                profile["skills"][sid]["level"] = lvl

def get_visible_skills(profile: dict, min_progress: float = 0.01):
    ensure_skill_state(profile)
    res = [s for s in profile["skills"].values() if float(s.get("progress", 0.0)) >= min_progress]
    res.sort(key=lambda s: float(s.get("progress", 0.0)), reverse=True)
    return res

def get_skill_defs_for_catalog(catalog_id: str, st_partner_packs: dict) -> Dict[str, SkillDef]:
    from .base_skills import BASE_SKILLS
    defs = dict(BASE_SKILLS)
    pack = st_partner_packs.get(catalog_id, {})
    defs.update(pack)
    return defs

class SkillEngine:
    """Class wrapper for the functional interface."""
    def __init__(self, skill_defs: Dict[str, SkillDef]):
        self.skill_defs = skill_defs
    def ensure_state(self, profile: dict): ensure_skill_state(profile)
    def process_events(self, profile: dict, events: List[dict]): process_new_events(profile, events)
    def update_skills(self, profile: dict): unlock_and_update_skills(profile, self.skill_defs)
    @staticmethod
    def get_visible_skills(profile: dict, min_progress: float = 0.01): return get_visible_skills(profile, min_progress)

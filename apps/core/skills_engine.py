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
    unlock_when: Callable[[dict], bool]      # условие разблокировки
    progress_fn: Callable[[dict], float]     # прогресс 0..1 после unlock
    levels: Optional[List[float]] = None    # thresholds для lvl

def ensure_skill_state(profile: dict):
    profile.setdefault("counters", {})
    profile.setdefault("skills", {})
    profile.setdefault("seen_events", 0)

def inc(profile: dict, key: str, by: int = 1):
    profile["counters"][key] = int(profile["counters"].get(key, 0) + by)

def process_new_events(profile: dict, events: list[dict]):
    """Обрабатываем только новые события, чтобы не пересчитывать всё каждый rerun."""
    ensure_skill_state(profile)
    start = int(profile.get("seen_events", 0))
    new = events[start:]
    if not new:
        return

    for e in new:
        t = e.get("type", "")
        if t == "swipe_like":
            inc(profile, "likes", 1)
        elif t == "swipe_dislike":
            inc(profile, "dislikes", 1)
        elif t == "wishlist_add":
            inc(profile, "wishlist_add", 1)
        elif t == "wishlist_remove":
            inc(profile, "wishlist_remove", 1)
        elif t == "buy_outfit":
            inc(profile, "buy_outfit", 1)
        elif t == "generate_outfit":
            inc(profile, "generate_outfits", 1)
        elif t == "query":
            inc(profile, "queries", 1)
        # будущие события от магазинов
        elif t == "deal_action":
            inc(profile, "deal_actions", 1)
        elif t == "luxury_action":
            inc(profile, "luxury_actions", 1)

    profile["seen_events"] = start + len(new)

def unlock_and_update_skills(profile: dict, skill_defs: Dict[str, SkillDef]):
    """Никогда не создаёт locked skills в state. Только unlock -> появляется."""
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
                    if p >= th:
                        lvl += 1
                profile["skills"][sid]["level"] = lvl

def get_visible_skills(profile: dict, min_progress: float = 0.01):
    """Показываем только открытые и не нулевые."""
    ensure_skill_state(profile)
    res = []
    for sid, stt in profile["skills"].items():
        if float(stt.get("progress", 0.0)) >= min_progress:
            res.append(stt)
    res.sort(key=lambda s: float(s.get("progress", 0.0)), reverse=True)
    return res

# -------------------------
# Base skills (платформа)
# -------------------------
def taste_stability_progress(p: dict) -> float:
    # Заглушка, использующая историю подобия (если она есть)
    hist = p.get("similarity_history", [])
    if not hist:
        return 0.0
    return min(1.0, len(hist) / 10.0)

BASE_SKILLS: Dict[str, SkillDef] = {
    "taste_stability": SkillDef(
        id="taste_stability",
        title="Постоянство вкуса",
        desc="Чем выше — тем стабильнее твой стиль и точнее подбор.",
        icon="🧠",
        unlock_when=lambda p: len(p.get("similarity_history", [])) >= 5,
        progress_fn=taste_stability_progress,
        levels=[0.25, 0.50, 0.75, 0.90],
    ),
    "collector": SkillDef(
        id="collector",
        title="Коллекционер",
        desc="Ты собираешь свою базу вещей (вишлист).",
        icon="🧺",
        unlock_when=lambda p: int(p.get("counters", {}).get("wishlist_add", 0)) >= 3,
        progress_fn=lambda p: min(1.0, int(p.get("counters", {}).get("wishlist_add", 0)) / 20.0),
        levels=[0.2, 0.4, 0.6, 0.8],
    ),
    "outfit_builder": SkillDef(
        id="outfit_builder",
        title="Сборщик образов",
        desc="Ты выбираешь комплекты, а не одиночные вещи.",
        icon="🖼️",
        unlock_when=lambda p: int(p.get("counters", {}).get("buy_outfit", 0)) >= 1,
        progress_fn=lambda p: min(1.0, int(p.get("counters", {}).get("buy_outfit", 0)) / 10.0),
        levels=[0.2, 0.5, 0.8],
    ),
    "explorer": SkillDef(
        id="explorer",
        title="Исследователь",
        desc="Ты пробуешь разные запросы и сценарии.",
        icon="🧭",
        unlock_when=lambda p: int(p.get("counters", {}).get("queries", 0)) >= 5,
        progress_fn=lambda p: min(1.0, int(p.get("counters", {}).get("queries", 0)) / 40.0),
        levels=[0.25, 0.5, 0.75],
    ),
    "smart_buyer": SkillDef(
        id="smart_buyer",
        title="Фокус на Выгоде",
        desc="Покупай товары со скидкой, чтобы качать этот навык.",
        icon="💸",
        unlock_when=lambda p: int(p.get("counters", {}).get("deal_actions", 0)) >= 1,
        progress_fn=lambda p: min(1.0, int(p.get("counters", {}).get("deal_actions", 0)) / 10.0),
        levels=[0.25, 0.5, 0.8],
    ),
    "luxury_seeker": SkillDef(
        id="luxury_seeker",
        title="Премиум Ловец",
        desc="Особое чутье на эксклюзивные вещи.",
        icon="👑",
        unlock_when=lambda p: int(p.get("counters", {}).get("luxury_actions", 0)) >= 1,
        progress_fn=lambda p: min(1.0, int(p.get("counters", {}).get("luxury_actions", 0)) / 5.0),
        levels=[0.3, 0.6, 0.9],
    )
}

def get_skill_defs_for_catalog(catalog_id: str, st_partner_packs: dict) -> Dict[str, SkillDef]:
    defs = dict(BASE_SKILLS)
    pack = st_partner_packs.get(catalog_id, {})
    defs.update(pack)
    return defs

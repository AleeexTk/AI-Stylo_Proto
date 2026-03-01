from .engine import SkillDef
from typing import Dict

def taste_stability_progress(p: dict) -> float:
    hist = p.get("similarity_history", [])
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

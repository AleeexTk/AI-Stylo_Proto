import sys
from pathlib import Path
import streamlit as st
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from datetime import datetime
import hashlib
import json
import random
import os

project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from apps.core.skills_engine import (
    SkillDef,
    ensure_skill_state,
    process_new_events,
    get_skill_defs_for_catalog,
    unlock_and_update_skills,
    get_visible_skills,
)
from apps.adapters.ollama_adapter import OllamaAdapter, OllamaAdapterError
from apps.core.ai.orchestrator import PEAROrchestrator
from apps.core.tools_registry import PreferenceToolRegistry
from apps.core.contracts import AssistantResult
from apps.core.tools.registry import LocalToolRegistry


DOMAIN_OPTIONS = ["fashion", "cinema"]

USE_GOOGLE_RAG_FALLBACK = os.getenv("USE_GOOGLE_RAG_FALLBACK", "0").lower() in {"1", "true", "yes", "on"}

# CSS Loading
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

css_path = Path(__file__).parent / "style_cyber.css"
if css_path.exists():
    local_css(str(css_path))
else:
    # Fallback minimal styling
    st.markdown("""
        <style>
        .main { background-color: #0d0d12; color: #00f3ff; }
        .stButton>button { border: 1px solid #00f3ff; background: rgba(0,243,255,0.1); color: #00f3ff; }
        </style>
    """, unsafe_allow_html=True)

# Настройка страницы
st.set_page_config(page_title="🧬 AI-Stylo | Virtual Fitting", layout="wide", page_icon="🧬")
st.markdown("<h1 style='text-align: center;'>🧬 AI-STYLO: VIRTUAL FITTING</h1>", unsafe_allow_html=True)
st.caption("EvoPyramid Protocol Active. System Status: NEON_SYNCED.")

# ---------- Модель эмбеддингов ----------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ---------- Вспомогательные функции ----------
def now_iso():
    return datetime.utcnow().isoformat()

def hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]

def log_event(event_type: str, payload: dict = None):
    st.session_state.events.append({
        "ts": now_iso(),
        "type": event_type,
        "payload": payload or {},
    })

# ---------- Инициализация состояния ----------
def init_state():
    if "profile" not in st.session_state:
        st.session_state.profile = {
            "user_id": "demo_user",
            "base_vector": None,
            "try_vector": None,
            "use_try": False,
            "brand_affinities": {},
            "budget_profile": {"min": 50, "max": 600, "usual": 150},
            "update_count": 0,
            "similarity_history": [],
            "onboarding_done": False,
            "fav_color": "#4A90E2",
            "style_pref": "casual",
            # SKILLS ENGINE STATE:
            "counters": {},
            "skills": {},
            "seen_events": 0
        }
    ensure_skill_state(st.session_state.profile)

    if "slots" not in st.session_state:
        st.session_state.slots = {
            "top": None,
            "bottom": None,
            "shoes": None,
            "accessory": None,
        }
    if "wishlist" not in st.session_state:
        st.session_state.wishlist = set()
    if "events" not in st.session_state:
        st.session_state.events = []
    if "catalogs" not in st.session_state:
        st.session_state.catalogs = {}
    if "current_catalog" not in st.session_state:
        st.session_state.current_catalog = None
    if "slot_selection" not in st.session_state:
        st.session_state.slot_selection = None
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 0 if not st.session_state.profile["onboarding_done"] else -1
    if "partner_skill_packs" not in st.session_state:
        st.session_state.partner_skill_packs = {}
    if "assistant_result" not in st.session_state:
        st.session_state.assistant_result = None
    if "assistant_domain" not in st.session_state:
        st.session_state.assistant_domain = "fashion"

init_state()
profile = st.session_state.profile

@st.cache_resource
def get_ollama_adapter() -> OllamaAdapter:
    return OllamaAdapter()


class _SessionToolRegistry(PreferenceToolRegistry):
    def __init__(self, profile_store: dict):
        super().__init__(preference_store=profile_store, default_domain="fashion")
        self.domain_options = tuple(DOMAIN_OPTIONS)

    def execute(self, tool_name: str, arguments: dict) -> dict:
        if "domain" not in arguments:
            arguments = dict(arguments)
            arguments["domain"] = st.session_state.get("assistant_domain", "fashion")

        result = super().execute(tool_name=tool_name, arguments=arguments)
        if result.get("ok"):
            saved = result.get("saved", {})
            key = next(iter(saved.keys()), "")
            value = saved.get(key)
            log_event("save_preference", {"domain": result.get("domain"), "key": key, "value": value})
        return result


@st.cache_resource
def get_orchestrator() -> PEAROrchestrator:
    return PEAROrchestrator(ollama_adapter=get_ollama_adapter(), tool_registry=_SessionToolRegistry(st.session_state.profile))


def run_ollama_healthcheck() -> tuple[bool, str]:
    try:
        status = get_ollama_adapter().health()
        return True, (
            f"✅ Ollama online ({status['models']['chat']} / {status['models']['embed']})"
        )
    except OllamaAdapterError as exc:
        return False, f"⚠️ Ollama недоступний: {exc}"


ollama_available, ollama_status_message = run_ollama_healthcheck()
st.caption(ollama_status_message)
if not ollama_available:
    st.warning("Локальний AI недоступний. Перевірте OLLAMA_BASE_URL і моделі.")

# ---------- Микро-опрос ----------
if not profile["onboarding_done"]:
    with st.container():
        st.markdown("## 🎮 Налаштуй свій стиль за 30 секунд")
        step = st.session_state.onboarding_step

        if step == 0:
            st.markdown("### 1. Твій улюблений колір")
            cols = st.columns(5)
            colors = {
                "Синій": "#4A90E2", "Зелений": "#50B883",
                "Чорний": "#2C3E50", "Білий": "#ECF0F1", "Рожевий": "#E84393"
            }
            for i, (name, code) in enumerate(colors.items()):
                with cols[i]:
                    if st.button(name, key=f"color_{name}"):
                        profile["fav_color"] = code
                        st.session_state.onboarding_step = 1
                        st.rerun()

        elif step == 1:
            st.markdown("### 2. Який стиль тобі ближче?")
            styles = ["Casual", "Street", "Minimal", "Classic", "Sport"]
            cols = st.columns(len(styles))
            for i, style in enumerate(styles):
                with cols[i]:
                    if st.button(style, key=f"style_{style}"):
                        profile["style_pref"] = style.lower()
                        st.session_state.onboarding_step = 2
                        st.rerun()

        elif step == 2:
            st.markdown("### 3. Твій бюджет на образ (грн)")
            budget = st.slider("", 0, 10000, (500, 3000), step=100)
            if st.button("Далі"):
                profile["budget_profile"]["min"] = budget[0]
                profile["budget_profile"]["max"] = budget[1]
                profile["budget_profile"]["usual"] = (budget[0] + budget[1]) // 2
                st.session_state.onboarding_step = 3
                st.rerun()

        elif step == 3:
            st.markdown("### 4. Твій розмір (необов'язково)")
            size = st.selectbox("Оберіть розмір", ["XS", "S", "M", "L", "XL", "Пропустити"])
            if st.button("Завершити"):
                if size != "Пропустити":
                    profile["size"] = size
                profile["onboarding_done"] = True
                st.session_state.onboarding_step = -1
                log_event("onboarding_complete", profile)
                st.rerun()
    st.stop()

# Заголовок с персонализированным цветом
st.markdown(f"<style> .stButton>button {{ background-color: {profile['fav_color']}; color: white; border: none; }} </style>", unsafe_allow_html=True)

# ---------- Боковая панель ----------
with st.sidebar:
    st.header("🗂️ Каталог")
    if not st.session_state.catalogs:
        # Демо-товары с "old_price" и "luxury" метками для витринных навыков
        demo_items = [
            {"id": "1", "name": "Оверсайз худи", "brand": "Balenciaga", "price": 4500, "old_price": 6000, "luxury_index": 0.9, "category": "top", "description": "Чорний оверсайз худи", "image": "https://picsum.photos/id/1015/400/500"},
            {"id": "2", "name": "Slim джинси", "brand": "Levi's", "price": 2700, "old_price": 2700, "luxury_index": 0.3, "category": "bottom", "description": "Класичні сині джинси slim", "image": "https://picsum.photos/id/133/400/500"},
            {"id": "3", "name": "Білі кросівки", "brand": "Nike", "price": 3200, "old_price": 4000, "luxury_index": 0.5, "category": "shoes", "description": "Мінімалістичні білі кросівки", "image": "https://picsum.photos/id/201/400/500"},
            {"id": "4", "name": "Шкіряна куртка", "brand": "Zara", "price": 5200, "old_price": 5200, "luxury_index": 0.4, "category": "top", "description": "Коричнева шкіряна куртка", "image": "https://picsum.photos/id/251/400/500"},
            {"id": "5", "name": "Кашеміровий светр", "brand": "COS", "price": 3900, "old_price": 5000, "luxury_index": 0.7, "category": "top", "description": "Сірий м'який светр", "image": "https://picsum.photos/id/669/400/500"},
            {"id": "6", "name": "Сумка Birkin", "brand": "Hermes", "price": 9500, "old_price": 9500, "luxury_index": 1.0, "category": "accessory", "description": "Ексклюзивна сумка", "image": "https://picsum.photos/id/660/400/500"}
        ]
        st.session_state.catalogs["demo"] = {
            "items": demo_items,
            "emb": {it["id"]: model.encode(it["description"]) for it in demo_items},
            "meta": {"source": "built-in", "count": len(demo_items)}
        }
        st.session_state.current_catalog = "demo"

    catalog_ids = list(st.session_state.catalogs.keys())
    selected_catalog = st.selectbox("Активний каталог", catalog_ids, index=catalog_ids.index(st.session_state.current_catalog) if st.session_state.current_catalog in catalog_ids else 0)
    st.session_state.current_catalog = selected_catalog
    cat = st.session_state.catalogs[selected_catalog]
    items = cat["items"]
    item_emb = cat["emb"]

    if st.button("♻️ Скинути профіль"):
        for key in ["profile", "slots", "wishlist", "events", "partner_skill_packs"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    # --------- Partner Skill Pack Injector ---------
    with st.expander("🏷️ Partner Skill Pack (JSON)", expanded=False):
        st.caption("Загрузи JSON-пак навыков для каталога. Появятся только когда откроются.")
        pack_file = st.file_uploader("Загрузить skill_pack.json", type=["json"], key="skill_pack_uploader")

        if pack_file is not None:
            raw = pack_file.read()
            data = json.loads(raw.decode("utf-8"))
            target_catalog = data.get("catalog_id", st.session_state.current_catalog)
            skills_list = data.get("skills", [])
            parsed_pack = {}

            for s in skills_list:
                sid, title, desc, icon = str(s["id"]), str(s["title"]), str(s.get("desc", "")), str(s.get("icon", "✨"))
                unlock = s.get("unlock", {"type": "counter_gte", "key": "wishlist_add", "value": 5})
                prog = s.get("progress", {"type": "counter_ratio", "key": "wishlist_add", "max": 25})
                levels = s.get("levels", [0.25, 0.5, 0.75])

                def make_unlock_fn(rule: dict):
                    rtype = rule.get("type")
                    if rtype == "counter_gte":
                        key, val = rule.get("key"), int(rule.get("value", 1))
                        return lambda p, k=key, v=val: int(p.get("counters", {}).get(k, 0)) >= v
                    return lambda p: False

                def make_progress_fn(rule: dict):
                    rtype = rule.get("type")
                    if rtype == "counter_ratio":
                        key, mx = rule.get("key"), float(rule.get("max", 20))
                        return lambda p, k=key, m=mx: min(1.0, float(p.get("counters", {}).get(k, 0)) / m)
                    return lambda p: 0.0

                parsed_pack[sid] = SkillDef(id=sid, title=title, desc=desc, icon=icon,
                                            unlock_when=make_unlock_fn(unlock),
                                            progress_fn=make_progress_fn(prog),
                                            levels=levels)

            st.session_state.partner_skill_packs[target_catalog] = parsed_pack
            log_event("partner_skill_pack_loaded", {"catalog_id": target_catalog, "count": len(parsed_pack)})
            st.success(f"Skill pack загружен для '{target_catalog}'!")
            st.rerun()

# --------- Движок навыков и пересчет ---------
process_new_events(profile, st.session_state.events)
skill_defs = get_skill_defs_for_catalog(selected_catalog, st.session_state.partner_skill_packs)
unlock_and_update_skills(profile, skill_defs)

# ---------- Основная область ----------
left_col, right_col = st.columns([1, 1], gap="medium")

with left_col:
    st.subheader("🖼️ Твій образ")
    avatar_placeholder = st.empty()
    with avatar_placeholder.container():
        st.image("https://via.placeholder.com/400x500?text=Your+Look+(RPG+Inventory)", use_container_width=True)
    
    col_s1, col_s2 = st.columns(2)
    def render_slot(slot_key, label):
        st.markdown(f"**{label}**")
        btn = st.button("➕" if st.session_state.slots[slot_key] is None else "🔄", key=f"slot_{slot_key}")
        if st.session_state.slots[slot_key]:
            itm = next((it for it in items if it["id"] == st.session_state.slots[slot_key]), None)
            if itm:
                st.image(itm["image"], width=100)
                st.caption(f"{itm['name']}\n{itm['price']} грн")
        else:
            st.caption("порожньо")
        return btn

    with col_s1:
        t_btn = render_slot("top", "Верх")
        b_btn = render_slot("bottom", "Низ")
    with col_s2:
        s_btn = render_slot("shoes", "Взуття")
        a_btn = render_slot("accessory", "Аксесуар")

    if t_btn: st.session_state.slot_selection = "top"
    if b_btn: st.session_state.slot_selection = "bottom"
    if s_btn: st.session_state.slot_selection = "shoes"
    if a_btn: st.session_state.slot_selection = "accessory"

with right_col:
    # ---------------- Вкладки (Control / DNA) ----------------
    tab_ctrl, tab_rag, tab_dna = st.tabs(["⚙️ Panel", "🤖 AI RAG (GDocs)", "🧬 Style DNA & Skills"])

    with tab_ctrl:
        st.markdown("**💰 Бюджет**")
        min_b, max_b = profile["budget_profile"]["min"], profile["budget_profile"]["max"]
        budget_range = st.slider("Діапазон цін (грн)", 0, 10000, (min_b, max_b), step=100)
        profile["budget_profile"]["min"], profile["budget_profile"]["max"] = budget_range

        st.markdown("**🎯 Стиль**")
        style_options = ["Casual", "Street", "Minimal", "Classic", "Sport"]
        cur_style = profile["style_pref"].capitalize()
        if cur_style not in style_options: cur_style = "Casual"
        selected_style = st.radio("Стиль", style_options, index=style_options.index(cur_style), horizontal=True, label_visibility="collapsed")
        profile["style_pref"] = selected_style.lower()

        if st.button("🎲 Згенерувати образ", use_container_width=True):
            log_event("generate_outfits", {"budget": budget_range, "style": selected_style})
            candidates = [it for it in items if budget_range[0] <= it["price"] <= budget_range[1]]
            tops = [it for it in candidates if it.get("category") == "top"]
            bottoms = [it for it in candidates if it.get("category") == "bottom"]
            shoes = [it for it in candidates if it.get("category") == "shoes"]
            accs = [it for it in candidates if it.get("category") == "accessory"]

            if tops: st.session_state.slots["top"] = random.choice(tops)["id"]
            if bottoms: st.session_state.slots["bottom"] = random.choice(bottoms)["id"]
            if shoes: st.session_state.slots["shoes"] = random.choice(shoes)["id"]
            if accs: st.session_state.slots["accessory"] = random.choice(accs)["id"]
            st.rerun()

        # Покупка
        total_price = 0
        discount_amount = 0
        luxury_score = 0
        filled_slots = []
        for slot_name, item_id in st.session_state.slots.items():
            if item_id:
                itm = next((it for it in items if it["id"] == item_id), None)
                if itm:
                    total_price += itm["price"]
                    if "old_price" in itm and itm["old_price"] > itm["price"]:
                        discount_amount += (itm["old_price"] - itm["price"])
                    luxury_score += itm.get("luxury_index", 0.0)
                    filled_slots.append(itm["name"])
        
        if filled_slots:
            st.markdown(f"**🛒 Разом: {total_price} грн**")
            if discount_amount > 0:
                st.success(f"💸 Ви економите: {discount_amount} грн!")
            if st.button("Купити образ", use_container_width=True):
                st.success("Образ додано до кошика!")
                log_event("buy_outfit", {"items": filled_slots, "total": total_price})
                # Триггеры для "витринных" скиллов:
                if discount_amount > 0: log_event("deal_action")
                if luxury_score > 1.0: log_event("luxury_action")
        else:
            st.info("Оберіть речі або згенеруйте образ")

    with tab_rag:
        st.subheader("💡 AI Assistant Studio")
        st.caption("Працює через PEAR Orchestrator. Доступний tool trigger: save_preference.")
        st.caption(f"Health: {ollama_status_message}")

        st.session_state.assistant_domain = st.radio(
            "Домен",
            DOMAIN_OPTIONS,
            index=DOMAIN_OPTIONS.index(st.session_state.assistant_domain) if st.session_state.assistant_domain in DOMAIN_OPTIONS else 0,
            horizontal=True,
        )
        prompt_placeholder = "Наприклад: підбери образ для офісу" if st.session_state.assistant_domain == "fashion" else "Наприклад: порадь фільм на вечір"
        user_msg = st.text_input("Поле запиту", placeholder=prompt_placeholder)

        pref_col1, pref_col2, pref_col3 = st.columns([1.1, 1.1, 0.8])
        with pref_col1:
            pref_key = st.text_input("Preference key", value="tone")
        with pref_col2:
            pref_value = st.text_input("Preference value", value="concise")
        with pref_col3:
            save_pref_clicked = st.button("💾 Зберегти preference", use_container_width=True)

        if save_pref_clicked:
            tool_result = get_orchestrator().tool_registry.execute(
                "save_preference",
                {
                    "domain": st.session_state.assistant_domain,
                    "key": pref_key,
                    "value": pref_value,
                },
            )
            st.session_state.assistant_result = AssistantResult(
                final_text="Preference saved via explicit save_preference trigger.",
                tool_outputs=[],
                metadata={"manual_tool_trigger": "save_preference", "tool_result": tool_result},
            )
            if tool_result.get("ok"):
                st.success("Preference збережено")
            else:
                st.error(f"Не вдалося зберегти preference: {tool_result.get('error', 'unknown error')}")

        if st.button("Запитати AI", use_container_width=True):
            if user_msg.strip():
                if not ollama_available:
                    st.warning("Ollama недоступний. Перевірте локальний сервіс.")
                else:
                    try:
                        with st.spinner("Звертаємось до Orchestrator..."):
                            assistant_result: AssistantResult = get_orchestrator().handle(
                                user_id=profile["user_id"],
                                user_message=user_msg,
                                forced_domain=st.session_state.assistant_domain,
                            )
                        st.session_state.assistant_result = assistant_result
                        log_event(
                            "rag_query_generate",
                            {
                                "text": user_msg,
                                "provider": "ollama",
                                "domain": st.session_state.assistant_domain,
                                "tool_calls": len(assistant_result.tool_outputs),
                                "orchestrator_step": assistant_result.metadata.get("step", ""),
                            },
                        )
                    except OllamaAdapterError as exc:
                        st.error(f"Ollama помилка: {exc}")

        assistant_result = st.session_state.assistant_result
        if assistant_result:
            st.markdown("### Відповідь асистента")
            st.success(assistant_result.final_text.strip() or "(порожня відповідь)")

            st.markdown("### Tool calls")
            if assistant_result.tool_outputs:
                tool_payload = [
                    {
                        "tool": out.tool_name,
                        "arguments": out.arguments,
                        "result": out.result,
                        "call_id": out.call_id,
                    }
                    for out in assistant_result.tool_outputs
                ]
                st.json(tool_payload)
            elif assistant_result.metadata.get("manual_tool_trigger"):
                st.json([
                    {
                        "tool": assistant_result.metadata["manual_tool_trigger"],
                        "result": assistant_result.metadata.get("tool_result", {}),
                    }
                ])
            else:
                st.info("Tool-и не викликались.")

            with st.expander("Повний JSON результат Orchestrator", expanded=False):
                st.json(
                    {
                        "final_text": assistant_result.final_text,
                        "tool_outputs": assistant_result.tool_results,
                        "notes": assistant_result.notes,
                        "metadata": assistant_result.metadata,
                    }
                )

    with tab_dna:
        st.subheader("🧬 Твоє Style DNA")
        st.write("Тут будет график или статика из эмбеддингов")

        st.divider()
        st.subheader("🎮 Навыки (твій індивідуальний стек)")
        visible = get_visible_skills(profile, min_progress=0.01)

        if not visible:
            st.info("Навик відкриються автоматично. Продовжуй збирати образи та купувати.")
        else:
            cols = st.columns(2)
            for i, sk in enumerate(visible):
                with cols[i % 2]:
                    st.markdown(f"{sk['icon']} **{sk['title']}** · lvl {sk.get('level',1)}")
                    st.progress(float(sk.get("progress", 0.0)))
                    st.caption(sk.get("desc",""))

# ---------- Карусель выбора предмета ----------
if st.session_state.slot_selection is not None:
    slot = st.session_state.slot_selection
    st.markdown(f"## Оберіть {slot}")

    cat_map = {"top": "top", "bottom": "bottom", "shoes": "shoes", "accessory": "accessory"}
    cat_match = cat_map.get(slot, slot)
    cands = [it for it in items if it.get("category") == cat_match and budget_range[0] <= it["price"] <= budget_range[1]]

    if not cands:
        st.warning("Немає товарів у цій категорії в межах бюджету")
        if st.button("Назад"):
            st.session_state.slot_selection = None
            st.rerun()
    else:
        cols = st.columns(3)
        for idx, item in enumerate(cands[:9]):
            with cols[idx % 3]:
                st.image(item["image"], width=150)
                price_str = f"{item['price']} грн"
                if "old_price" in item and item["old_price"] > item["price"]:
                    price_str = f"~~{item['old_price']}~~ {price_str} 🔥"
                st.markdown(f"**{item['name']}**\n\n{price_str}")
                if st.button("Обрати", key=f"sel_{item['id']}"):
                    st.session_state.slots[slot] = item["id"]
                    st.session_state.slot_selection = None
                    log_event("wishlist_add", {"item_id": item["id"]})  # трактуем выбор как wishlist
                    st.rerun()
        if st.button("Скасувати"):
            st.session_state.slot_selection = None
            st.rerun()
    st.stop()

# ---------- Логи ----------
with st.expander("📎 Останні події"):
    if st.session_state.events:
        df = pd.DataFrame(st.session_state.events[-10:])
        st.dataframe(df, use_container_width=True, hide_index=True)

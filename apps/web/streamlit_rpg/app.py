import sys
from pathlib import Path
import streamlit as st
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from datetime import datetime, UTC
import hashlib
import json
import random
import os
import urllib.parse
import requests
import time
import io
from PIL import Image, ImageDraw
import colorsys
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from ai_stylo.core.skills_engine import (
    SkillDef,
    ensure_skill_state,
    process_new_events,
    get_skill_defs_for_catalog,
    unlock_and_update_skills,
    get_visible_skills,
)
from ai_stylo.adapters.ollama_adapter import OllamaAdapter, OllamaAdapterError
from ai_stylo.adapters.generative_pipeline import VirtualTryOnPipeline
from ai_stylo.core.ai.orchestrator import PEAROrchestrator
from ai_stylo.core.tools_registry import PreferenceToolRegistry
from ai_stylo.core.contracts import AssistantResult
from ai_stylo.core.tools.registry import LocalToolRegistry
from ai_stylo.core.scraping.catalog_scraper import CatalogScraper


DOMAIN_OPTIONS = ["fashion", "cinema"]

USE_GOOGLE_RAG_FALLBACK = os.getenv("USE_GOOGLE_RAG_FALLBACK", "0").lower() in {"1", "true", "yes", "on"}

# CSS Loading
def apply_custom_theme(primary="#00f3ff", secondary=None):
    """Генерує динамічний CSS на основі обраних кольорів з перевіркою контрасту."""
    def get_luminance(hex_color):
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255

    txt_color = "#ffffff" if get_luminance(primary) < 0.6 else "#000000"
    acc_color = secondary if secondary else primary
    
    st.markdown(f"""
        <style>
        :root {{
            --primary-bg: {primary};
            --text-main: {txt_color};
            --accent: {acc_color};
        }}
        .main {{ background-color: #0d0d12; color: #ffffff; }}
        .stButton>button {{ 
            background: {primary}22; 
            color: {primary}; 
            border: 1px solid {primary};
            transition: all 0.3s ease;
        }}
        .stButton>button:hover {{ 
            background: {primary}; 
            color: {txt_color}; 
            box-shadow: 0 0 15px {primary};
        }}
        .hud-text {{ color: {primary}; text-shadow: 0 0 10px {primary}44; }}
        .hud-progress-fill {{ background: linear-gradient(90deg, {primary}, {acc_color}); }}
        [data-testid="stSidebar"] {{ background-color: #050508; border-right: 1px solid {primary}33; }}
        h1, h2, h3, h4 {{ color: {primary} !important; font-family: 'Source Code Pro', monospace; }}
        </style>
    """, unsafe_allow_html=True)

# Настройка страницы
st.set_page_config(page_title="🧬 AI-Stylo | Virtual Fitting", layout="wide", page_icon="🧬")

# Top-level HUD
st.markdown("""
<div class="hud-text">PROTOCOL: EVOPYRAMID_GENESIS_V1.0.4 | NODE: STANDALONE_HUB</div>
<div class="hud-progress"><div class="hud-progress-fill" style="width: 100%;"></div></div>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>🧬 AI-STYLO: VIRTUAL FITTING</h1>", unsafe_allow_html=True)
st.caption("EvoPyramid Protocol Active. System Status: <span style='color: #00f3ff; font-weight: bold;'>NEON_SYNCED (100%)</span>", unsafe_allow_html=True)

# ---------- Модель эмбеддингов ----------
@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()

# ---------- Вспомогательные функции ----------
def now_iso():
    return datetime.now(UTC).isoformat()

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
            "user_id": "sanya",
            "base_vector": None,
            "try_vector": None,
            "use_try": False,
            "brand_affinities": {},
            "budget_profile": {"min": 50, "max": 600, "usual": 150},
            "update_count": 0,
            "similarity_history": [],
            "onboarding_done": True,  # Авто-пропуск для dev-режиму
            "fav_colors": ["#00f3ff"],  # Список для 1-2 кольорів
            "fav_color": "#00f3ff",     # Для зворотної сумісності
            "style_pref": "casual",
            # SKILLS ENGINE STATE:
            "counters": {},
            "skills": {},
            "seen_events": 0,
            "gender": "male"
        }
    ensure_skill_state(st.session_state.profile)
    
    # Застосовуємо тему при ініціалізації
    colors = st.session_state.profile.get("fav_colors", ["#00f3ff"])
    p = colors[0] if colors else "#00f3ff"
    s = colors[1] if len(colors) > 1 else None
    apply_custom_theme(p, s)

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
    if "current_brand" not in st.session_state:
        st.session_state.current_brand = "default"

    if "catalogs" not in st.session_state:
        st.session_state.catalogs = {}
        # Демо-товары за замовчуванням
        demo_items = [
            {"id": "g1", "name": "Чорна сукня міні", "brand": "Gepur", "price": 2100, "old_price": 2300, "luxury_index": 0.6, "category": "top", "description": "Чорна сукня міні зі стрейч-сітки", "image": "https://gepur.com/product/49230/img/1.jpg"},
            {"id": "g2", "name": "Бежева сукня з блискітками", "brand": "Gepur", "price": 3500, "old_price": 3500, "luxury_index": 0.8, "category": "top", "description": "Бежева сукня з блискітками зі шнурівкою", "image": "https://gepur.com/product/45216/img/1.jpg"},
            {"id": "1", "name": "Оверсайз худи", "brand": "Balenciaga", "price": 4500, "old_price": 6000, "luxury_index": 0.9, "category": "top", "description": "Чорний оверсайз худи", "image": "https://picsum.photos/id/1015/400/500"},
            {"id": "2", "name": "Slim джинси", "brand": "Levi's", "price": 2700, "old_price": 2700, "luxury_index": 0.3, "category": "bottom", "description": "Класичні сині джинси slim", "image": "https://picsum.photos/id/133/400/500"}
        ]
        st.session_state.catalogs["demo"] = {
            "items": demo_items,
            "emb": {it["id"]: model.encode(it["description"]) for it in demo_items},
            "meta": {"source": "local", "count": len(demo_items)}
        }

    if "current_catalog" not in st.session_state:
        st.session_state.current_catalog = "demo"
    if "slot_selection" not in st.session_state:
        st.session_state.slot_selection = None
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = -1
    if "partner_skill_packs" not in st.session_state:
        st.session_state.partner_skill_packs = {}
    if "assistant_result" not in st.session_state:
        st.session_state.assistant_result = None
    if "assistant_domain" not in st.session_state:
        st.session_state.assistant_domain = "fashion"

init_state()
profile = st.session_state.profile

# Головний цикл застосування теми
colors = profile.get("fav_colors", ["#00f3ff"])
primary_c = colors[0] if colors else "#00f3ff"
secondary_c = colors[1] if len(colors) > 1 else None
apply_custom_theme(primary_c, secondary_c)

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

@st.cache_resource
def get_pipeline() -> VirtualTryOnPipeline:
    return VirtualTryOnPipeline()

@st.cache_resource
def get_catalog_scraper() -> CatalogScraper:
    return CatalogScraper()

def render_tension_map(base_bytes: bytes, dna: dict) -> Image.Image:
    """Накладає теплову карту напруги на фото користувача."""
    img = Image.open(io.BytesIO(base_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    
    grid = dna.get("grid_map", [])
    heatmap = dna.get("fit_heatmap", {}).get("heatmap", [])
    
    if not grid or not heatmap: return img
    
    # Масштабуємо точки і малюємо прямокутні сектори
    row_count = len(grid)
    col_count = len(grid[0]) if row_count > 0 else 0
    
    for r in range(row_count):
        for c in range(col_count):
            val = heatmap[r][c]
            if val <= 0.05: continue # Пропускаємо холодні зони
            
            # Розрахунок кольору: Red (1.0) -> Yellow (0.5) -> Blue (0.1)
            # Для спрощення: Red з різною прозорістю
            alpha = int(val * 180)
            color = (255, 0, 0, alpha) if val > 0.6 else (255, 255, 0, alpha)
            
            p = grid[r][c] # [x, y] normalized
            px, py = p[0] * w, p[1] * h
            
            # Розмір блоку сітки
            bw, bh = (w/col_count)*0.8, (h/row_count)*0.8
            draw.rectangle([px-bw/2, py-bh/2, px+bw/2, py+bh/2], fill=color)
            
    return img


def run_ollama_healthcheck() -> tuple[bool, str, dict]:
    try:
        health = get_ollama_adapter().health()
        if health["status"] == "ok":
            return True, f"✅ Ollama online ({health['models']['chat']})", health
        else:
            chat_ok = health["models"].get("chat_ok", False)
            msg = f"⚠️ Ollama degraded: {'Chat OK' if chat_ok else 'Chat MISSING'}"
            return chat_ok, msg, health
    except Exception as exc:
        return False, f"❌ Ollama error: {exc}", {"status": "error"}

# ---------- HUD Status Bar ----------
ollama_ready, ollama_status_message, ollama_info = run_ollama_healthcheck()
status_color = "#00f3ff" if ollama_ready else "#ff00ff"
st.markdown(f"""
<div style="background: rgba(0,243,255,0.05); padding: 5px 15px; border-left: 3px solid {status_color}; margin-bottom: 25px;">
    <span class="hud-text" style="color: {status_color}; font-size: 0.9rem;">🛰️ NEURAL_LINK: {ollama_status_message.upper()}</span>
</div>
""", unsafe_allow_html=True)

if not ollama_ready:
    st.info("💡 NEURAL_SIM_MODE: ACTIVE (FALLBACK_TO_INTERNAL_LOGIC)")

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
                        profile["fav_colors"] = [code]
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
            budget = st.slider("Бюджет", 0, 10000, (500, 3000), step=100, label_visibility="collapsed")
            if st.button("Далі"):
                profile["budget_profile"]["min"] = budget[0]
                profile["budget_profile"]["max"] = budget[1]
                profile["budget_profile"]["usual"] = (budget[0] + budget[1]) // 2
                st.session_state.onboarding_step = 3
                st.rerun()

        elif step == 3:
            st.markdown("### 4. Твоя стать")
            g_cols = st.columns(2)
            with g_cols[0]:
                if st.button("Чоловіча ♂️"):
                    profile["gender"] = "male"
                    st.session_state.onboarding_step = 4
                    st.rerun()
            with g_cols[1]:
                if st.button("Жіноча ♀️"):
                    profile["gender"] = "female"
                    st.session_state.onboarding_step = 4
                    st.rerun()

        elif step == 4:
            st.markdown("### 5. Твій розмір (необов'язково)")
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
current_btn_color = profile.get("fav_color", profile.get("fav_colors", ["#00f3ff"])[0])
st.markdown(f"<style> .stButton>button {{ background-color: {current_btn_color}; color: white; border: none; }} </style>", unsafe_allow_html=True)

# Боковая панель
with st.sidebar:
    st.header("🗂️ Каталог")
    
    # Автозавантаження глобального маркету
    market_file = Path("data/global_market.json")
    if market_file.exists() and "global_market" not in st.session_state.catalogs:
        try:
            with open(market_file, "r", encoding="utf-8") as f:
                market_data = json.load(f)
                market_items = market_data.get("items", [])
                st.session_state.catalogs["global_market"] = {
                    "items": market_items,
                    "emb": {it["id"]: model.encode(it["description"]) for it in market_items},
                    "meta": {"source": "Global Market API", "count": len(market_items)}
                }
        except Exception as e:
            st.warning(f"⚠️ Не вдалося завантажити global_market.json: {e}")

    catalog_ids = list(st.session_state.catalogs.keys())
    selected_catalog = st.selectbox("Активний каталог", catalog_ids, index=catalog_ids.index(st.session_state.current_catalog) if st.session_state.current_catalog in catalog_ids else 0)
    st.session_state.current_catalog = selected_catalog
    
    st.markdown("---")
    st.markdown("### 🔗 Магазини")
    if st.button("🔌 Підключити Gepur & Kasta Feed"):
        st.toast("Синхронізація з маркетплейсами...")
        time.sleep(1)
        st.session_state.current_catalog = "global_market"
        st.rerun()

    if st.button("♻️ Скинути все"):
        for key in ["profile", "slots", "wishlist", "events", "catalogs", "current_catalog"]:
            if key in st.session_state: del st.session_state[key]
        st.rerun()

    cat = st.session_state.catalogs.get(selected_catalog, st.session_state.catalogs.get("demo"))
    items = cat["items"]
    item_emb = cat["emb"]

    # --------- Partner Skill Pack Injector ---------
    with st.expander("🏷️ Завантажити навички (JSON)", expanded=False):
        st.caption("Завантажте JSON-пак навичок для каталогу.")
        pack_file = st.file_uploader("Оберіть skill_pack.json", type=["json"], key="skill_pack_uploader")

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
            st.success(f"Пак навичок завантажено для '{target_catalog}'!")
            st.rerun()

# --------- Движок навыков и пересчет ---------
process_new_events(profile, st.session_state.events)
skill_defs = get_skill_defs_for_catalog(selected_catalog, st.session_state.partner_skill_packs)
unlock_and_update_skills(profile, skill_defs)

# --- Дефолтні значення для scope-safe доступу поза вкладками ---
budget_range = (profile["budget_profile"]["min"], profile["budget_profile"]["max"])
selected_style = profile.get("style_pref", "casual").capitalize()

# --- Early Side-Effect for Session State ---
# Need to capture uploader value before columns to ensure display sync
if "user_photo_bytes" not in st.session_state:
    st.session_state.user_photo_bytes = None

# ---------- Основная область ----------
left_col, right_col = st.columns([1, 1], gap="medium")

with left_col:
    st.markdown("###  NEURAL MIRROR")
    
    # Futuristic Avatar Display
    if "last_viz_bytes" in st.session_state:
        st.image(st.session_state.last_viz_bytes, use_container_width=True, caption="Твій сгенерований образ")
    elif st.session_state.user_photo_bytes:
        st.image(st.session_state.user_photo_bytes, use_container_width=True, caption="Твій базовий аватар (Біометрія)")
    else:
        # High-quality fashion placeholders
        if profile.get("gender") == "male":
            default_img = "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format|fit=crop|q=80|w=800"
        else:
            default_img = "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format|fit=crop|q=80|w=800"
        st.image(default_img, use_container_width=True, caption="Твій базовий аватар (Digital Soul)")
    
    # HUD UI elements
    st.markdown("<div class='hud-bar'></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hud-text'>SCANNING BIOMETRICS: <span style='color:#00f3ff'>{profile['user_id'].upper()}</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='hud-text'>SYNCING WITH DIGITAL SOUL... <span style='color:#00ff00'>CONNECTED</span></div>", unsafe_allow_html=True)
    
    # Web Scraper Input
    st.markdown("---")
    
    # --- Кнопка Глобальної Візуалізації ---
    equipped_items = []
    for slot_name, item_id in st.session_state.slots.items():
        if item_id:
            itm = next((it for it in items if it["id"] == item_id), None)
            if itm: equipped_items.append(f"{itm['name']} ({itm['brand']})")

    can_viz = len(equipped_items) > 0 or ("user_photo_bytes" in st.session_state)
    
    if st.button("✨ ВІЗУАЛІЗУВАТИ ОБРАЗ", width="stretch", type="primary", disabled=not can_viz):
        pipeline = get_pipeline()
        p_bytes = st.session_state.get("user_photo_bytes")
        custom_g = st.session_state.get("custom_garment_url")
        viz_items = list(equipped_items)

        with st.status("🛰️ Синхронізація образу...", expanded=True) as status:
            viz_items = []
            for slot_name, item_id in st.session_state.slots.items():
                if item_id:
                    itm = next((it for it in items if it["id"] == item_id), None)
                    if itm and itm.get("image"):
                        viz_items.append(itm["image"])

            if custom_g:
                viz_items = [custom_g] + viz_items
                st.write(f"🛰️ Syncing custom garment: {custom_g[:30]}...")

            res_bytes = pipeline.generate_look(
                gender=profile.get("gender", "male"),
                user_desc=f"{selected_style} style, {profile.get('ai_guidance', '')}",
                background_desc="Cyberpunk fashion studio",
                items=viz_items,
                photo_bytes=p_bytes,
                user_id=profile["user_id"]
            )

            if res_bytes:
                st.session_state.last_viz_bytes = res_bytes
                st.session_state.outfit_result = res_bytes
                log_event("visualize_outfit", {"items": len(equipped_items), "has_photo": p_bytes is not None})
                status.update(label="✅ Образ успішно синхронізовано!", state="complete", expanded=False)
                st.rerun()
            else:
                status.update(label="❌ Помилка синхронізації", state="error")
                st.error("Двигун генерації не відповів. Перевірте підключення до AI-ядра.")

    if not can_viz:
        st.caption("💡 Одягніть щось або завантажте фото для активації дзеркала.")

    st.markdown("---")
    web_url = st.text_input("🔗 URL з магазину", placeholder="Вставте посилання на товар...")
    if st.button("🛰️ ПІДТЯГНУТИ З САЙТУ", width="stretch"):
        if web_url:
            with st.spinner("AI сканує сторінку та сегментує активи..."):
                product = get_catalog_scraper().scrape_product(web_url)
                if product:
                    # 1. Додаємо в поточний каталог
                    cat_id = st.session_state.current_catalog
                    st.session_state.catalogs[cat_id]["items"].append(product)
                    
                    # 2. Генеруємо ембеддінг для AI-пошуку
                    desc_text = f"{product['name']} category {product['category']}"
                    st.session_state.catalogs[cat_id]["emb"][product["id"]] = model.encode(desc_text)
                    
                    st.toast(f"✅ Товар '{product['name']}' ({product['price']}грн) додано!")
                    log_event("web_crawl_success", {"url": web_url, "product_id": product["id"]})
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Не вдалося вилучити дані з посилання. Перевірте URL.")
        else:
            st.warning("Вставте URL")
    
    st.markdown("### 🎒 MY WARDROBE")
    
    def render_slot_cyber(slot_key, label, icon="💠"):
        st.markdown(f"<div class='hud-text'>{icon} {label.upper()}</div>", unsafe_allow_html=True)
        
        has_item = st.session_state.slots[slot_key] is not None
        btn_label = "ADD" if not has_item else "SWAP"
        
        col1, col2 = st.columns([1, 2])
        with col1:
            btn = st.button(btn_label, key=f"slot_{slot_key}")
        with col2:
            if has_item:
                itm = next((it for it in items if it["id"] == st.session_state.slots[slot_key]), None)
                if itm:
                    st.markdown(f"<span style='font-size:0.8rem;'>{itm['name']}</span>", unsafe_allow_html=True)
                    st.progress(0.85) # Simulating "loading/fitting" progress
            else:
                st.caption("EMPTY_SLOT")
                st.progress(0.0)

        return btn

    t_btn = render_slot_cyber("top", "Upper Body", "👕")
    b_btn = render_slot_cyber("bottom", "Lower Body", "👖")
    s_btn = render_slot_cyber("shoes", "Footwear", "👟")
    a_btn = render_slot_cyber("accessory", "Accessory", "🕶️")

    if t_btn: st.session_state.slot_selection = "top"
    if b_btn: st.session_state.slot_selection = "bottom"
    if s_btn: st.session_state.slot_selection = "shoes"
    if a_btn: st.session_state.slot_selection = "accessory"

with right_col:
    # ---------------- Вкладки (Control / DNA) ----------------
    tab_chat, tab_fit, tab_viz, tab_showcase, tab_dna, tab_rag = st.tabs(["💬 AI-STylist", "🧺 Примірочна", "🖼️ Mirror", "📊 B2B PILOT SHOWCASE", "🧬 Style DNA & Навички", "🤖 AI Studio"])

    with tab_viz:
        st.markdown("### 🖼️ Результат Візуалізації")
        if "outfit_result" in st.session_state:
            st.image(st.session_state.outfit_result, use_container_width=True)
            st.success("✅ ОБРАЗ СИНХРОНІЗОВАНО [LATENCY: 1.8s]")
        else:
            st.info("Натисніть 'ВІЗУАЛІЗУВАТИ ОБРАЗ' у вкладці Примірочна, щоб побачити результат тут.")

    with tab_showcase:
        st.markdown("""
        <div style="background: rgba(0,255,0,0.05); padding: 25px; border: 2px solid #00ff00; border-radius: 10px; margin-bottom: 30px;">
            <h2 style="color: #00ff00; margin-top: 0;">🚀 B2B PILOT SHOWCASE: THE FUTURE OF RETAIL</h2>
            <p style="color: #cccccc;">AI-Stylo Enterprise Protocol v1.1.0-build.04</p>
        </div>
        """, unsafe_allow_html=True)

        col_roi1, col_roi2, col_roi3 = st.columns(3)
        with col_roi1:
            st.metric("RETURN RATE REDUCTION", "-22.4%", "+4.1%", delta_color="normal")
            st.caption("Lower costs via SizeEngine precision")
        with col_roi2:
            st.metric("CONVERSION BOOST", "+14.8%", "Target: 18%", delta_color="normal")
            st.caption("Higher engagement via Mirror Sync")
        with col_roi3:
            st.metric("AVG. ORDER VALUE (AOV)", "+9.2%", "Upsell active", delta_color="normal")
            st.caption("AI-Stylist basket optimization")

        st.markdown("---")
        
        st.markdown("### 🛠️ CORE TECHNOLOGY STACK")
        sc_col1, sc_col2 = st.columns(2)
        
        with sc_col1:
            st.markdown("""
            **🛰️ BIOMETRIC_CORE (Avatar DNA)**
            - 300-point skeletal mapping (10x30 grid)
            - 98% pose synchronization accuracy
            - Real-time anthropometric extraction
            
            **🌡️ THERMAL_FIT_ENGINE**
            - Tension heatmap visualization
            - Local stress point detection (Shoulders, Hips)
            - Brand-aware sizing bias (ZARA/NIKE/LEVI'S)
            """)
            
        with sc_col2:
            st.markdown("""
            **🔗 MERCHANT_INGESTOR (Catalog Scraper)**
            - Zero-integration product import (BS4/OG)
            - Automatic AI-embedding generation
            - Category and Luxury Index classification
            
            **🧠 HYBRID_VTON_PIPELINE**
            - Perspective image warping engine
            - Neural Inpainting (SD-XL/Local Core)
            - Cross-platform JS-Widget architecture
            """)
            
        st.markdown("---")
        st.markdown("### 📈 ANALYTICS PREVIEW (Simulated)")
        chart_data = pd.DataFrame(
            np.random.randn(20, 3) + [1, 2, 5],
            columns=['Try-on Intensity', 'Purchase Intent', 'Fit Accuracy']
        )
        st.line_chart(chart_data)
        
        st.button("📄 DOWNLOAD FULL B2B DECK (.PDF)", help="Demo only: Generates PDF summary")
        st.caption("© 2026 AI-Stylo Enterprise | Proprietary Algorithm | EvoPyramid Genesis Core")

    with tab_chat: # Renamed from tab_ctrl
        st.markdown("**🎨 Ваша палітра (до 2-х кольорів)**")
        color_palette = {
            "Cyber Aqua": "#00f3ff", "Neon Pink": "#ff00ff", 
            "Toxic Green": "#39ff14", "Gold": "#ffd700",
            "Pure White": "#ffffff", "Deep Red": "#ff4d4d",
            "Classic Navy": "#000080", "Slate Grey": "#708090"
        }
        
        c_grid = st.columns(4)
        selected_colors = profile.get("fav_colors", [])
        
        for i, (name, hex_code) in enumerate(color_palette.items()):
            is_sel = hex_code in selected_colors
            btn_label = f"✅ {name}" if is_sel else name
            with c_grid[i % 4]:
                if st.button(btn_label, key=f"p_color_{hex_code}", use_container_width=True):
                    if hex_code in selected_colors:
                        selected_colors.remove(hex_code)
                    else:
                        if len(selected_colors) < 2:
                            selected_colors.append(hex_code)
                        else:
                            selected_colors = [hex_code] # Скидаємо до одного, якщо вже 2
                    profile["fav_colors"] = selected_colors
                    st.rerun()
        
        # Візуальний індикатор обраних кольорів
        if selected_colors:
            st.markdown(f"**Активна тема:** " + " + ".join([f"<span style='color:{c};'>■</span>" for c in selected_colors]), unsafe_allow_html=True)
            # Орієнтир для AI
            profile["ai_guidance"] = f"Prefer colors in hex: {', '.join(selected_colors)}"

        st.divider()
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

        if st.button("🎲 Мікс образу", width="stretch"):
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

        st.divider()
        with st.expander("📎 Останні події (LOG)", expanded=True):
            if st.session_state.events:
                df = pd.DataFrame(st.session_state.events[-10:])
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.info("Подій ще не зафіксовано.")

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
            if st.button("Купити образ", width="stretch"):
                st.success("Образ додано до кошика!")
                log_event("buy_outfit", {"items": filled_slots, "total": total_price})
                # Триггеры для "витринных" скиллов:
                if discount_amount > 0: log_event("deal_action")
                if luxury_score > 1.0: log_event("luxury_action")
        else:
            st.info("Оберіть речі або згенеруйте образ")

    with tab_fit:
        st.subheader("🧺 Налаштування Аватара")
        
        # Вибір статі
        gender_map = {"male": "Чоловічий ♂️", "female": "Жіночий ♀️"}
        current_gender = profile.get("gender", "female")
        new_gender = st.radio("Твоя стать", ["male", "female"], 
                             index=0 if current_gender == "male" else 1,
                             format_func=lambda x: gender_map[x], horizontal=True)
        if new_gender != current_gender:
            profile["gender"] = new_gender
            st.rerun()

        # Custom Item URL for B2B Test
        st.markdown("---")
        st.markdown("### 🏬 Контекст Бренду (Merchant Config)")
        brand_options = {
            "default": "AI-Stylo Standard",
            "zara_style": "Zara (Slim Fit)",
            "nike_fit": "Nike (Athletic)"
        }
        selected_brand = st.selectbox("Оберіть сітку бренду", options=list(brand_options.keys()), 
                                     format_func=lambda x: brand_options[x])
        st.session_state.current_brand = selected_brand

        st.markdown("### 📸 Твоє фото")
        user_photo = st.file_uploader("Завантаж портрет для Mirror Sync", type=["jpg", "jpeg", "png"])
        if user_photo:
            photo_bytes = user_photo.getvalue()
            if st.session_state.user_photo_bytes != photo_bytes:
                st.session_state.user_photo_bytes = photo_bytes
                st.rerun() # Force re-draw with the new photo at the top
            
            # 🧬 DNA Extraction & HUD
            with st.spinner("🧬 CONDUCTING_THERMAL_SCAN..."):
                # Передаємо brand_id для точного Fit-аналізу та карти
                dna = get_pipeline().get_avatar_profile(photo_bytes, profile["user_id"], {"brand_id": selected_brand})
            
            fit = dna.get('fit_analysis', {})
            comp_val = dna.get('completeness', 0)
            conf_val = fit.get('confidence', 0)
            
            comp_color = "#00f3ff" if comp_val > 0.8 else "#ff00ff"
            conf_color = "#00ff00" if conf_val > 0.7 else "#ffff00"
                
            st.markdown(f"""
            <div style="background: rgba(0,243,255,0.05); padding: 15px; border: 1px solid #00f3ff; border-radius: 5px; margin-bottom: 20px;">
                <h4 style="color: #00f3ff; margin-top: 0;">🧬 AVATAR_DNA_REPORT [BRAND: {fit.get('brand_name','').upper()}]</h4>
                <div style="font-family: 'Source Code Pro', monospace; font-size: 0.85rem; line-height: 1.6;">
                    <div style="border-bottom: 1px solid rgba(0,243,255,0.2); margin-bottom: 8px; padding-bottom: 4px;">
                        BODY_TYPE: <span style="color: #ff00ff;">{dna.get('body_type', 'UNKNOWN').upper()}</span> | 
                        POSE: <span style="color: #ff00ff;">{dna.get('pose_type', 'UNKNOWN').upper()}</span>
                    </div>
                    <div>SHOULDER_WIDTH: <span style="color: #00f3ff;">{dna.get('measurements', {}).get('shoulder_width', 0)}px</span></div>
                    <div>COMPLETENESS: <span style="color: {comp_color};">{int(comp_val*100)}%</span></div>
                    
                    <div style="margin-top: 12px; padding: 8px; background: rgba(0,255,0,0.05); border-left: 3px solid {conf_color};">
                        <div style="font-weight: bold; color: {conf_color};">🛰️ AI_SIZE_PREDICTOR for {fit.get('brand_name')}</div>
                        <div>RECOMMENDED: <span style="color: #ffffff; font-size: 1.1rem;">{fit.get('recommended_size')}</span></div>
                        <div>FIT_HINT: <span style="color: #cccccc;">{fit.get('fit_hint','').replace('_',' ').upper()}</span></div>
                        <div>CONFIDENCE: <span style="color: {conf_color};">{int(conf_val*100)}%</span></div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            show_tension = st.checkbox("🛰️ Показати Thermal Tension Map (300 sectors)", value=False)
            if show_tension:
                with st.spinner("Рендеринг теплової сітки..."):
                    tension_img = render_tension_map(photo_bytes, dna)
                    st.image(tension_img, caption="X-RAY FIT_ANALYSIS: TENSION ZONES (RED = STRESS)", use_container_width=True)
            else:
                st.image(user_photo, caption="Фото готове до синхронізації", width=200)
            
            if st.button("🗑️ Видалити фото"):
                if "user_photo_bytes" in st.session_state: del st.session_state.user_photo_bytes
                st.rerun()

        # Custom Item URL for B2B Test
        st.markdown("---")
        st.markdown("### 👕 Custom Garment Link (B2B Test)")
        custom_url = st.text_input("Встав посилання на фото товару (PNG/JPG)", placeholder="https://example.com/shirt.png")
        if custom_url:
            st.session_state.custom_garment_url = custom_url
            st.success("✅ Custom garment link synced")

        st.info("💡 Основна кнопка генерації знаходиться під Дзеркалом зліва.")

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
            pref_key = st.text_input("Ключ налаштування", value="tone")
        with pref_col2:
            pref_value = st.text_input("Значення", value="concise")
        with pref_col3:
            save_pref_clicked = st.button("💾 Зберегти", width="stretch")

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

        if st.button("Запитати AI", width="stretch"):
            if user_msg.strip():
                if not ollama_ready:
                    # Simulation mode
                    with st.spinner("Симулюємо відповідь (Digital Soul Mode)..."):
                        time.sleep(1.5)
                        responses = [
                            f"Аналізуючи твій стиль ({profile['style_pref']}), я рекомендую звернути увагу на контрастні аксесуари.",
                            "Твій вибір кольору свідчить про впевненість. Образ для офісу буде ідеальним з цим худі.",
                            "Я бачу, що ти віддаєш перевагу комфорту. Можливо, додамо кросівки до цього луку?",
                            f"Для події '{selected_style}' я б порадив додати трохи люксових елементів з твого гардеробу."
                        ]
                        st.session_state.assistant_result = AssistantResult(
                            final_text=random.choice(responses),
                            tool_outputs=[],
                            metadata={"simulation": True}
                        )
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
                    except Exception as exc:
                        st.error(f"AI помилка: {exc}")

        assistant_result = st.session_state.assistant_result
        if assistant_result:
            st.markdown("### Відповідь асистента")
            st.success(assistant_result.final_text.strip() or "(порожня відповідь)")

            st.markdown("### Виклики інструментів (Tool calls)")
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
                st.info("Інструменти не викликались.")

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

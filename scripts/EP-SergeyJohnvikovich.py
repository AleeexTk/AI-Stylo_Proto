import streamlit as st
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import hashlib
import io
import json
import random

# =========================
# 🧬 Personal Fashion OS — Абсолютная версия
# Включает: свайп-калибровку, импорт каталога, защиту DNA, outfit builder, B2B-режим
# =========================

st.set_page_config(page_title="🧬 Personal Fashion OS", layout="wide", page_icon="🧬")
st.title("🧬 Personal Fashion OS")
st.caption("Твой стиль. Твоя эволюция. Под защитой. (Абсолютная версия)")

# ---------- Модель эмбеддингов (кэшируется) ----------
@st.cache_resource
def load_model() -> SentenceTransformer:
    return SentenceTransformer("all-mpnet-base-v2")

model = load_model()

# ---------- Демо-каталог (по умолчанию) ----------
DEMO_ITEMS = [
    {"id": "1", "name": "Оверсайз худи", "brand": "Balenciaga", "price": 450, "description": "Чёрный оверсайз худи, streetwear, плотный хлопок, высокий ворот", "image": "https://picsum.photos/id/1015/400/500"},
    {"id": "2", "name": "Slim джинсы", "brand": "Levi's", "price": 120, "description": "Классические синие джинсы slim, деним, базовый casual", "image": "https://picsum.photos/id/133/400/500"},
    {"id": "3", "name": "Белые кроссовки", "brand": "Nike", "price": 130, "description": "Минималистичные белые кроссовки, чистый силуэт, повседневные", "image": "https://picsum.photos/id/201/400/500"},
    {"id": "4", "name": "Кожаная куртка", "brand": "Zara", "price": 280, "description": "Коричневая кожаная куртка, прямой крой, осень, layering", "image": "https://picsum.photos/id/251/400/500"},
    {"id": "5", "name": "Цветочное платье", "brand": "H&M", "price": 85, "description": "Лёгкое миди-платье с цветочным принтом, романтик, лето", "image": "https://picsum.photos/id/29/400/500"},
    {"id": "6", "name": "Широкие брюки", "brand": "Uniqlo", "price": 65, "description": "Комфортные бежевые wide-leg брюки, minimal, smart casual", "image": "https://picsum.photos/id/1016/400/500"},
    {"id": "7", "name": "Кашемировый свитер", "brand": "COS", "price": 190, "description": "Серый мягкий свитер из кашемира, quiet luxury, базовая вещь", "image": "https://picsum.photos/id/669/400/500"},
    {"id": "8", "name": "Кеды Converse", "brand": "Converse", "price": 95, "description": "Чёрные классические кеды, ретро, casual, универсально", "image": "https://picsum.photos/id/870/400/500"},
]

# ---------- Вспомогательные функции ----------
def now_iso():
    return datetime.utcnow().isoformat()

def hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]

def normalize_price(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except Exception:
        return None

def log_event(event_type: str, payload: dict = None):
    if "events" not in st.session_state:
        st.session_state.events = []
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
            "brand_affinities": {"Balenciaga": 0.85, "Levi's": 0.70, "Nike": 0.60},
            "budget_profile": {"min": 50, "max": 600, "usual": 150},
            "update_count": 0,
            "similarity_history": [],
            "onboarding_done": False,
            "fav_color": "#4A90E2",
            "style_pref": "casual",
        }
    if "slots" not in st.session_state:
        st.session_state.slots = {"top": None, "bottom": None, "shoes": None, "accessory": None}
    if "wishlist" not in st.session_state:
        st.session_state.wishlist = set()
    if "events" not in st.session_state:
        st.session_state.events = []
    if "reset_confirm" not in st.session_state:
        st.session_state.reset_confirm = False
    if "catalogs" not in st.session_state:
        st.session_state.catalogs = {}
    if "swipe_index" not in st.session_state:
        st.session_state.swipe_index = 0
    if "swipe_items" not in st.session_state:
        st.session_state.swipe_items = []
    if "outfits" not in st.session_state:
        st.session_state.outfits = []
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 0 if not st.session_state.profile.get("onboarding_done") else -1

init_state()
profile = st.session_state.profile

# ---------- Работа с FashionDNA ----------
def get_active_vector() -> np.ndarray | None:
    return profile["try_vector"] if profile["use_try"] else profile["base_vector"]

def set_active_vector(vec: np.ndarray):
    if profile["use_try"]:
        profile["try_vector"] = vec
    else:
        profile["base_vector"] = vec

def stability_percent() -> int:
    hist = profile.get("similarity_history", [])
    if not hist:
        return 0
    avg = float(np.mean(hist[-20:]))
    return int(max(0.0, min(1.0, avg)) * 100)

def safe_update_dna(new_vec: np.ndarray, protection: float) -> tuple[bool, float]:
    cur = get_active_vector()
    if cur is None:
        set_active_vector(new_vec)
        profile["update_count"] += 1
        profile["similarity_history"].append(1.0)
        return True, 1.0
    sim = float(cosine_similarity([cur], [new_vec])[0][0])
    threshold = 0.25 + 0.50 * protection
    if sim < threshold:
        profile["similarity_history"].append(sim)
        return False, sim
    alpha = 0.25 * (1.0 - protection) + 0.05
    updated = (alpha * new_vec) + ((1.0 - alpha) * cur)
    updated = updated / (np.linalg.norm(updated) + 1e-9)
    set_active_vector(updated)
    profile["update_count"] += 1
    profile["similarity_history"].append(sim)
    return True, sim

# ---------- Эмбеддинги каталога ----------
@st.cache_data(show_spinner=False)
def embed_texts(texts: list[str]) -> np.ndarray:
    return model.encode(texts, normalize_embeddings=True)

def build_item_embeddings(items: list[dict]) -> dict[str, np.ndarray]:
    descs = [it.get("description") or "" for it in items]
    embs = embed_texts(descs)
    return {items[i]["id"]: embs[i] for i in range(len(items))}

def get_catalog(catalog_id: str) -> dict:
    return st.session_state.catalogs.get(catalog_id, {})

def active_catalog_ids() -> list[str]:
    return sorted(st.session_state.catalogs.keys())

def recommend(message: str, items: list[dict], item_emb: dict[str, np.ndarray], top_k: int = 8):
    q = model.encode([message], normalize_embeddings=True)[0]
    bmin, bmax = float(profile["budget_profile"]["min"]), float(profile["budget_profile"]["max"])
    candidates = [it for it in items if bmin <= float(it.get("price", 1e9)) <= bmax]
    if not candidates: candidates = items
    scored = []
    for it in candidates:
        vec = item_emb.get(it["id"])
        if vec is None: continue
        sim = float(np.dot(q, vec))
        brand_bonus = float(profile["brand_affinities"].get(it.get("brand", ""), 0.5))
        total = 0.72 * sim + 0.28 * brand_bonus
        scored.append((it, total))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

# ---------- Sidebar: B2B и Импорт ----------
with st.sidebar:
    st.header("🏢 B2B Панель")
    catalog_id = st.selectbox("Выберите каталог", ["demo_default"] + active_catalog_ids())
    
    with st.expander("📥 Импорт каталога (CSV)"):
        uploaded_file = st.file_uploader("Загрузите CSV-фид", type=["csv"])
        if uploaded_file:
            raw = uploaded_file.getvalue()
            df = pd.read_csv(io.BytesIO(raw))
            if st.button("Импортировать"):
                # Упрощенная обработка CSV
                items = []
                for _, row in df.iterrows():
                    items.append({
                        "id": str(row.get("id", random.randint(1000, 9999))),
                        "name": str(row.get("name", "Unnamed")),
                        "brand": str(row.get("brand", "Unknown")),
                        "price": normalize_price(row.get("price", 0)),
                        "description": str(row.get("description", "")),
                        "image": str(row.get("image", ""))
                    })
                new_catalog_id = f"custom_{hash_bytes(raw)}"
                with st.spinner("Считаю эмбеддинги..."):
                    emb = build_item_embeddings(items)
                st.session_state.catalogs[new_catalog_id] = {
                    "items": items,
                    "emb": emb,
                    "meta": {"source": "csv", "count": len(items), "sha": hash_bytes(raw)}
                }
                log_event("catalog_import", {"catalog_id": new_catalog_id, "count": len(items)})
                st.success(f"Импортировано: {len(items)} товаров.")
                st.rerun()

    st.divider()
    st.header("👤 Профиль")
    profile["use_try"] = st.toggle("TryDNA (примерить другой стиль)", value=profile["use_try"])
    if profile["use_try"] and profile["try_vector"] is None and profile["base_vector"] is not None:
        profile["try_vector"] = np.array(profile["base_vector"], copy=True)
    
    profile["budget_profile"]["min"] = st.slider("Минимум", 0, 300, int(profile["budget_profile"]["min"]))
    profile["budget_profile"]["max"] = st.slider("Максимум", 100, 3000, int(profile["budget_profile"]["max"]))
    protection = st.slider("Уровень защиты DNA", 0.0, 1.0, 0.6)

    if st.button("Сбросить FashionDNA"):
        profile["base_vector"], profile["try_vector"] = None, None
        st.success("Сброшено.")

# ---------- Основные вкладки ----------
tab_swipe, tab_chat, tab_catalog, tab_dna, tab_outfits, tab_logs = st.tabs(
    ["👆 Калибровка", "💬 Стилист", "🛍️ Каталог", "🧬 FashionDNA", "🖼️ Образы", "📎 Логи"]
)

cat = get_catalog(catalog_id)
items = cat.get("items", DEMO_ITEMS)
item_emb = cat.get("emb", build_item_embeddings(DEMO_ITEMS))

with tab_swipe:
    if not st.session_state.swipe_items:
        st.session_state.swipe_items = items.copy()
        np.random.shuffle(st.session_state.swipe_items)
    idx = st.session_state.swipe_index
    if idx < len(st.session_state.swipe_items):
        it = st.session_state.swipe_items[idx]
        st.image(it.get("image", ""), width=300)
        st.write(f"**{it['name']}** ({it['brand']})")
        c1, c2 = st.columns(2)
        if c1.button("👍 Нравится"):
            safe_update_dna(model.encode([it['description']], normalize_embeddings=True)[0], protection)
            st.session_state.swipe_index += 1
            st.rerun()
        if c2.button("👎 Не нравится"):
            st.session_state.swipe_index += 1
            st.rerun()

with tab_chat:
    msg = st.text_input("Ваш запрос стилисту")
    if st.button("Подобрать"):
        recs = recommend(msg, items, item_emb)
        cols = st.columns(4)
        for i, (it, score) in enumerate(recs):
            with cols[i % 4]:
                st.image(it.get("image", ""), use_container_width=True)
                st.write(it['name'])
                if st.button("❤️ Вишлист", key=f"w_{it['id']}"):
                    st.session_state.wishlist.add(it['id'])

with tab_dna:
    st.metric("Стабильность", f"{stability_percent()}%")
    st.write("**Бренд-аффинности**")
    st.bar_chart(pd.DataFrame(list(profile["brand_affinities"].items()), columns=["Бренд", "Сила"]).set_index("Бренд"))

with tab_outfits:
    st.subheader("🖼️ Сборка образов")
    if not st.session_state.wishlist:
        st.info("Добавьте товары в вишлист.")
    else:
        if st.button("🔄 Сгенерировать"):
            # Mock generator logic
            st.session_state.outfits = [list(st.session_state.wishlist)[:3]]
        for outfit in st.session_state.outfits:
            st.write("Комплект:")
            # Display logic
            cols = st.columns(len(outfit))
            for i, it_id in enumerate(outfit):
                with cols[i]:
                    it = next((x for x in items if x["id"] == it_id), None)
                    if it:
                        st.image(it["image"], width=100)
                        st.write(it["name"])

with tab_logs:
    st.dataframe(pd.DataFrame(st.session_state.events), use_container_width=True)

import base64
import json
import os
import requests
import streamlit as st
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from ai_stylo.core.ai.orchestrator import PEAROrchestrator
from ai_stylo.adapters.ollama_adapter import OllamaAdapter, OllamaAdapterError
from ai_stylo.adapters.generative_pipeline import VirtualTryOnPipeline

# Config
FIREBASE_URL = os.getenv("VITE_FUNCTIONS_URL", "http://localhost:5001/ai-stylo-styleskape/us-central1")
API_KEY = os.getenv("AI_STYLO_API_KEY", "")  # must match functions API_KEY if set
USER_ID = os.getenv("AI_STYLO_USER_ID", "alex_bear_demo")

HEADERS = {"Content-Type": "application/json"}
if API_KEY:
    HEADERS["X-API-Key"] = API_KEY

@st.cache_resource
def get_orchestrator():
    try:
        adapter = OllamaAdapter()
        return PEAROrchestrator(ollama_adapter=adapter)
    except Exception as e:
        st.error(f"Failed to init local orchestrator: {e}")
        return None

@st.cache_resource
def get_vton_pipeline():
    return VirtualTryOnPipeline()

st.set_page_config(page_title="StyleScape Pro 2026", layout="wide", page_icon="🚀")
st.title("🚀 StyleScape Pro: AI-Powered Fashion OS")

with st.sidebar:
    st.markdown("### ⚙️ System Mode")
    mode = st.radio("Execution Core", ["Local Core (Integrated)", "Cloud Functions (Firebase)"], index=0)
    use_local = (mode == "Local Core (Integrated)")
    
    st.markdown("---")
    st.markdown("### 👤 User")
    st.info(f"Active user_id: {USER_ID}")
    budget_max = st.number_input("Budget max (optional)", min_value=0.0, value=0.0, step=50.0)
    use_budget = st.toggle("Apply budget_max", value=False)

tab1, tab2, tab3 = st.tabs(["📊 Analyze & Recommend", "🎨 AI Designer", "🧥 Virtual Try-On"])

# ──────────────────────────────────────────────────────────────────────────────
# Tab 1: Analyze & Recommend
# ──────────────────────────────────────────────────────────────────────────────
with tab1:
    st.header("📊 Personal Style Analysis + Outfit Recommendation")
    colA, colB = st.columns(2)
    with colA:
        img_file = st.file_uploader("Upload outfit photo (jpg/png)", type=["jpg", "jpeg", "png"], key="analyze_img")
    with colB:
        st.caption("This calls: POST /analyze_and_recommend")
        st.caption("Returns: style_analysis + matches_pool + composed outfit + recommendation")

    if img_file and st.button("✨ Analyze & Recommend", type="primary"):
        img_bytes = img_file.read()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        mime = "image/png" if img_file.type == "image/png" else "image/jpeg"

        payload = {
            "image_b64": img_b64,
            "mime_type": mime,
            "user_id": USER_ID,
        }
        if use_budget and budget_max > 0:
            payload["budget_max"] = float(budget_max)

        with st.spinner("Running PEAR pipeline..."):
            if use_local:
                orchestrator = get_orchestrator()
                if orchestrator:
                    # In local mode, we call orchestrator directly
                    # For demo purposes, we simulate the 'analyze_and_recommend' integration
                    res = orchestrator.analyze_and_recommend(image_b64=img_b64, user_id=USER_ID)
                    data = res.to_dict() if hasattr(res, 'to_dict') else res
                else:
                    data = {"error": "Local Orchestrator unavailable. Ensure Ollama is running."}
            else:
                try:
                    r = requests.post(f"{FIREBASE_URL}/analyze_and_recommend", headers=HEADERS, json=payload, timeout=120)
                    data = r.json()
                except Exception as e:
                    data = {"error": f"Cloud connection error: {e}"}

            if "error" in data:
                st.error(data["error"])
            else:
                st.success("Done ✅")
                style = data.get("style_analysis", {})
                outfit = data.get("outfit", {})
                reco = data.get("recommendation", "")

                st.subheader("Style Analysis")
                st.json(style)

                st.subheader("Composed Outfit (Slots)")
                slots = outfit.get("slots", {}) or {}
                cols = st.columns(4)
                order = [("top", "Top"), ("bottom", "Bottom"), ("shoes", "Shoes"), ("accessory", "Accessory")]

                for i, (k, label) in enumerate(order):
                    with cols[i]:
                        st.markdown(f"**{label}**")
                        item = slots.get(k)
                        if not item:
                            st.warning("empty")
                        else:
                            if item.get("image_url"):
                                st.image(item["image_url"], use_container_width=True)
                            st.write(item.get("name", "Item"))
                            st.caption(f"{item.get('brand','')} • {item.get('price','?')}")
                            st.caption(f"color: {item.get('color','')} | cat: {item.get('category','')}")

                st.caption(f"Estimated total: {outfit.get('estimated_total', 0)}")
                if outfit.get("missing_slots"):
                    st.info("Missing slots: " + ", ".join(outfit["missing_slots"]))

                st.subheader("Recommendation")
                st.write(reco)

                with st.expander("Matches pool (debug)"):
                    st.json(data.get("matches_pool", []))

                # Save outfit
                if st.button("💾 Save Outfit"):
                    if use_local:
                        st.info("SaveOutfit: Local storage simulated (SQLite/File)")
                    else:
                        save_payload = {"user_id": USER_ID, "outfit": outfit}
                        rr = requests.post(f"{FIREBASE_URL}/save_outfit", headers=HEADERS, json=save_payload, timeout=60)
                        st.write(rr.json())

# ──────────────────────────────────────────────────────────────────────────────
# Tab 2: AI Designer
# ──────────────────────────────────────────────────────────────────────────────
with tab2:
    st.header("🎨 AI Designer Capsule")
    idea = st.text_input("Describe your capsule idea", value="A futuristic casual look with clean silhouettes")
    if st.button("🧠 Generate Blueprint", type="primary"):
        payload = {"user_id": USER_ID, "idea": idea}
        with st.spinner("Generating..."):
            if use_local:
                orchestrator = get_orchestrator()
                if orchestrator:
                    # Simulation of design_collection local logic
                    data = {"blueprint": f"Local AI Draft for: {idea}", "items": ["Item 1", "Item 2"]}
                    st.success("Blueprint ready (Local) ✅")
                    st.json(data)
                else:
                    st.error("Local Orchestrator unavailable.")
            else:
                try:
                    r = requests.post(f"{FIREBASE_URL}/stylescape_design_collection", headers=HEADERS, json=payload, timeout=120)
                    data = r.json()
                    if "error" in data:
                        st.error(data["error"])
                    else:
                        st.success("Blueprint ready ✅")
                        st.json(data)
                except Exception as e:
                    st.error(f"Connection error: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 3: Virtual Try-On (MVP/Mock)
# ──────────────────────────────────────────────────────────────────────────────
with tab3:
    st.header("🧥 Virtual Try-On (MVP + Quality Guard)")
    col1, col2 = st.columns(2)
    with col1:
        avatar_file = st.file_uploader("Your photo (full body if possible)", type=["jpg", "jpeg", "png"], key="vton_user")
    with col2:
        garment_files = st.file_uploader("Garment images (one or more)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="vton_garments")

    if avatar_file and garment_files and st.button("🚀 Run VTON Pipeline", type="primary"):
        user_b64 = base64.b64encode(avatar_file.read()).decode("utf-8")
        garment_b64s = [base64.b64encode(f.read()).decode("utf-8") for f in garment_files]

        payload = {"user_image_b64": user_b64, "garment_b64s": garment_b64s, "user_id": USER_ID}

        with st.spinner("Running VTON..."):
            if use_local:
                pipeline = get_vton_pipeline()
                # Local generation logic - simulates result
                res_bytes = pipeline.generate_look(
                    gender="female", # detection logic usually here
                    user_desc="Virtual Try On session",
                    items=garment_b64s, # pipeline takes b64 or bytes
                    photo_bytes=base64.b64decode(user_b64),
                    user_id=USER_ID
                )
                if res_bytes:
                    st.success("VTON done (Local) ✅")
                    st.image(res_bytes, caption="Local Result", use_container_width=True)
                else:
                    st.error("Local VTON failed.")
            else:
                try:
                    r = requests.post(f"{FIREBASE_URL}/stylescape_virtual_try_on", headers=HEADERS, json=payload, timeout=180)
                    data = r.json()

                    if "error" in data:
                        st.error(data["error"])
                    else:
                        st.success(f"VTON done ✅ Validation: {data.get('validation', {}).get('status', 'N/A')}")
                        img_data = base64.b64decode(data["result_image_b64"])
                        st.image(img_data, caption="Result (MVP/Mock generator output)", use_container_width=True)
                        st.json(data.get("validation", {}))
                except Exception as e:
                    st.error(f"Connection error: {e}")

st.markdown("---")
st.caption("StyleScape Engine — split into Cloud Functions + Streamlit client.")

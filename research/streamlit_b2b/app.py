import sys
import os
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Path fix
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from ai_stylo.core.database import SessionLocal
from ai_stylo.core.catalog.service import CatalogService

# Initialize DB and Service
db = SessionLocal()
catalog = CatalogService(db)

st.set_page_config(page_title="AI-Stylo | Merchant Dashboard", layout="wide")

st.sidebar.title("🚀 AI-Stylo B2B")
st.sidebar.caption("v1.1-autumn | Merchant ID: demo_1")

menu = st.sidebar.radio("Navigation", ["Overview", "Product Catalog", "Merchant Integration"])

if menu == "Overview":
    st.title("📊 Merchant Analytics Overview")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Try-Ons", "1,284", "+15%")
    col2.metric("Size Recs Confidence", "89%", "+2%")
    col3.metric("Conversion Uplift", "24.5%", "+3.2%")
    
    st.markdown("### Conversion Trend")
    chart_data = pd.DataFrame(np.random.randn(20, 2), columns=["Direct", "AI-Assisted"])
    st.line_chart(chart_data)

elif menu == "Product Catalog":
    st.title("📦 Catalog Management")
    
    with st.expander("Import New Product from URL", expanded=True):
        prod_url = st.text_input("Product URL", placeholder="https://store.com/products/item-123")
        if st.button("Ingest with AI-Stylo"):
            try:
                product = catalog.ingest_from_url("demo_1", prod_url)
                st.success(f"✅ Product '{product.title}' ingested and analyzed!")
                st.json(product.meta_data)
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

    st.divider()
    st.subheader("Your Products")
    prods = catalog.get_products("demo_1")
    if prods:
        df = pd.DataFrame([{
            "SKU": p.id,
            "Brand": p.brand,
            "Title": p.title,
            "Price": f"{p.price} {p.currency}",
            "Category": p.category
        } for p in prods])
        st.table(df)
    else:
        st.info("No products ingested yet.")

elif menu == "Merchant Integration":
    st.title("🔌 Integration Center")
    st.info("Copy and paste the snippet below before the closing </body> tag of your product page.")
    
    sdk_path = "ai_stylo/web_widget/sdk.js"
    st.code(f"""<!-- AI-Stylo Widget -->
<script src="https://cdn.ai-stylo.com/sdk.js?merchant_id=demo_1"></script>""", language="html")
    
    st.markdown("### Preview")
    st.caption("How the widget button looks on your site:")
    st.image("https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&q=80&w=300")
    st.button("✨ Virtual Try-On", disabled=True)

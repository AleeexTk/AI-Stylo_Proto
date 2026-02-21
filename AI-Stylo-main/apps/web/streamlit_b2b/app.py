import sys
from pathlib import Path
import streamlit as st

project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from apps.core.contracts import Item, Profile, Event

st.set_page_config(page_title="Personal Fashion OS | B2B Plugin Demo", layout="centered")
st.title("🛍️ Картка товару (B2B Плагін)")

st.markdown("### Худи Balenciaga (Демо)")
st.image("https://picsum.photos/id/1015/400/500", width=300)
st.write("**Ціна:** 4500 грн")

st.divider()
st.subheader("Модуль EvoPyramid: Fashion OS")
st.caption("Цей блок інтегрується на сайт партнера.")

if st.button("✨ Згенерувати образ з цим товаром", type="primary"):
    st.success("API Виклик в core-layer. Образ підібрано!")
    cols = st.columns(3)
    with cols[0]:
        st.image("https://picsum.photos/id/133/400/500", caption="Джинси Levi's (2700 грн)")
    with cols[1]:
        st.image("https://picsum.photos/id/201/400/500", caption="Кросівки Nike (3200 грн)")
    with cols[2]:
        st.image("https://picsum.photos/id/660/400/500", caption="Сумка Hermes (9500 грн)")
    
    st.info("Бюджет враховано. Taste Stability використано.")

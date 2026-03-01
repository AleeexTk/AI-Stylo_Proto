# Repo bootstrap (production track)

## 1) Layered structure

### Level 0 — Core
- `apps/core/fashion_dna.py` — safe updates, drift guard, stability.
- `apps/core/catalog.py` — import, normalization, embedding cache.
- `apps/core/reco.py` — ranking by query + DNA + budget + brand affinity.
- `apps/core/outfits.py` — explainable outfit compatibility rules v0.

### Level 1 — Experience
- `apps/web/streamlit_rpg/` — inventory slots, outfit builder, gamified progression.
- `apps/web/streamlit_b2b/` — minimal storefront demo widget.

### Level 2 — Integration
- `apps/adapters/gemini_tryon.py`
- `apps/adapters/shopify.py`
- `apps/adapters/woocommerce.py`
- `apps/adapters/telegram_leads.py` (later)

### Level 3 — Growth / Skills
- Skill packs and progression metrics that unlock only after qualifying behavior.

## 2) Must-have MVP screen (RPG)
- Slot selection and replacement.
- Outfit generation button.
- Total price + budget awareness.
- Buy-all CTA.
- Event logging for future skill progression.

## 3) B2B pitch page requirements
- What it is (1 block).
- How to embed (script/button example).
- Why it matters (hypothesis metrics).
- Direct contact CTA.

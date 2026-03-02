# AI-Stylo / Stylescape v1.0 Architecture Blueprint

## Product Blocks v1.0

1. **Outfit Engine** (Core Value)
2. **Skill Tree** (Differentiation + Explainability + Segmentation)
3. **Try-On Service** (API-first + Cache + Intent Gating)
4. **Merchant Analytics** (B2B Value)
5. **Integrations** (CSV/API + Widget/SDK)

---

## 1. System Layers

### 1.1 Client Layer

* **Widget/SDK**: Embedded on partner sites (Outfit picking, Try-On, Buy outfit, Profile/Skills).
* **Demo Web**: Sandboxed showcase (stylescape.space).

### 1.2 API Gateway / BFF

* Single entry point for auth (merchant/user), rate limits, and routing.

### 1.3 Core Services

* **Catalog**: Normalization, item storage, assets.
* **User/Profile**: User preferences, DNA vectors, style history.
* **Events**: Append-only event store (swipes, views, wishlist, generating).
* **Skill Engine**: Real-time counter updates, xp, level, and unlocking logic.
* **Recommendation**: Candidate generation, scoring (skill modifiers), explainability.
* **Merchant Analytics**: ROI tracking, segment behavior, funnel analysis.

### 1.4 Try-On Service (Async)

* Asynchronous job queue (Redis).
* Provider abstraction (Fal, Runway, Stability, etc.).
* Caching (avatar_hash + outfit_hash).
* Intent-gated rendering.

---

## 2. Storage Strategy

* **Postgres**: Primary relational data (merchants, items, users, events).
* **Redis**: Job queue, rate limits, session/hot cache.
* **S3/CDN**: Avatars, Try-On results, JSON snapshots.

---

## 3. Data Flows

### 3.1 Outfit Generation

1. UI requests outfits.
2. Core logs `generate_outfits` event.
3. Skill Engine updates XP.
4. Recommendation Engine returns N outfits + explainability tags.

### 3.2 Try-On (The "Lazy" Flow)

1. UI requests job.
2. API checks cache.
3. If miss, adds to queue.
4. Worker processes using API-first providers.
5. UI polls until done.

---

## 4. Repository Structure (Actual)

```text
ai_stylo/
  core/
    ai/                 # PEAR Orchestrator, Agentic Interface
    memory/             # SQLite Stores (Profile, Preference, Vector)
    skills/             # Unified Skill Engine & Base Skills
    tools/              # Local Tool Registry & Shotlist/Capsule tools
    contracts.py        # Shared Dataclasses
  adapters/
    ollama_adapter.py   # Main LLM Client
    generative_pipeline.py # SD-XL & MediaPipe VTON
    google_ai_adapter.py # RAG Fallback
  extension/            # Chrome Extension Logic (JS/JSON)
apps/
  web/
    streamlit_rpg/      # B2C Immersive UI
    streamlit_b2b/      # B2B Pilot Showcase
```

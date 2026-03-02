# 🧬 AI-Stylo: The Personal Fashion OS

> **"Style is not just how you look; it's how your data feels."**  
> Powered by **EvoPyramid PEAR Architecture** and Local AI.

AI-Stylo is a state-of-the-art Personal Fashion Operating System designed to bridge the gap between human aesthetics and machine reasoning. It utilizes a local-first AI stack (Ollama + Stable Diffusion) to provide intimate, data-driven style recommendations while respecting the user's "Style DNA".

---

## 📐 Core Architecture: The PEAR Pipeline

The heart of AI-Stylo is the **PEAR Orchestrator** (`ai_stylo/core/ai/orchestrator.py`), which follows a strict 5-stage bio-informatic reasoning loop:

1. **👁️ PERCEIVE**: Intent extraction and environmental awareness.
2. **🌿 ENRICH**: Real-time context gathering (Weather, Events, Trends).
3. **🧬 ADAPT**: Personalizing the request via User Style DNA and Personality Memory.
4. **⚡ ACT**: Multi-tool execution (Recommendation, Generation, Purchase Manifests).
5. **🧠 REFLECT**: Self-correction and learning for future interactions.

---

## 📂 Project Structure

```bash
AI-Stylo_Proto/
├── main.py                    # 🚀 Main entry point
├── ai_stylo/
│   ├── core/                  # 🧠 The Brain
│   │   ├── ai/                # Orchestration, Agentic DOM Parsing
│   │   ├── memory/            # SQLite Persistence (Profile, Prefs, Vectors)
│   │   ├── skills/            # RPG Skill Engine (Gamification)
│   │   └── contracts.py       # Hardened Dataclasses
│   ├── adapters/              # 🔌 The Nervous System
│   │   ├── ollama_adapter.py  # Local LLM Interface (Robust Retry logic)
│   │   ├── generative_pipeline.py # Neural Try-On & MediaPipe Warping
│   │   └── google_ai_adapter.py # RAG Fallback
│   └── extension/             # 🌐 Chrome Extension Bridge
├── apps/                      # 🖥️ Experience Layers
│   └── web/                   # Streamlit RPG & B2B Portals
├── configs/                   # ⚙️ Identity & Identity Manifests
└── tests/                     # 🧪 Verification Suite
```

---

## ⚡ Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **Ollama** (`llama3.2` + `nomic-embed-text`)
- **Stable Diffusion API** (Optional for local VTON)

### 2. Installation

```bash
pip install -r requirements.txt
cp .env.example .env  # Configure your endpoints
```

### 3. Execution

```bash
# Start the full experience
python main.py
```

---

## 🛡️ Identity & Compliance

AI-Stylo follows the **EVO_IDENTITY.yaml** manifest. It ensures:

- **Isolation Level: High** (Privacy first)
- **Quarantine Enabled** (Unrecognized inputs are sanitized)
- **Dual-Mode UI** (Immersive RPG for users, Professional Grid for B2B)

---

## 🚀 Roadmap: The Evolutionary Path

- [x] **PEAR Orchestrator** (Bio-informatic pipeline)
- [x] **Neural Warping** (MediaPipe pose-to-garment sync)
- [x] **Agentic DOM Parser** (Real-time item extraction using BS4)
- [ ] **Stylescape Hub Integration** (Production SaaS connector)
- [ ] **Real-world Trial** (BETA testing in Kyiv Fashion Cluster)

---
---

##### Created with ❤️ by the AI-Stylo Dev Collective (AleeexTk & SergeyJohnvikovich)

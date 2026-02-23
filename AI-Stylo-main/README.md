# 🧬 AI-Stylo Core: Personal Fashion OS

AI-Stylo is a fashion recommendation prototype with two UX modes on one core:

- **RPG Inventory UI** for B2C engagement (`apps/web/streamlit_rpg/app.py`)
- **B2B Widget Demo** for partner stores (`apps/web/streamlit_b2b/app.py`)

## Quick start

```bash
pip install -r requirements.txt
```

## One-click launch from unpacked ZIP

After downloading and unpacking the repository ZIP:

- **Windows:** double-click `start_ai_stylo.bat`
- **macOS/Linux:** run `./start_ai_stylo.sh`

This opens a local launcher window with one button. The launcher automatically:
1. creates `.venv` (on first run),
2. installs dependencies from `requirements.txt`,
3. starts the Streamlit project interface.

### One-command runs

```bash
make run-rpg
make run-b2b
make demo-data
```

- `run-rpg` launches the main Streamlit RPG app.
- `run-b2b` launches the embedded-store demo screen.
- `demo-data` generates `data/demo_catalog.json` for repeatable local demos.

## Run from unpacked ZIP (one click)

After downloading and unpacking the repository archive, you can start the app without manual setup:

- **Windows:** double-click `start_ai_stylo.bat`
- **Linux/macOS:** run `./start_ai_stylo.sh`

On first launch the script will:
1. Create `.venv` inside the project folder
2. Install dependencies from `requirements.txt`
3. Auto-start the Streamlit RPG interface

For the B2B demo mode use:

```bash
./start_ai_stylo_b2b.sh
```

## Environment variables

```bash
# Ollama connection
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_CHAT_MODEL=llama3
export OLLAMA_EMBED_MODEL=nomic-embed-text
export OLLAMA_TIMEOUT=30

# Optional: allow legacy Google RAG fallback when Ollama is unavailable
export USE_GOOGLE_RAG_FALLBACK=0
```

## Local run example (Ollama-first)

```bash
# 1) Start Ollama and pull models once
ollama serve
ollama pull llama3
ollama pull nomic-embed-text

# 2) Run app
python main.py
# or
streamlit run apps/web/streamlit_rpg/app.py
```

## Current repo layout

```text
apps/
  core/
    contracts.py
    skills_engine.py
  adapters/
    google_ai_adapter.py
  web/
    streamlit_rpg/app.py
    streamlit_b2b/app.py
scripts/
  demo_data.py
```

## Product architecture (target)

See `docs/REPO_BOOTSTRAP.md` for the recommended “Core / Experience / Integration / Growth” structure and rollout sequence.

## Execution roadmap

See `docs/GITHUB_ISSUES.md` for a prioritized issue list that can be copied into GitHub Issues.

## Local Ollama assistant plan (RU)

See `docs/LOCAL_AI_ASSISTANT_PLAN_RU.md` for a detailed architecture, roadmap, risks, testing, and budget for the offline-first Sergey assistant.

# 🧬 AI-Stylo Core: Personal Fashion OS

AI-Stylo is a fashion recommendation prototype with two UX modes on one core:

- **RPG Inventory UI** for B2C engagement (`apps/web/streamlit_rpg/app.py`)
- **B2B Widget Demo** for partner stores (`apps/web/streamlit_b2b/app.py`)

## Quick start

```bash
pip install -r requirements.txt
```

### One-command runs

```bash
make run-rpg
make run-b2b
make demo-data
```

- `run-rpg` launches the main Streamlit RPG app.
- `run-b2b` launches the embedded-store demo screen.
- `demo-data` generates `data/demo_catalog.json` for repeatable local demos.

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

## Implementation status and EvoPyramid note (RU)

See `docs/IMPLEMENTATION_STATUS_RU.md` for a repository-based status check and explicit marking that development/testing is done on a minimal necessary EvoPyramid architecture basis for AI-Stylo.

PYTHON ?= python
STREAMLIT ?= streamlit

.PHONY: run-rpg run-b2b demo-data check

run-rpg:
	$(PYTHON) main.py

run-b2b:
	$(STREAMLIT) run apps/web/streamlit_b2b/app.py

demo-data:
	$(PYTHON) scripts/demo_data.py

check:
	$(PYTHON) -m py_compile main.py apps/core/contracts.py apps/core/skills_engine.py apps/web/streamlit_rpg/app.py apps/web/streamlit_b2b/app.py

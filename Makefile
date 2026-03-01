PYTHON ?= python
STREAMLIT ?= streamlit

.PHONY: run-rpg run-b2b demo-data check test-smoke

run-rpg:
	$(PYTHON) main.py

run-b2b:
	$(STREAMLIT) run apps/web/streamlit_b2b/app.py

demo-data:
	$(PYTHON) scripts/demo_data.py

check:
	$(PYTHON) -m py_compile main.py ai_stylo/core/*.py apps/web/streamlit_rpg/*.py apps/web/streamlit_b2b/*.py

test-smoke:
	$(PYTHON) -m pytest tests/test_smoke.py -v

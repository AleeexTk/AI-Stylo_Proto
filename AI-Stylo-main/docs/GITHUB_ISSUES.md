# Suggested GitHub Issues (copy-ready)

## P0 — Repository hardening
1. **Add deterministic local run commands**
   - AC: `make run-rpg`, `make run-b2b`, `make demo-data` work locally.
2. **Split core from UI logic**
   - AC: recommendation and profile logic moved from Streamlit app to `apps/core/*` modules.
3. **Unify startup docs**
   - AC: README has one quick start and one architecture link.

## P1 — MVP product readiness
4. **Implement explainable outfit rules v0**
   - AC: no pure random fill; each slot has a compatibility reason.
5. **Stabilize FashionDNA update flow**
   - AC: thresholded updates + drift guard + tests.
6. **Budget-aware full outfit flow**
   - AC: user sees slot-level picks, total, and over-budget warning.

## P2 — B2B integration readiness
7. **Create plugin-like adapter contracts**
   - AC: shop adapters share one interface for product payload and CTA callbacks.
8. **Publish B2B mini landing page content**
   - AC: “What / How / KPI hypothesis / Contact” in one page.
9. **Telemetry event schema freeze v1**
   - AC: event names and required fields documented and validated.

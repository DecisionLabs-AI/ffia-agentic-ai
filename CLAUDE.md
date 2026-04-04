# FFIA — Claude Code Instructions

## Project
FFIA (Fuel & Food Impact Analyzer) — MADT 7204 Vibe Coding, W1–W6.
IT Lead: Kanpirom Suksawat. Stack: Python, Streamlit, Claude Sonnet, SQLite.

## Coding Rules
- Always add `# Step N:` comments explaining each logical block
- Security first: API keys from `.env` only, never hardcoded
- Update `docs/rubric-status.md` after completing each weekly milestone
- No new files unless necessary — prefer editing existing ones

## Architecture (current)
- `agent/main.py` — LLM core, ReAct tool loop
- `app/main.py` — Streamlit UI
- `agent/tools/` — one file per tool
- `data/ffia.db` — SQLite database (to be created in W2)

## Next Up (W2)
1. `agent/tools/invoice_reader.py` — Claude Vision OCR
2. `data/db.py` — SQLite helpers (invoices, invoice_items, margin_analysis tables)
3. Wire file uploader + DB into `app/main.py`
4. Build `get_oil_price`, `calculate_margin`, `simulate_scenario` tools

## Do Not
- Commit `.env` (it is in .gitignore)
- Use pytesseract — use Claude Vision for OCR instead
- Add features beyond the current week's scope

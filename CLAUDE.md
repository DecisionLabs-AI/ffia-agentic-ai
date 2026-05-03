# FFIA — Claude Code Instructions

## Project
FFIA (Fuel & Food Impact Analyzer) — MADT 7204 Vibe Coding, W1–W6.
IT Lead: Kanpirom Suksawat. Stack: Python, Next.js, FastAPI, Gemini 2.5 Flash (Vertex AI), PostgreSQL.

## Coding Rules
- Always add `# Step N:` comments explaining each logical block
- Security first: API keys from `.env` only, never hardcoded
- Update `docs/rubric-status.md` after completing each weekly milestone
- No new files unless necessary — prefer editing existing ones
- **Whenever the stack, libraries, auth method, or architecture changes — update CLAUDE.md immediately to reflect the truth. CLAUDE.md is the source of truth for planning.**

## Architecture (current — W4 Complete)

| Layer | Entry Point | Notes |
|---|---|---|
| Frontend | `frontend/` | Next.js — pages: chat, dashboard, login, profile, setup, upload, cost-data |
| Backend API | `api/main.py` | FastAPI — routers in `api/routers/`, routes in `api/routes/` |
| Agent | `agent/main.py` | LangGraph ReAct agent — 10 tools, Gemini 2.5 Flash (Vertex AI) |
| Data | `data/db.py` | PostgreSQL helpers — invoice CRUD, profile upsert, RAG schema, RLS |
| Legacy UI | `app/` | Streamlit views — **do not delete until confirmed no longer needed** |

> `api/main.py` mocks Streamlit at startup because `app/` code still has residual Streamlit imports. Do not remove `app/` or Streamlit from `requirements.txt` without cleaning those imports first.

## Do Not
- Commit `.env` (it is in .gitignore)
- Use pytesseract — use Claude Vision for OCR instead
- Add features beyond the current week's scope
- Remove `app/` or Streamlit dependencies without explicit confirmation

## Coding Standards & Library Versions
- **Models:** ALWAYS use `gemini-2.5-flash` or newer. Never use `gemini-1.5-flash` as it is deprecated and will cause 404 errors.
- **Google AI:** Use `langchain-google-vertexai` package. Import `ChatVertexAI` from `langchain_google_vertexai`. Auth via `GCP_SERVICE_ACCOUNT_JSON` + `GCP_PROJECT_ID` — NEVER use `GOOGLE_API_KEY` or `ChatGoogleGenerativeAI`.
- **LangChain:** ALWAYS import Tools from `langchain_core.tools` (e.g., `from langchain_core.tools import Tool`). Do NOT use `langchain.tools`.
- **Agents:** Avoid deprecated LangChain agent methods. Use current LangGraph or up-to-date `langchain.agents` patterns.
- **Dependencies:** When generating `requirements.txt`, always assume the latest versions of packages for the current year (2026).

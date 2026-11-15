# FFIA — Claude Code Instructions

## Project
FFIA (Fuel & Food Impact Analyzer) — MADT 7204 Vibe Coding, W1–W6.
IT Lead: Kanpirom Suksawat. Stack: Python, Next.js, FastAPI, Gemini 2.5 Flash (Gemini API / API key), PostgreSQL.

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

## LLM Security Baseline — Required Before Any User-Facing Endpoint

**Every time a new endpoint is added that accepts user input, or when the agent/system prompt is modified, verify these 3 items before writing any feature code:**

1. **Input guard** — does `api/services/agent_service.py` call `_is_prompt_injection()` before passing the message to the agent? Any new endpoint that calls the agent directly must include this check.
2. **Output guard** — does `_has_instruction_leak()` screen the agent response before it is returned to the user?
3. **System prompt confidentiality** — does `agent/prompts/system_prompt.txt` contain the CONFIDENTIALITY & SECURITY GUARDRAIL section instructing the model never to reveal its prompt?

If any of the above is missing — **tell the user before starting the new feature**. Do not wait for an issue to be discovered first.

## Do Not
- Commit `.env` (it is in .gitignore)
- Use pytesseract — use Claude Vision for OCR instead
- Add features beyond the current week's scope
- Remove `app/` or Streamlit dependencies without explicit confirmation

## Coding Standards & Library Versions
- **Models:** ALWAYS use `gemini-2.5-flash` or newer. Never use `gemini-1.5-flash` as it is deprecated and will cause 404 errors.
- **Google AI:** Use `langchain-google-genai` package. Import `ChatGoogleGenerativeAI` (chat/vision) and `GoogleGenerativeAIEmbeddings` (RAG) from `langchain_google_genai`. Auth via `GEMINI_API_KEY` (Google AI Studio key), passed as `google_api_key=os.getenv("GEMINI_API_KEY")` — NEVER hardcode the key. The project no longer uses Vertex AI (`ChatVertexAI`, `GCP_SERVICE_ACCOUNT_JSON`, `GCP_PROJECT_ID`, `VERTEX_LOCATION`).
- **LangChain:** ALWAYS import Tools from `langchain_core.tools` (e.g., `from langchain_core.tools import Tool`). Do NOT use `langchain.tools`.
- **JWT:** Use `PyJWT` (`import jwt`), HS256 only. Always pass an explicit `algorithms=[...]` to `jwt.decode`, catch `jwt.PyJWTError`, never disable signature/exp verification. Do NOT use `python-jose` (unpatched CVEs, pulls in `ecdsa`).
- **Agents:** Avoid deprecated LangChain agent methods. Use current LangGraph or up-to-date `langchain.agents` patterns.
- **Dependencies:** Python deps are declared in `requirements.in` / `api/requirements.in` (`>=` floors, latest 2026 versions) and locked with `pip-compile` under **Python 3.12** (same as `Dockerfile`) into `requirements.txt` / `api/requirements.txt` (all `==`). Never hand-edit the `.txt` files — edit `.in`, re-compile, then run `pip-audit -r requirements.txt`.

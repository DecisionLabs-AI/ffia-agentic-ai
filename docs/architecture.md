# FFIA — Project Context & Agent Architecture

> Status: **W4 Complete** — App modularized into `app/views/` + `app/components/`. New tools: ingredient price, platform GP lookup, RAG vector search. 3-step Business Setup stepper. Invoice delete UI. Vertex AI auth (service account) replaces API key auth. GraphRecursionError graceful fallback shipped.

---

## Business Context

FFIA (Fuel & Food Impact Analyzer) is an AI-powered decision support tool for Bangkok restaurant owners. It connects real-time oil price movements to menu cost structures, helping operators understand how fuel and ingredient costs affect their margins — without needing a data analyst.

**Target users:** Restaurant owners and operators in Bangkok who manage food costs manually and lack visibility into how commodity price swings affect menu profitability.

**Problems it solves:**
- **Cost increase analysis** — quantify the impact of oil/fuel price changes on ingredient and delivery costs
- **Menu risk detection** — flag which menu items are most exposed to cost volatility
- **Pricing recommendations** — suggest adjusted menu prices to protect target margins

---

## Data & Business Logic Source

All business logic, data definitions, and scenario rules are maintained as living documents in the `docs/` folder:

| Document | Purpose |
|---|---|
| `docs/data_definition.md` | Schema definitions, field meanings, data types, and acceptable value ranges |
| `docs/business_rules.md` | Margin calculation formulas, cost allocation logic, and pricing thresholds |
| `docs/scenarios.md` | Pre-defined what-if scenarios used by the simulation tool |
| `docs/demo_script.md` | Guided demo flow — sample questions, expected agent responses, and presenter notes |

→ These documents are the **single source of truth** for all system logic. When implementing tools or agent behavior, defer to these files — not assumptions or LLM defaults.

---

## AI Development & Prompt Rules

Rules that apply when generating code, prompts, or agent logic for this project:

- **Always apply the Style Guide Prompt** before generating or modifying any code — consistency matters across weeks
- **Do not hallucinate libraries or functions** — only use packages present in `requirements.txt` or explicitly approved
- **Validate all inputs** — check type, range, and empty/null before passing to tools or queries
- **Explain before fixing** — when diagnosing an error, describe the root cause first, then apply the fix
- **Use deterministic logic in tools** — tools must return consistent outputs for the same inputs; no randomness or LLM calls inside tools
- **Security first** — all secrets via `.env` only; never hardcode credentials or connection strings
- **Model pinning** — always use `gemini-2.5-flash` or newer; `gemini-1.5-flash` is deprecated and causes 404 errors

---

## Team Responsibility Model

| Role | Responsibilities |
|---|---|
| **Business Team** | Define data schemas (`data_definition.md`), business rules (`business_rules.md`), simulation scenarios (`scenarios.md`), and demo flow (`demo_script.md`) |
| **IT Lead (Kanpirom)** | Implement agent tools, wire LangGraph agent, integrate database and UI, and ensure system behavior matches business-defined rules |

The business team owns the *what* — the IT Lead owns the *how*. Implementation decisions that affect business logic must be validated against `docs/business_rules.md` before merging.

---

## System Design Philosophy

FFIA uses a **single-agent, multi-tool architecture**:

- **Agent** (`agent/main.py`) — orchestrates reasoning via a LangGraph ReAct loop; decides which tools to call, interprets observations, and generates final recommendations in natural language
- **Tools** (`agent/tools/`) — handle all deterministic logic (SQL queries, margin calculations, scenario simulation); tools never call the LLM and always return structured, predictable outputs
- **Separation of concerns** — the agent reasons, tools compute; this keeps the LLM focused on language and intent while tools guarantee correctness for numeric and data operations

This design makes the system easier to test (tools are pure functions), easier to debug (reasoning traces are captured per step), and easier to extend (new tools can be added without changing agent logic).

---

## High-Level Architecture

```
User (Streamlit — dark sidebar)
        │
        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  app/main.py  (bootstrap: auth wall, CSS inject, sidebar, router)    │
│  app/views/dashboard.py   app/views/profile.py   app/views/upload.py │
│  app/views/chat.py        app/components/layout.py + sidebar.py      │
│  Auth: FFIA_AUTH_USERS_JSON (PBKDF2)                                 │
│  OCR:  app/utils/ocr.py — Claude Vision invoice extraction           │
└────────────┬──────────────────────────────┬─────────────────────────┘
             │ run_agent()                  │ data/db.py
             ▼                              ▼
┌────────────────────────┐   ┌──────────────────────────────────────┐
│      agent/main.py     │   │            data/db.py                │
│  LangGraph ReAct Agent │   │  psycopg2 CRUD helpers               │
│  Gemini 2.5 Flash      │   │  invoices, invoice_items,            │
│  Vertex AI (SvcAcct)   │   │  restaurant_profiles,                │
│  Thought→Action→Obs    │   │  ingredient_market_prices,           │
│  recursion_limit=9     │   │  invoice_embeddings (pgvector)       │
└──┬──┬──┬──┬──┬──┬──┬───┘  └──────────────┬───────────────────────┘
   │  │  │  │  │  │  │                       │
   ▼  ▼  ▼  ▼  ▼  ▼  ▼                       ▼
postgres_tool          rag_tool         PostgreSQL (Supabase)
oil_price_tool         search_tool      Row-Level Security (RLS)
ingredient_price_tool                   per user_id tenant
platform_gp_lookup_tool                 pgvector extension (RAG)
business_rules_tool (×4)
```

---

## Components

### 1. LLM Core
- **Model**: Gemini 2.5 Flash via `ChatVertexAI` (`langchain-google-vertexai`)
- **Framework**: LangGraph `create_react_agent` — ReAct (Reason + Act) loop
- **Location**: `agent/main.py`
- **Auth**: GCP service account — `GCP_SERVICE_ACCOUNT_JSON` (Streamlit Cloud) or `GOOGLE_APPLICATION_CREDENTIALS` (local dev) + `GCP_PROJECT_ID`
- **Temperature**: 0 (deterministic for data analysis)
- **Recursion limit**: 9 steps per turn (configurable in `run_agent()` config)

### 2. Tools
| Tool | File | Description |
|---|---|---|
| `oil_price_tool` | `agent/tools/oil_price_tool.py` | Live diesel/gasohol prices from Bangchak API; Thai and English fuel-name aliases; returns price + effective date |
| `postgres_tool` | `agent/tools/postgres_tool.py` | SELECT queries against PostgreSQL; RLS enforced via `app.current_user_id` session config |
| `ingredient_price_tool` | `agent/tools/ingredient_price_tool.py` | Ingredient market price lookup from `ingredient_market_prices` PostgreSQL table |
| `platform_gp_lookup_tool` | `agent/tools/platform_gp_lookup_tool.py` | Returns gross profit % per delivery platform from the `platform_fee` table |
| `rag_tool` | `agent/tools/rag_tool.py` | pgvector similarity search over `invoice_embeddings` — retrieves relevant invoice context |
| `platform_floor_guard_tool` | `agent/tools/business_rules_tool.py` | Rule L1 — platform cost floor check; classifies as HEALTHY/WATCH/WARNING/CRITICAL |
| `promo_profitability_tool` | `agent/tools/business_rules_tool.py` | Rule L3 — promo viability check; computes minimum viable price + psychological pricing |
| `cogs_alert_tool` | `agent/tools/business_rules_tool.py` | Rule L4 — COGS impact alert with cuisine-group substitute ingredient map |
| `scenario_classifier_tool` | `agent/tools/business_rules_tool.py` | Classifies business situation into Scenario 1/2/3 and returns an action plan |
| `search_tool` | `agent/tools/search_tool.py` | Web search via DuckDuckGo — no API key required; fallback for general queries |

**Security guardrails on PostgreSQL tool:**
- Only `SELECT` statements accepted — mutations rejected at tool level
- Results capped at 50 rows to control LLM context size
- Row-Level Security (RLS) enforced at the database layer — each query is tenant-scoped to the authenticated `user_id`

**Business-rule tools source of truth:**
- `platform_floor_guard_tool`, `promo_profitability_tool`, `cogs_alert_tool` → `docs/business_rules.md` (Rules L1, L3, L4)
- `scenario_classifier_tool` → `docs/scenarios.md` (Scenario 1/2/3 selection logic)

### 3. Prompts
- **System prompt**: `agent/prompts/system_prompt.txt` — defines FFIA role, available tools, Bangkok/THB context, output format
- **Tool descriptions**: docstrings on each `@tool` function — LangGraph reads these to decide when to call each tool

### 4. Data Layer
- **PostgreSQL**: Cloud-hosted (Supabase) — primary data source
- Connection via `DATABASE_URL` in `.env`; helpers in `data/db.py` (psycopg2, no ORM)
- **Row-Level Security**: `_apply_user_context(conn, user_id)` sets `app.current_user_id` PostgreSQL session variable; RLS policies enforce per-tenant isolation on all tables
- **Tables managed by `data/db.py`**:
  - `invoices` — invoice header records per user
  - `invoice_items` — line items linked to each invoice
  - `restaurant_profiles` — restaurant context and margin thresholds per user
  - `restaurant_channel_mix` — per-platform revenue share and GP % per user
  - `ingredient_market_prices` — reference ingredient prices (seeded from CSV)
  - `invoice_embeddings` — pgvector embeddings of invoice chunks for RAG retrieval

### 5. Authentication
- **Source**: `FFIA_AUTH_USERS_JSON` env var — JSON array of users with pre-hashed passwords
- **Verification**: PBKDF2-SHA256 (390,000 iterations) via `app/utils/auth.py`
- **Session**: `st.session_state["auth_user"]` — contains `user_id`, `username`, `display_name`
- `user_id` doubles as the PostgreSQL tenant identifier for RLS

### 6. User Interface
- **Framework**: Streamlit — modularized into views and components
- **Entry point**: `app/main.py` — bootstrap only (auth wall, CSS injection, sidebar, page router)
- **Views** (`app/views/`):
  - `chat.py` — AI Assistant chat with reasoning trace expander and prompt chips
  - `dashboard.py` — Decision cards, Quick Actions, current-month invoice list
  - `profile.py` — Business Setup 3-step stepper (profile form → invoice upload → readiness review)
  - `upload.py` — OCR invoice ingestion (Claude Vision) → editable form → PostgreSQL save + delete
- **Components** (`app/components/`):
  - `layout.py` — `_render_page_hero()`, `_render_section_header()`, `_load_logo_b64()`
  - `sidebar.py` — `_render_sidebar()`, `_render_sidebar_nav_button()`
- **Styles**: `app/styles/main_css.py` — global CSS theme injected via `st.markdown()`
- **Sidebar**: Dark navy (`#0f172a`) with active/inactive CSS states, bottom-pinned account block
- **Reasoning Transparency**: `st.expander` collapsed by default; shows tool name + observation per step

---

## Key Files

| File | Purpose |
|---|---|
| `agent/main.py` | LangGraph agent setup, `run_agent()` public function, `_extract_text()` Gemini content normalizer |
| `agent/tools/oil_price_tool.py` | Live oil price from Bangchak API — Thai/English aliases, date fields |
| `agent/tools/business_rules_tool.py` | Business-rule tools: L1 platform floor guard, L3 promo profitability, L4 COGS alert, scenario classifier |
| `agent/tools/postgres_tool.py` | PostgreSQL SELECT tool for agent — RLS-enforced, 50-row cap |
| `agent/tools/ingredient_price_tool.py` | Ingredient market price lookup from PostgreSQL reference table |
| `agent/tools/platform_gp_lookup_tool.py` | Per-platform GP % lookup from `platform_fee` table |
| `agent/tools/rag_tool.py` | pgvector invoice embedding similarity search |
| `agent/tools/search_tool.py` | DuckDuckGo web search tool |
| `agent/prompts/system_prompt.txt` | Agent role, tool guidance, Bangkok/THB context, output format |
| `app/main.py` | Streamlit bootstrap — auth wall, CSS injection, DB setup, sidebar render, page router |
| `app/views/chat.py` | AI Assistant chat page — prompt chips, agent turn, reasoning trace |
| `app/views/dashboard.py` | Dashboard page — decision cards, Quick Actions, invoice list |
| `app/views/profile.py` | Business Setup 3-step stepper — profile form, upload, readiness review |
| `app/views/upload.py` | Data Upload page — OCR ingestion, invoice form, save/delete |
| `app/components/layout.py` | Shared page hero, section header, logo loader |
| `app/components/sidebar.py` | Sidebar nav and brand block |
| `app/styles/main_css.py` | Global CSS theme string |
| `app/utils/auth.py` | User authentication — PBKDF2 password verification, session helpers |
| `app/utils/ocr.py` | Claude Vision OCR — extracts invoice fields and line items from uploaded images |
| `data/db.py` | PostgreSQL helpers — invoice CRUD, profile upsert/fetch, RAG schema, RLS context setup |
| `requirements.txt` | Python dependencies |
| `.env` | Secrets — never committed (see `.env.example`) |

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection URL (`postgresql://user:pass@host:5432/db`) |
| `FFIA_AUTH_USERS_JSON` | Yes | JSON array of users with `username`, `display_name`, `password_hash` |
| `GCP_PROJECT_ID` | Yes | GCP project ID — required by Vertex AI for both agent LLM and invoice OCR |
| `GCP_SERVICE_ACCOUNT_JSON` | Yes | Full service account key JSON (single-line string) — used by agent and OCR on Streamlit Cloud |
| `GOOGLE_APPLICATION_CREDENTIALS` | Local dev | Path to GCP key JSON file — used when `GCP_SERVICE_ACCOUNT_JSON` is not set |

---

## run_agent() Contract

```python
run_agent(
    user_message: str,
    chat_history: list = None,
    callbacks: list = None,
    current_user_id: str | None = None,
) -> dict
```

Returns:
```python
{
    "output": str,                          # Final answer — plain string
    "intermediate_steps": [                 # Tool calls made during reasoning
        ("tool_name", "observation_text"),  # One tuple per tool invocation
        ...
    ]
}
```

`_extract_text()` normalizes Gemini 2.5 Flash's content block format (`[{'type':'text','text':'...'}]`) to a plain string before returning.

---

## Security Boundaries
- All secrets loaded from `.env` via `python-dotenv` — never hardcoded
- GCP service account credentials loaded from `GCP_SERVICE_ACCOUNT_JSON` env var (Streamlit Cloud) or `GOOGLE_APPLICATION_CREDENTIALS` file path (local dev)
- PostgreSQL tool rejects any non-SELECT SQL at the tool level
- Query results capped at 50 rows before passing to LLM
- Row-Level Security enforced at DB layer — `set_postgres_tool_user_id()` / `reset_postgres_tool_user_id()` bracket every agent invocation

---

## Completed Milestones

| Week | Deliverable |
|---|---|
| W1 | LangGraph ReAct agent, Gemini 2.5 Flash, DuckDuckGo search tool, dark sidebar UI |
| W2 | PostgreSQL integration, invoice CRUD (`data/db.py`), RLS tenant isolation, user authentication |
| W3 | Bangchak oil price tool, 4 business-rule tools (L1/L3/L4/Scenario Classifier), OCR invoice upload (Claude Vision), Data Upload page, Business Profile Settings page, platform channel assets |
| W4 | App modularized into `app/views/` + `app/components/` + `app/styles/`; ingredient price tool; platform GP lookup tool; RAG vector search tool (`rag_tool.py`); `invoice_embeddings` table with pgvector; 3-step Business Setup stepper; invoice delete UI; Vertex AI service account auth |

## Planned Next
- [x] `GraphRecursionError` graceful UI fallback — `app/views/chat.py` surfaces user-friendly Thai message
- [ ] `calculate_margin` tool — compute true net margin per menu item using invoice and profile data
- [ ] `simulate_scenario` tool — what-if oil price sensitivity analysis
- [ ] Multi-agent: Planner → Data Agent + Margin Agent + Recommendation Agent

---

*Last updated: W4 complete — UI modularized into views/components, RAG tool, ingredient price tool, platform GP lookup, 3-step stepper, invoice delete, Vertex AI auth, GraphRecursionError graceful fallback.*

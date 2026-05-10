# FFIA - Current Architecture

> Status: submission-ready MVP/prototype. The active product path is
> Next.js + FastAPI + LangGraph ReAct + PostgreSQL/Supabase. The legacy
> Streamlit app remains in the repository but is not the current primary
> deployed path.

---

## Business Context

FFIA (Fuel & Food Impact Analyzer) helps Bangkok restaurant owners connect
fuel prices, delivery platform fees, promotions, and actual invoice costs to
pricing and margin decisions.

The MVP is designed around a practical owner workflow:

1. Log in.
2. Set up restaurant profile and channel mix.
3. Upload an invoice image.
4. Review and edit OCR-extracted invoice data.
5. Save invoice data to PostgreSQL.
6. Inspect dashboard cost summary and top spend items.
7. Ask the AI Assistant for profile, platform, promo, oil price, or cost-risk analysis.

---

## Active Deployed Structure

| Layer | Technology | Active files |
|---|---|---|
| Frontend | Next.js | `frontend/app/*`, `frontend/components/*`, `frontend/lib/api.ts` |
| Backend API | FastAPI | `api/main.py`, `api/routes/*`, `api/services/*` |
| Agent | LangGraph ReAct | `agent/main.py` |
| LLM | Vertex AI `ChatVertexAI` / Gemini | `FFIA_AGENT_MODEL`, `VERTEX_LOCATION`, `GCP_PROJECT_ID` |
| Database | PostgreSQL/Supabase | `data/db.py`, `DATABASE_URL` |
| Deployment target | Vercel + Cloud Run | Vercel frontend, Cloud Run backend |
| Legacy app | Streamlit | `app/` exists but is not the active primary product path |

---

## Active Request Flow

```text
User
  |
  v
Next.js frontend
  - login
  - dashboard
  - business setup
  - OCR upload/review
  - cost data
  - AI chat
  |
  v
FastAPI backend
  - /health
  - /login
  - /chat
  - /dashboard-summary
  - /business-setup
  - /invoices/*
  |
  v
agent.main.run_agent()
  |
  v
LangGraph ReAct agent
  |
  +--> postgres_tool -------------> PostgreSQL/Supabase
  +--> ingredient_price_tool -----> PostgreSQL/Supabase
  +--> oil_price_tool ------------> Bangchak Oil Price API
  +--> search_tool ---------------> restricted web search fallback
  +--> business rule tools -------> deterministic Python calculations
  |
  v
FastAPI response
  - answer
  - lightweight tool-observation trace
  |
  v
Next.js chat UI
```

---

## Frontend Architecture

The active UI is the Next.js app in `frontend/`.

| Feature | Files | Current status |
|---|---|---|
| Login | `frontend/app/login/page.tsx`, `frontend/lib/auth.ts` | Sandbox login stores user context in localStorage |
| App shell / nav | `frontend/components/AppShell.tsx`, `frontend/components/Sidebar.tsx` | Active |
| Dashboard | `frontend/app/dashboard/page.tsx` | Uses `/dashboard-summary` |
| Business setup | `frontend/app/setup/page.tsx`, `frontend/components/setup/*` | Saves profile/channel mix via `/business-setup` |
| OCR upload/review | `frontend/components/setup/InvoiceUploadStep.tsx`, `frontend/app/upload/page.tsx` | Preview, edit, save via `/invoices/*` |
| Cost data | `frontend/app/cost-data/page.tsx` | Invoice item review and exclusion |
| AI Assistant | `frontend/app/chat/page.tsx` | Markdown rendering, loading animation, auto-scroll, trace details |

Frontend environment variables:

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI backend origin |
| `NEXT_PUBLIC_API_URL` | Backward-compatible API base fallback |
| `NEXT_PUBLIC_API_TIMEOUT_MS` | Generic API timeout |
| `NEXT_PUBLIC_CHAT_TIMEOUT_MS` | Chat timeout; `180000` recommended for production |

---

## Backend Architecture

The active backend is `api/main.py`, which registers sandbox routes used by the
current Next.js frontend.

| Route | File | Purpose |
|---|---|---|
| `GET /health` | `api/routes/health.py` | Health check |
| `POST /login` | `api/routes/login.py`, `api/services/auth_service.py` | Sandbox login |
| `POST /chat` | `api/routes/chat.py`, `api/services/agent_service.py` | Calls `agent.main.run_agent()` |
| `GET /dashboard-summary` | `api/routes/dashboard.py`, `api/services/dashboard_service.py` | Dashboard snapshot |
| `/business-setup` | `api/routes/business_setup.py` | Profile/channel mix load and save |
| `/invoices/*` | `api/routes/invoices.py` | OCR preview, reviewed save, invoice list/items, exclusion, delete |

Legacy authenticated routers under `api/routers/` still exist and are registered
when imports succeed, but the current Next.js frontend uses the sandbox routes
above.

Backend environment variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL/Supabase connection |
| `ENVIRONMENT` | Runtime mode; `production` on Cloud Run |
| `JWT_SECRET` | Required in production |
| `FFIA_AUTH_USERS_JSON` | Login users with PBKDF2 password hashes |
| `GCP_PROJECT_ID` | Vertex AI project |
| `GCP_SERVICE_ACCOUNT_JSON` | Inline service account JSON or omit when using Cloud Run service account |
| `VERTEX_LOCATION` | Vertex AI region |
| `FFIA_AGENT_MODEL` | Gemini model name |
| `CORS_ORIGINS` | Allowed frontend origins |
| `FFIA_AGENT_TIMEOUT_SECONDS` | Agent service timeout; `150` recommended |

---

## Agent Architecture

`agent/main.py` builds a lazy singleton LangGraph ReAct agent using
`create_react_agent(...)` and `ChatVertexAI`.

Key behavior:

- System prompt is loaded from `agent/prompts/system_prompt.txt`.
- Chat history is accepted and reduced to the latest turns.
- `current_user_id` is bound to `postgres_tool` through a ContextVar.
- Invoice questions may receive latest invoice context from `data.db.get_latest_invoice()`.
- Profile/risk questions may receive latest restaurant profile context from
  `data.db.fetch_latest_restaurant_profile()`.
- The public contract is `run_agent(...) -> {"output": str, "intermediate_steps": [...]}`.

### Active Registered Tools

These tools are actually registered in `agent/main.py` and reachable from the
AI Assistant chat flow.

| Tool | File | Current role | Depends on |
|---|---|---|---|
| `postgres_tool` | `agent/tools/postgres_tool.py` | SELECT-only PostgreSQL queries with tenant context | `DATABASE_URL`, current user |
| `search_tool` | `agent/tools/search_tool.py` | Restricted search fallback | `ddgs` or `TAVILY_API_KEY` |
| `oil_price_tool` | `agent/tools/oil_price_tool.py` | Live fuel price lookup | Bangchak API |
| `ingredient_price_tool` | `agent/tools/ingredient_price_tool.py` | Reference ingredient price lookup | `ingredient_market_prices` |
| `platform_floor_guard_tool` | `agent/tools/business_rules_tool.py` | Partial L1 platform floor calculation | LLM/tool inputs |
| `promo_profitability_tool` | `agent/tools/business_rules_tool.py` | Partial L3 promo viability calculation | LLM/tool inputs |
| `cogs_alert_tool` | `agent/tools/business_rules_tool.py` | Partial L4 COGS impact calculation | LLM/tool inputs |
| `scenario_classifier_tool` | `agent/tools/business_rules_tool.py` | Scenario 1/2/3 helper | LLM/tool inputs |

### Exists But Not Wired

These files/capabilities exist but are not active product features:

| Item | Current status |
|---|---|
| `agent/tools/rag_tool.py` | Exists, but `rag_cost_history_tool` is not registered in `agent/main.py` |
| `invoice_embeddings` | Schema helper exists in `data/db.py`, but indexing/retrieval is not wired into upload/save/chat |
| `agent/tools/platform_gp_lookup_tool.py` | Exists and has tests, but is not registered in the active agent |
| `ingredient_aliases` / `ingredient_matching_template.csv` | Seed path exists, but product lookup does not use aliases |
| `pg_trgm` fuzzy matching | Not implemented |
| Fuzzy ingredient search | Not implemented |
| Deterministic menu margin calculator | Planned future tool |
| L2 Cross-Platform Margin Arbitrage | Documented only |
| L5 Dynamic Delivery Radius Control | Documented only |

Do not demo these as active features.

---

## Data Layer

PostgreSQL/Supabase is the main data source and the single source of truth for
restaurant profile, channel mix, invoice, and invoice item data.

| Table | Current product usage |
|---|---|
| `restaurant_profiles` | Business setup, dashboard profile snapshot, agent profile context |
| `restaurant_channel_mix` | Business setup, dashboard channel mix, agent SQL context |
| `invoices` | OCR save/list/dashboard/agent latest invoice context |
| `invoice_items` | OCR save/list/top spend/exclusion/agent SQL context |
| `ingredient_market_prices` | `ingredient_price_tool` lookup |
| `platform_fee` | Global reference table; queryable through `postgres_tool`; dedicated lookup tool is not registered |
| `invoice_embeddings` | Future RAG schema only; not wired |
| `ingredient_aliases` | Future fuzzy/alias matching only; not wired |

Tenant handling:

- `data.db.get_connection(user_id)` sets `app.current_user_id`.
- Invoice helpers require `user_id`.
- `postgres_tool` replaces the literal `'current_user_placeholder'` with the
  current authenticated user.
- `invoice_items.excluded_from_analysis` is used by dashboard/top spend and
  agent SQL guidance to omit non-business items by default.

---

## OCR / Invoice Flow

```text
User uploads image
  -> frontend/components/setup/InvoiceUploadStep.tsx
  -> POST /invoices/ocr-preview
  -> app/utils/ocr.py::extract_invoice_data()
  -> editable review state in React
  -> POST /invoices/save
  -> data.db.save_invoice()
  -> dashboard / invoice list / cost-data page
```

Current status:

- OCR extraction uses Gemini Vision through `ChatVertexAI`.
- Header fields are editable before save.
- Line items are editable before save.
- Edited values are saved through the current save payload.
- Saved invoice items can be excluded/restored from analysis.
- OCR confidence confirmation is documented in business rules but not
  implemented as a confidence-driven product flow.

---

## Business Rules Status

| Rule | Current implementation |
|---|---|
| L1 Platform Cost Floor Guard | Partially implemented as `platform_floor_guard_tool`; active agent can call it when inputs are available |
| L2 Cross-Platform Margin Arbitrage | Documented only; not implemented as tool or product flow |
| L3 Promo Profitability Guard | Partially implemented as `promo_profitability_tool`; active agent has prompt/input guidance |
| L4 Raw Material COGS Alert | Partially implemented as `cogs_alert_tool`; simplified assumptions |
| L5 Dynamic Delivery Radius Control | Documented only; not implemented as tool or product flow |
| Scenario 1/2/3 classifier | Implemented as helper tool; depends on supplied/derived inputs |

Business-rule tools are useful for MVP guidance, but they are not a complete
deterministic margin engine.

---

## Reasoning Trace / Auditability

The AI Assistant exposes lightweight trace details:

- Tool name
- Tool observation text
- Any returned error marker

This is not hidden chain-of-thought. It is an audit-friendly summary of
observable tool calls and data sources. The agent prompt also asks for a short
data-source footer in answers, but exact footer quality depends on the LLM turn.

Current status: partial but demoable.

Future auditability improvements:

- Persist traces server-side.
- Add structured source tags per answer.
- Add deterministic calculator outputs for menu margin and scenarios.

---

## Timeout / Reliability Notes

Chat requests can take longer than ordinary API requests because the agent may
call external APIs, PostgreSQL, and multiple tools.

Recommended production settings:

| Layer | Recommended timeout |
|---|---|
| Frontend chat timeout | `NEXT_PUBLIC_CHAT_TIMEOUT_MS=180000` |
| Backend agent timeout | `FFIA_AGENT_TIMEOUT_SECONDS=150` |
| Cloud Run request timeout | `300s` |

Rule: frontend timeout should exceed backend agent timeout so users receive the
backend's graceful timeout message instead of a browser-side abort.

Known reliability considerations:

- Bangchak API/network failures are handled as tool errors or null dashboard oil data.
- Database failures return user-friendly dashboard/API errors where implemented.
- Long or broad agent questions may hit recursion/timeout limits.
- RAG/fuzzy matching should not be included in reliability claims because those
  paths are not wired into the product flow.

---

## Key Files

| File | Purpose |
|---|---|
| `frontend/lib/api.ts` | Frontend API client and timeouts |
| `frontend/app/chat/page.tsx` | AI Assistant UI, markdown rendering, loading animation, auto-scroll, trace details |
| `frontend/components/setup/InvoiceUploadStep.tsx` | OCR upload, editable review, save, invoice list |
| `frontend/app/cost-data/page.tsx` | Invoice item review and exclusion |
| `api/main.py` | FastAPI app and route registration |
| `api/routes/chat.py` | Active chat route |
| `api/services/agent_service.py` | Agent timeout, DB-first routing hint, `run_agent()` adapter |
| `api/services/dashboard_service.py` | Dashboard summary aggregation |
| `api/routes/invoices.py` | Active OCR/invoice endpoints |
| `agent/main.py` | LangGraph ReAct setup and `run_agent()` |
| `agent/tools/postgres_tool.py` | Tenant-aware SELECT-only SQL tool |
| `agent/tools/business_rules_tool.py` | Partial L1/L3/L4/scenario tools |
| `app/utils/ocr.py` | Gemini Vision OCR extraction |
| `data/db.py` | PostgreSQL helpers |

---

## Planned Future Implementation

- Wire RAG indexing after invoice save and register `rag_cost_history_tool`.
- Add fuzzy ingredient matching using aliases and/or `pg_trgm`.
- Register or replace `platform_gp_lookup_tool` with deterministic platform fee resolution.
- Add deterministic menu margin calculator tool.
- Add L2 Cross-Platform Margin Arbitrage tool.
- Add L5 Dynamic Delivery Radius Control tool.
- Add checked-in Cloud Run deployment artifacts such as `Dockerfile` or `cloudbuild.yaml`.
- Persist reasoning/audit traces for post-hoc review.

---

*Last updated for submission: active Next.js + FastAPI product path, registered agent tools only, RAG/fuzzy/L2/L5 clearly marked as future work.*

# FFIA - Fuel & Food Impact Analyzer

> **MADT 7204 Vibe Coding Project** | Team 2 | Bangkok Oil Price Crisis

FFIA is a deployed prototype for Bangkok restaurant owners. It combines a
Next.js frontend, FastAPI backend, PostgreSQL/Supabase data layer, and a
LangGraph ReAct AI agent powered by Vertex AI Gemini. The goal is to help
restaurant operators understand how fuel prices, delivery platform fees,
promotions, and invoice costs affect margin decisions.

The current active product path is:

```text
User -> Next.js frontend -> FastAPI backend -> LangGraph ReAct agent
     -> registered tools -> PostgreSQL / external APIs -> response + trace
```

The legacy Streamlit app still exists in `app/`, but it is no longer the
primary deployed product path.

---

## Team

| Role | Name |
|---|---|
| IT Lead | Kanpirom Suksawat |
| Mgmt Member | Pornphrom Rujiwatchara-oran |
| Mgmt Member | Anantaporn Lapsakkarn |
| Mgmt Member | Jantana Pattarapronpisit |
| Mgmt Member | Rapeepat Rattanapachai |

---

## Problem Statement

Oil price movement in Thailand affects restaurants beyond direct cooking fuel:

- Fuel and logistics costs are embedded in supplier pricing and delivery fees.
- Platform GP/commission can erase margin before ingredient cost is counted.
- Promotions can increase sales while destroying profit if break-even math is not checked.
- Restaurant owners often lack a single place to connect invoices, channel mix,
  fuel prices, and pricing decisions.

FFIA gives owners a practical AI assistant and dashboard for cost visibility,
invoice review, and decision support.

---

## Current Implementation Status

| Area | Current status |
|---|---|
| Frontend | Next.js app in `frontend/` |
| Backend | FastAPI app in `api/` |
| Agent | LangGraph ReAct agent in `agent/main.py` |
| LLM | Vertex AI `ChatVertexAI`, model from `FFIA_AGENT_MODEL`, region from `VERTEX_LOCATION` |
| Database | PostgreSQL/Supabase via `DATABASE_URL`; single source of truth for invoice/profile/channel data |
| Deployment target | Vercel frontend + Cloud Run backend |
| Legacy app | Streamlit code remains in `app/`, but is not the primary deployed path |

### Active FastAPI Routes

| Route | Purpose |
|---|---|
| `GET /health` | Backend health check |
| `POST /login` | Sandbox login using `FFIA_AUTH_USERS_JSON` |
| `POST /chat` | AI Assistant endpoint |
| `GET /dashboard-summary` | Dashboard snapshot |
| `GET /business-setup` / `POST /business-setup` | Business profile and channel mix load/save |
| `/invoices/*` | OCR preview, reviewed save, invoice list, item list, item exclusion, invoice delete |

---

## Current Demo Scope

The following capabilities are working and suitable for the final demo when
environment variables and database connectivity are configured:

| Feature | Status | Main files |
|---|---|---|
| Sandbox login | Demo-ready | `frontend/app/login/page.tsx`, `api/routes/login.py`, `api/services/auth_service.py` |
| Dashboard summary | Demo-ready | `frontend/app/dashboard/page.tsx`, `api/services/dashboard_service.py` |
| Business setup save/load | Demo-ready | `frontend/app/setup/page.tsx`, `api/routes/business_setup.py`, `data/db.py` |
| OCR invoice preview | Demo-ready | `frontend/components/setup/InvoiceUploadStep.tsx`, `api/routes/invoices.py`, `app/utils/ocr.py` |
| OCR review/edit/save | Demo-ready | `frontend/components/setup/InvoiceUploadStep.tsx`, `data/db.py::save_invoice` |
| Invoice listing / top spend | Demo-ready | `frontend/app/dashboard/page.tsx`, `frontend/app/cost-data/page.tsx` |
| Exclude item from analysis | Demo-ready | `frontend/app/cost-data/page.tsx`, `api/routes/invoices.py`, `data/db.py::toggle_item_exclusion` |
| AI Assistant chat | Demo-ready | `frontend/app/chat/page.tsx`, `api/routes/chat.py`, `api/services/agent_service.py` |
| Markdown assistant output | Demo-ready | `frontend/app/chat/page.tsx` |
| Loading animation / auto-scroll | Demo-ready | `frontend/app/chat/page.tsx` |
| Lightweight reasoning trace | Partial but demoable | Chat UI shows tool observations returned by the backend |

### Partially Implemented / Prompt-Guided

These are usable in controlled demos but should be presented as MVP decision
support rather than deterministic production calculators:

- AI profile risk routing
- AI platform/delivery analysis
- AI promo profitability
- Menu margin calculation from user-provided prices/costs
- Business rule application
- Reasoning trace / auditability
- Business rules L1, L3, and L4

---

## Agent Design

The active agent is a single LangGraph ReAct agent in `agent/main.py`.

### Registered Agent Tools

Only the tools below are registered in the active `create_react_agent(...)`
tool list and reachable from `/chat`:

| Tool | File | Current role |
|---|---|---|
| `postgres_tool` | `agent/tools/postgres_tool.py` | Read-only PostgreSQL SELECT queries with tenant context |
| `search_tool` | `agent/tools/search_tool.py` | Restricted external search fallback |
| `oil_price_tool` | `agent/tools/oil_price_tool.py` | Live Bangchak fuel price lookup |
| `ingredient_price_tool` | `agent/tools/ingredient_price_tool.py` | Reference ingredient price lookup from PostgreSQL |
| `platform_floor_guard_tool` | `agent/tools/business_rules_tool.py` | Partial L1 platform floor calculation |
| `promo_profitability_tool` | `agent/tools/business_rules_tool.py` | Partial L3 promo viability calculation |
| `cogs_alert_tool` | `agent/tools/business_rules_tool.py` | Partial L4 COGS alert calculation |
| `scenario_classifier_tool` | `agent/tools/business_rules_tool.py` | Scenario 1/2/3 classification helper |

### Exists But Not Wired Into Active Product Flow

Do not present these as active product features:

| File / capability | Current status |
|---|---|
| `agent/tools/rag_tool.py` / `rag_cost_history_tool` | Exists, but not registered in `agent/main.py` and not called by chat |
| `invoice_embeddings` | Schema helper exists, but indexing/retrieval is not wired into upload/save/chat |
| `agent/tools/platform_gp_lookup_tool.py` | Exists and has tests, but is not registered in the active agent |
| `data/raw/ingredient_matching_template.csv` | Seed data exists, but product lookup does not use it |
| `pg_trgm` fuzzy matching | Not implemented |
| Fuzzy ingredient search | Not implemented; current ingredient lookup is simple `ILIKE` |
| L2 Cross-Platform Margin Arbitrage | Documented only |
| L5 Dynamic Delivery Radius Control | Documented only |
| Deterministic menu margin calculator tool | Planned future implementation |

---

## Repository Structure

```text
ffia-agentic-ai/
├── frontend/                  # Active Next.js frontend
│   ├── app/                   # Login, dashboard, setup, cost-data, chat
│   ├── components/            # App shell, sidebar, setup steps
│   └── lib/                   # API client and local auth helpers
├── api/                       # Active FastAPI backend
│   ├── main.py                # FastAPI app and route registration
│   ├── routes/                # Active sandbox routes
│   ├── routers/               # Legacy JWT routers, still present
│   └── services/              # Agent, auth, dashboard services
├── agent/
│   ├── main.py                # LangGraph ReAct agent
│   ├── prompts/               # System prompt
│   └── tools/                 # Registered and future tools
├── data/
│   ├── db.py                  # PostgreSQL helpers
│   ├── raw/                   # CSV reference data
│   └── scripts/               # One-time seed scripts
├── app/                       # Legacy Streamlit app, not primary deployed path
├── docs/                      # Architecture, business rules, scenarios, rubric
└── tests/                     # Unit and routing tests
```

---

## Data Sources

| Source | Type | Current usage |
|---|---|---|
| PostgreSQL/Supabase | Primary app data | Restaurant profiles, channel mix, invoices, invoice items, ingredient market prices |
| Bangchak Oil Price API | External API | Live fuel price via `oil_price_tool` and dashboard helper |
| `ingredient_market_prices` | Reference table | Ingredient price lookup via `ingredient_price_tool` |
| DuckDuckGo/Tavily | External search | Restricted fallback via `search_tool` |

PostgreSQL remains the single source of truth for invoice, line item, profile,
and channel-mix data.

---

## Local Setup

### 1. Backend Local Run

```bash
git clone https://github.com/DecisionLabs-AI/ffia-agentic-ai
cd ffia-agentic-ai
cp .env.example .env
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"ffia-api"}
```

### 2. Frontend Local Run

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Recommended `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_CHAT_TIMEOUT_MS=180000
```

Local URLs:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

### 3. Production Deploy Environment Variables

Deployment target:

- Frontend: Vercel
- Backend: Google Cloud Run

Frontend:

| Variable | Recommended value / note |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Cloud Run backend URL |
| `NEXT_PUBLIC_CHAT_TIMEOUT_MS` | `180000` recommended |

Backend:

| Variable | Recommended value / note |
|---|---|
| `DATABASE_URL` | PostgreSQL/Supabase URL; include `sslmode=require` for hosted DBs |
| `ENVIRONMENT` | `production` on Cloud Run |
| `JWT_SECRET` | Required in production, even though active sandbox login stores local user context |
| `FFIA_AUTH_USERS_JSON` | Single-line JSON array of PBKDF2 users |
| `GCP_PROJECT_ID` | Google Cloud project ID |
| `GCP_SERVICE_ACCOUNT_JSON` | Inline service account JSON, or use Cloud Run service account identity |
| `VERTEX_LOCATION` | Example: `asia-southeast1` |
| `FFIA_AGENT_MODEL` | Example: `gemini-2.5-flash` |
| `CORS_ORIGINS` | Vercel frontend origin |
| `FFIA_AGENT_TIMEOUT_SECONDS` | `150` recommended |

Reliability note: frontend chat timeout should exceed backend agent timeout.
Recommended production sizing is frontend `180s`, backend agent `150s`, and
Cloud Run request timeout `300s`.

Deployment artifact note: this repository currently documents the Vercel +
Cloud Run target, but checked-in `Dockerfile` / `cloudbuild.yaml` deployment
artifacts are not present.

---

## Known Limitations / Future Implementation

These are intentionally listed so the submission reflects the real MVP scope:

- RAG / semantic retrieval is not active in the product flow.
- `rag_cost_history_tool` exists but is not registered in the active agent.
- `invoice_embeddings` schema helpers exist, but invoice indexing is not wired into OCR save or chat.
- `ingredient_matching_template.csv` and ingredient aliases are not used by product lookup yet.
- `pg_trgm` fuzzy matching is not implemented.
- Fuzzy ingredient search is not implemented.
- `platform_gp_lookup_tool` exists but is not registered in the active agent.
- L2 Cross-Platform Margin Arbitrage is documented only.
- L5 Dynamic Delivery Radius Control is documented only.
- Deterministic menu margin calculator and scenario simulator tools are planned future work.
- Reasoning trace is lightweight tool-observation visibility, not hidden chain-of-thought.

---

## Vibe-Coding Tools Used

| Tool | What it was used for |
|---|---|
| Claude Code | Scaffolding, UI iteration, agent implementation support |
| Codex | Read-only audit, reliability fixes, documentation correction |
| Gemini 2.5 Flash | LLM powering the ReAct agent via Vertex AI |
| LangChain / LangGraph | Agent framework and tool orchestration |
| PostgreSQL/Supabase | Persistent restaurant, invoice, and reference data |

---

*Last updated for submission: Next.js + FastAPI MVP, active LangGraph agent, PostgreSQL source of truth, Vercel + Cloud Run deployment target, with RAG/fuzzy/L2/L5 clearly marked as future implementation.*

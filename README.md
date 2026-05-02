# FFIA — Fuel & Food Impact Analyzer

> **MADT 7204 Vibe Coding Project** | Team 2 | Bangkok Oil Price Crisis

---

## Team

| Role | Name |
|---|---|
| **IT Lead** | Kanpirom Suksawat |
| Mgmt Member | Pornphrom Rujiwatchara-oran |
| Mgmt Member | Anantaporn Lapsakkarn |
| Mgmt Member | Jantana Pattarapronpisit |
| Mgmt Member | Rapeepat Rattanapachai |

---

## Problem Statement

Oil prices in Thailand are at historic highs. For Bangkok restaurants, this crisis is not just
about cooking fuel — it silently raises costs throughout the entire supply chain:

- **Invisible Cost Transmission**: Fuel surcharges are embedded inside delivery and logistics
  fees, but restaurant owners only calculate profit based on ingredient costs. The true margin
  is always lower than they think.
- **Reactive Pricing Risk**: Without data, owners guess at menu prices. This leads to
  "selling well but losing money" — or pricing so high they lose customers.
- **Operational Blindspot**: There is no tool today that shows, in real time, how a 1 baht
  change in diesel price affects the gross margin of a specific menu item.

**FFIA solves this** by combining live EPPO oil price data with the restaurant's own menu cost
sheet, then using an AI agent to calculate true margins, simulate price scenarios, and recommend
concrete actions — with full reasoning transparency so owners can trust the output.

---

## Current State (W4)

- **Agent**: LangGraph ReAct agent powered by Gemini 2.5 Flash (Vertex AI)
- **Tools**: PostgreSQL SQL tool, Bangchak oil price API tool, ingredient market price tool, platform GP lookup tool, RAG vector search tool, 4 business-rule tools (platform floor guard, promo profitability, COGS alert, scenario classifier), DuckDuckGo web search
- **UI**: Streamlit app modularized into `app/views/` pages and `app/components/`; 3-step guided Business Setup stepper; invoice delete; dark sidebar with active-state nav
- **Data**: PostgreSQL connected via `DATABASE_URL` — invoices, invoice items, restaurant profiles, ingredient market prices, and invoice embeddings stored with Row-Level Security

---

## Agent Design

> Full details in [`docs/architecture.md`](docs/architecture.md)

FFIA is an **agentic AI system** — the AI agent is the product, not a feature bolted onto a dashboard.

### What the agent does
1. Fetches today's oil price live from the Bangchak Oil Price API
2. Queries restaurant cost and invoice data from PostgreSQL (RLS-enforced per user)
3. Calculates the real gross margin per menu item (including hidden fuel/platform costs)
4. Evaluates delivery platform profitability (platform floor guard — Rule L1)
5. Checks whether a planned promotion is financially viable (promo profitability — Rule L3)
6. Monitors raw material COGS changes and recommends substitutes (COGS alert — Rule L4)
7. Classifies the business situation into Scenario 1/2/3 and provides an action plan
8. Explains its reasoning step by step (transparent ReAct loop)

### Tools the agent uses
| Tool | File | Purpose |
|---|---|---|
| `oil_price_tool` | `agent/tools/oil_price_tool.py` | Live diesel/gasohol prices from Bangchak API (Thai & English aliases) |
| `postgres_tool` | `agent/tools/postgres_tool.py` | SELECT queries against PostgreSQL with RLS + 50-row cap |
| `ingredient_price_tool` | `agent/tools/ingredient_price_tool.py` | Ingredient market price lookup from PostgreSQL reference table |
| `platform_gp_lookup_tool` | `agent/tools/platform_gp_lookup_tool.py` | Per-platform gross profit % lookup |
| `rag_tool` | `agent/tools/rag_tool.py` | Vector similarity search over saved invoice embeddings (pgvector) |
| `platform_floor_guard_tool` | `agent/tools/business_rules_tool.py` | Platform cost floor check — HEALTHY/WATCH/WARNING/CRITICAL (Rule L1) |
| `promo_profitability_tool` | `agent/tools/business_rules_tool.py` | Promo viability + psychological pricing recommendation (Rule L3) |
| `cogs_alert_tool` | `agent/tools/business_rules_tool.py` | COGS impact alert + substitute ingredient map (Rule L4) |
| `scenario_classifier_tool` | `agent/tools/business_rules_tool.py` | Classify situation into Scenario 1/2/3 with action plan |
| `search_tool` | `agent/tools/search_tool.py` | Web search via DuckDuckGo (fallback for general queries) |

### LLM
Gemini 2.5 Flash via Vertex AI (`langchain-google-vertexai` / `ChatVertexAI`) — powers the agent's ReAct reasoning loop. Auth via GCP service account (`GCP_SERVICE_ACCOUNT_JSON` + `GCP_PROJECT_ID`).

---

## Repository Structure

```
agentic-ai-mcp/
├── agent/
│   ├── main.py                          # LangGraph ReAct agent + run_agent() function
│   ├── tools/
│   │   ├── oil_price_tool.py            # Live oil price from Bangchak API
│   │   ├── business_rules_tool.py       # L1 platform guard, L3 promo, L4 COGS, scenario classifier
│   │   ├── postgres_tool.py             # PostgreSQL SELECT tool (RLS-enforced, 50-row cap)
│   │   ├── ingredient_price_tool.py     # Ingredient market price lookup from PostgreSQL
│   │   ├── platform_gp_lookup_tool.py   # Per-platform GP % lookup
│   │   ├── rag_tool.py                  # Invoice embedding vector search (pgvector)
│   │   └── search_tool.py               # DuckDuckGo web search tool
│   └── prompts/
│       └── system_prompt.txt            # Agent role, tool guidance, Bangkok/THB context, output format
├── app/
│   ├── main.py                          # Streamlit bootstrap — auth wall, CSS, sidebar, page router
│   ├── views/
│   │   ├── chat.py                      # AI Assistant chat page
│   │   ├── dashboard.py                 # Dashboard page — decision cards, quick actions
│   │   ├── profile.py                   # Business Setup 3-step stepper — profile form + upload + readiness
│   │   └── upload.py                    # Data Upload page — OCR invoice ingestion
│   ├── components/
│   │   ├── layout.py                    # _render_page_hero(), _render_section_header(), _load_logo_b64()
│   │   └── sidebar.py                   # _render_sidebar(), _render_sidebar_nav_button()
│   ├── styles/
│   │   └── main_css.py                  # Global CSS theme string (injected via st.markdown)
│   ├── utils/
│   │   ├── auth.py                      # PBKDF2 password verification, session helpers
│   │   ├── ocr.py                       # Claude Vision invoice OCR and JSON cleanup
│   │   └── upload_cache.py              # Upload file cache key builder
│   └── assets/
│       ├── ffia_logo_design.png         # Sidebar logo
│       ├── grab.png                     # Grab delivery platform icon
│       ├── lineman.png                  # LINE MAN delivery platform icon
│       ├── shopeefood.png               # Shopee Food delivery platform icon
│       └── walkin.png                   # Walk-in channel icon
├── data/
│   ├── db.py                            # PostgreSQL helpers — invoice CRUD, profile upsert, RAG schema, RLS
│   ├── scripts/
│   │   ├── oil_price_pipeline.py        # Oil price data ingestion pipeline
│   │   └── seed_ingredient_aliases.py   # Ingredient alias seeding script
│   └── raw/
│       ├── ingredient_market_price.csv          # Ingredient reference prices
│       └── ingredient_matching_template.csv     # Alias mapping template
├── docs/
│   ├── architecture.md              # Agent architecture documentation
│   ├── business_rules.md            # Margin formulas, cost thresholds, pricing rules
│   ├── scenarios.md                 # What-if scenario definitions (Scenario 1/2/3)
│   ├── data_definition.md           # Schema definitions and field meanings
│   ├── demo_script.md               # Guided demo flow and expected agent responses
│   └── rubric-status.md             # Weekly milestone & grading tracker
├── tests/                           # Unit and integration tests
├── notebooks/                       # Exploratory notebooks
├── .env.example                     # Environment variable template (safe to commit)
├── .gitignore                       # Excludes .env, credentials, __pycache__
├── CLAUDE.md                        # Claude Code instructions for this project
├── requirements.txt                 # Python dependencies
└── README.md
```

---

## Data Sources

| Source | Type | How Used |
|---|---|---|
| Bangchak Oil Price API | Public/Industry | Live diesel and gasohol prices fetched by `oil_price_tool` |
| PostgreSQL (Supabase) | Cloud Database | Restaurant cost, invoice, and profile data — RLS per user tenant |
| DuckDuckGo Web Search | Free API | Real-time news and general price lookups (fallback) |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- GCP service account with Vertex AI access (`GCP_SERVICE_ACCOUNT_JSON`, `GCP_PROJECT_ID`) — powers both the Gemini 2.5 Flash agent and the Claude Vision OCR
- PostgreSQL database accessible via connection URL (`DATABASE_URL`)
- pgvector extension enabled on the PostgreSQL instance (for RAG tool)

### Steps

```bash
# Step 1: Clone the repository
git clone <repo-url>
cd agentic-ai-mcp

# Step 2: Create your environment file from the template
# SECURITY: Never commit the real .env file
cp .env.example .env

# Step 3: Fill in your runtime credentials in .env
# Required:
#   DATABASE_URL=postgresql://user:password@host:5432/dbname
#   JWT_SECRET=<64-char hex>  # python3 -c "import secrets; print(secrets.token_hex(32))"
#   FFIA_AUTH_USERS_JSON=[{"username":"...","password_hash":"pbkdf2_sha256$...","display_name":"..."}]
#   GCP_PROJECT_ID=your-gcp-project-id
#   GCP_SERVICE_ACCOUNT_JSON=<contents of gcp-key.json as a single-line string>
#   CORS_ORIGINS=http://localhost:3000
# Optional (defaults shown):
#   ENVIRONMENT=development        # set to "production" on Cloud Run
#   VERTEX_LOCATION=asia-southeast1
#   FFIA_AGENT_MODEL=gemini-2.5-flash
#   FFIA_AGENT_TIMEOUT_SECONDS=90

# Step 4: Create and activate a Python virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Step 5: Install dependencies
pip install -r requirements.txt

# Step 6: Run the Streamlit UI
streamlit run app/main.py

# Optional: Test the agent via CLI only
python agent/main.py
```

## Next.js + FastAPI Migration Sandbox

This sandbox path replaces the Streamlit UI with a Next.js frontend while keeping the existing Python agent, tools, business rules, and database helpers behind a thin FastAPI wrapper.

### Backend

```bash
cd agentic-ai-mcp
cp .env.example .env
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

Sandbox endpoints:

- `GET /health`
- `POST /chat`
- `GET /dashboard-summary`

The unauthenticated dashboard wrapper uses `FFIA_DEMO_USER_ID` when no `user_id` query parameter is supplied. Missing database, oil price, or profile data returns `null` or empty arrays instead of crashing the dashboard.

#### Cloud Run — Required Environment Variables

| Variable | Notes |
|---|---|
| `ENVIRONMENT` | Set to `production` — enforces JWT_SECRET check at startup |
| `DATABASE_URL` | Add `?sslmode=require` for all cloud-hosted PostgreSQL |
| `JWT_SECRET` | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `FFIA_AUTH_USERS_JSON` | Single-line JSON array of users with PBKDF2 hashes |
| `GCP_PROJECT_ID` | GCP project ID |
| `GCP_SERVICE_ACCOUNT_JSON` | Inline JSON string — **not** a file path. Or use Cloud Run Service Account (Workload Identity) and omit this var. |
| `VERTEX_LOCATION` | Default: `asia-southeast1` |
| `FFIA_AGENT_MODEL` | Default: `gemini-2.5-flash`. Both the agent and OCR use this var. |
| `CORS_ORIGINS` | Frontend Cloud Run URL — use `CORS_ORIGINS`, **not** `FRONTEND_ORIGINS` |
| `FFIA_AGENT_TIMEOUT_SECONDS` | Default: `60`. Recommend `90` on Cloud Run. |

Store sensitive values (`JWT_SECRET`, `DATABASE_URL`, `GCP_SERVICE_ACCOUNT_JSON`, `FFIA_AUTH_USERS_JSON`) in Secret Manager and mount via `--set-secrets`. See `.env.cloudrun.example` for the full template.

### Frontend

```bash
cd agentic-ai-mcp/frontend
cp .env.example .env.local
npm install
npm run dev
```

Local URLs:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/health`

Do not commit `.env`, `.env.local`, `gcp-key.json`, service account keys, or other secrets.

---

## Vibe-Coding Tools Used

| Tool | What it was used for |
|---|---|
| Claude Code (Anthropic) | Repo scaffolding, agent implementation, UI design, code review |
| Codex (OpenAI) | Project review, debugging, reliability fixes, and optimization |
| Gemini 2.5 Flash (Google) | LLM powering the ReAct agent reasoning loop |
| LangChain / LangGraph | Agent framework, tool orchestration |
| Streamlit | Chat UI and reasoning trace dashboard |
| PostgreSQL | Restaurant cost and invoice data storage/querying |

---

## Known Limitations & Next Steps

- `calculate_margin` tool — compute true net margin per menu item using invoice and profile data — planned next.
- `simulate_scenario` tool — what-if oil price sensitivity analysis — planned next.
- Multi-agent pattern (Planner → Data Agent + Margin Agent + Recommendation Agent) — future.
- GraphRecursionLimit hardening — graceful UI fallback when agent loops exceed `recursion_limit=9` — in progress.

---

*Last updated: W4 — app modularized into views/components, RAG vector search tool, ingredient price tool, platform GP lookup tool, 3-step Business Setup stepper, invoice delete UI, Vertex AI auth.*
